"""緑の認証の行: 作業ツリーの指紋と、赤の原因の分け方と、認証の判定。

- diff_bytes(repo, rev) -> bytes: 作業ツリーの今の姿の木と rev の間の差分のバイト（差分の組み方の 1 か所）
- fingerprint(repo) -> {"head", "diff_hash"}: HEAD と、HEAD に対する diff_bytes の sha256
- matches(cert_fingerprint, repo) -> bool: 認証の指紋が今の作業ツリーと同じか
- classify(...) -> (red_cause, summary): 事実だけで赤の原因を分ける
- certify(...) -> (ok, reason): 認証してよいか

ASF の `W/.shared/validation-evidence.ts`:1-23（HEAD と追跡ファイルの binary の差分）と `W/deliver/scripts/gate-green.ts` に倣う。
"""
import hashlib

import baseline_red
import gatemarks
import tree_run
import unittrees

MEASURED = ("clean", "found")
# 素材の語の持ち主は gatemarks.MATERIAL_WORDS。測った結果でない語は全部未了で、落ちた先の分けで黙って認証しない
NOT_DONE = tuple(w for w in gatemarks.MATERIAL_WORDS if w not in MEASURED)
BASE_OK = MEASURED + ("not_applicable",)
HEAD_LIMIT = 10   # summary に並べる鍵の数


def diff_bytes(repo, rev) -> bytes:
    """unittrees.fresh_tree(repo)（追跡のファイルと .gitignore に当たらない未追跡のファイルの中身・実行ビット・シンボリックリンクの木。
    本物の index・HEAD は動かさない）と rev の間の `git diff <unittrees._DIFF の旗> <rev> <その木>` のバイト（--binary・--no-renames・--no-ext-diff・--no-textconv・
    --no-color と、a/・b/ の頭を固める旗。利用者の git の設定で字が変わらない）。
    git の木でない・rev が引けなければ ValueError。fingerprint・合わせの封印・累積差分が同じこの関数を使う"""
    try:
        tree = unittrees.fresh_tree(repo)
        return unittrees._git(repo, *unittrees._DIFF, rev, tree).stdout
    except (unittrees.UnitTreeError, OSError) as e:
        raise ValueError(f"差分を組めない（{repo}・{rev}）: {e}") from e


def fingerprint(repo) -> dict:
    """{"head": HEAD の commit の sha, "diff_hash": diff_bytes(repo, "HEAD") の sha256 の 16 進}。差分が無ければ空のバイトの sha256。
    git の木でない・HEAD が引けなければ ValueError"""
    try:
        head = unittrees._out(repo, "rev-parse", "--verify", "HEAD^{commit}")
    except (unittrees.UnitTreeError, OSError) as e:
        raise ValueError(f"HEAD が引けない（{repo}）: {e}") from e
    return {"head": head, "diff_hash": hashlib.sha256(diff_bytes(repo, "HEAD")).hexdigest()}


def _fp(x):
    """指紋の形 (head, diff_hash)。dict で 2 つが文字列でなければ None"""
    if not isinstance(x, dict):
        return None
    head, diff_hash = x.get("head"), x.get("diff_hash")
    return (head, diff_hash) if isinstance(head, str) and isinstance(diff_hash, str) else None


def matches(cert_fingerprint, repo) -> bool:
    """cert_fingerprint が dict で head・diff_hash が今の fingerprint(repo) と同じ時だけ真。None・形の違い・git の誤りは偽"""
    want = _fp(cert_fingerprint)
    if want is None:
        return False
    try:
        return _fp(fingerprint(repo)) == want
    except ValueError:
        return False


def _keys(cases) -> str:
    keys = [baseline_red._key(c) for c in cases]
    more = f" ほか {len(keys) - HEAD_LIMIT} 件" if len(keys) > HEAD_LIMIT else ""
    return "・".join(keys[:HEAD_LIMIT]) + more


def classify(*, material, runs, cases, baseline_cases, junit_steps, junit_unran) -> tuple:
    """赤の原因を事実だけで分ける ——（red_cause, summary）。red_cause は ""・environment・incomplete・introduced・inherited。順:
    1. 素材の status が clean → ("", "")
    2. 赤の段（exit が 0 でない段）が 1 つ以上在り、全部が起こせない段（tree_run.launch_kind が broken）→ environment
       （今の works の entry.env_only_red。entry.py:768-772。素材が not_run でもこちらが先）
    3. status が測った結果（MEASURED）でない素材の語（NOT_DONE。not_run・awaiting_human・not_applicable・carried_over）か、
       junit_unran が空でない → incomplete
    4. baseline_cases が在り、今の落ちた物（failure・error）に、元で通っていたか元に無かった物（baseline_red._must_pass）が在る → introduced
    5. baseline_cases が在り、落ちた物が 1 つ以上在って全部が元でも落ちていて、broken を除く赤の段が全部 junit_steps に在る → inherited
    6. ほか（JUnit の無い赤の段・shell の test_cmd の赤・baseline_cases が None）→ ""（原因の無い赤）
    baseline_cases は元の結末の cases。呼び手は、元の結末の exit が None の時と、1 件ごとの結末の出どころが無い時に None を渡す"""
    status = (material or {}).get("status")
    if status == "clean":
        return "", ""
    reds = [r for r in runs or [] if r.get("exit") != 0]
    broken = [r for r in reds if tree_run.launch_kind(r.get("exit")) == "broken"]
    if reds and len(broken) == len(reds):
        return "environment", f"赤の段は全部起こせない段: {'・'.join(str(r.get('name')) for r in broken)}"
    if status in NOT_DONE or junit_unran:
        why = [f"素材が {status}"] if status in NOT_DONE else []
        why += [f"JUnit の報告を宣言した段が走らなかった: {'・'.join(map(str, junit_unran))}"] if junit_unran else []
        return "incomplete", "；".join(why)
    names = "・".join(str(r.get("name")) for r in reds) or "無し"
    failed = [c for c in cases or [] if c.get("outcome") in baseline_red.FAILED]
    if baseline_cases is not None:
        base = baseline_red.outcomes(baseline_cases)
        introduced = [c for c in failed if baseline_red._must_pass(c, base)]
        if introduced:
            return "introduced", (f"今回落ちて元で通っていたか元に無かった {len(introduced)} 件: {_keys(introduced)}"
                                  f"（赤の段: {names}。元の結末の 1 件ごとの結末と比べた）")
        steps = set(junit_steps or [])
        inherited = failed and all(base.get(baseline_red._key(c)) in baseline_red.FAILED for c in failed)
        if inherited and all(r.get("name") in steps for r in reds if r not in broken):
            return "inherited", (f"落ちた {len(failed)} 件は全部元でも落ちていた: {_keys(failed)}"
                                 f"（赤の段: {names}。元の結末の 1 件ごとの結末と比べた）")
    return "", f"赤の段 {names}: 元の結末と比べる 1 件ごとの事実が無い（{gatemarks.BASELINE_UNVERIFIED}）"


SELF_REPORTED = "任せ先の自己申告の緑（機械が走らせていない）"


def certify(*, mode, material_status, green, before, after, now, self_reported=False) -> tuple:
    """認証してよいか ——（ok, reason）。
    - base: material_status が clean・found・not_applicable なら (True, "")。not_run・awaiting_human・素材が無いなら偽（緑を仮定しない）
    - final: before・after・now の指紋が揃わなければ偽（どれが違ったかを reason に）→ green が True（bool）でなければ (False, "緑でない")
      （原因は呼び手が red_cause と証拠で別に返す）→ self_reported（素材を機械でなく任せ先の役が書いた）なら (False, SELF_REPORTED)
      → ほかは (True, "")。赤は原因が何でも認証しない。任せ先の緑は走り切る前に読んだ緑と見分けられない（今の works の
      review-loop.py の _ci_by_engine。実測 2026-09-25: 572 件の途中の 537 件で clean と書いた）"""
    if mode == "base":
        if material_status in BASE_OK:
            return True, ""
        return False, f"素材が {material_status or '無い'}——緑を仮定しない"
    if mode != "final":
        raise ValueError(f"mode は base か final: {mode!r}")
    fps = {"before": _fp(before), "after": _fp(after), "now": _fp(now)}
    missing = [k for k, v in fps.items() if v is None]
    if missing:
        return False, f"指紋が無いか形が違う: {'・'.join(missing)}"
    differ = [k for k in ("after", "now") if fps[k] != fps["before"]]
    if differ:
        return False, f"指紋が before と違う: {'・'.join(differ)}"
    if green is not True:
        return False, "緑でない"
    if self_reported:
        return False, SELF_REPORTED
    return True, ""
