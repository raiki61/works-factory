"""緑の認証の行: 作業ツリーの指紋と、赤の原因の分け方と、認証の判定。

- diff_bytes(repo, rev, *, skip=()) -> bytes: 作業ツリーの今の姿の木と rev の間の差分のバイト（差分の組み方の 1 か所。除くパスの頭 skip の下は載せない）
- diff_between(repo, before, after, *, skip=()) -> bytes: 2 つの commit の間の差分のバイト（diff_bytes と同じ旗）
- fingerprint(repo) -> {"head", "diff_hash"}: HEAD と、HEAD に対する diff_bytes の sha256
- matches(cert_fingerprint, repo) -> bool: 認証の指紋が今の作業ツリーと同じか
- classify(...) -> (red_cause, summary): 事実だけで赤の原因を分ける
- certify(...) -> (ok, reason): 認証してよいか
- ran_steps(runs, junit_unran) -> {"ran", "unran"}: 起こした段と、起こせない・試験を走らせなかった段の名（ran_note の steps）
- ran_note(*, green, red_cause, by, steps=None) -> str: 試験が走ったかの、報告と関所の冒頭に出す句（RAN_NOTES のどれかと案内か ""）

ASF の `W/.shared/validation-evidence.ts`:1-23（HEAD と追跡ファイルの binary の差分）と `W/deliver/scripts/gate-green.ts` に倣う。
"""
import hashlib

import baseline_red
import declared_checks
import gatemarks
import tree_run
import unittrees

MEASURED = ("clean", "found")
# 素材の語の持ち主は gatemarks.MATERIAL_WORDS。測った結果でない語は全部未了で、落ちた先の分けで黙って認証しない
NOT_DONE = tuple(w for w in gatemarks.MATERIAL_WORDS if w not in MEASURED)
NOT_APPLICABLE = "not_applicable"
AWAITING_HUMAN = "awaiting_human"
BASE_OK = MEASURED + (NOT_APPLICABLE, AWAITING_HUMAN)
INCOMPLETE = "incomplete"   # 赤の原因: 測り切れていない（classify の 3.）
ENVIRONMENT = "environment"   # 赤の原因: 赤の段が全部起こせない（classify の 2.）
INTRODUCED = "introduced"   # 赤の原因: 直しが起こした赤（classify の 4.）
INHERITED = "inherited"   # 赤の原因: 元から落ちていた赤（classify の 5.）
INTERACTION = "interaction"   # 赤の原因: 修正どうしの絡みの赤（classify は返さない。test-gate の返りの enum が持つ）
NOT_RAN = "工場の中では試験が走っていない"
PARTLY_RAN = "工場の中では試験の段の一部しか走らせられていない"
UNVERIFIED_RUN = "工場の中では試験が走ったと確かめられていない"
GATE_BROKE = "工場の中で試験の関門の script が落ちたか返さなかった（試験が走ったかは分からない。工場の不具合）"
# 赤の原因の語（試験の関門の返りの red_cause の enum。tests/workflows/test_test_gate.py が照らす）ごとの、試験が走ったかの句。
# 1 件ごとの事実で分けた赤（introduced・inherited・interaction）は走った赤なので句を出さない
RAN_BY_CAUSE = {INTRODUCED: "", INHERITED: "", ENVIRONMENT: NOT_RAN, INTERACTION: "", INCOMPLETE: NOT_RAN, "": UNVERIFIED_RUN}
RED_CAUSES = tuple(RAN_BY_CAUSE)
RAN_NOTES = (NOT_RAN, PARTLY_RAN, UNVERIFIED_RUN, GATE_BROKE)
GATE_BROKE_BY = ""   # 返す節の中の誤り（workflows/test-gate/scripts/result.py の failed）か、関門が返さなかった時の返りの by
RAN_GUIDE = f"準備が要る道具は {declared_checks.declared.SETUP_HINT}、か工場の外の手元で試験を回す"
HEAD_LIMIT = 10   # summary に並べる鍵の数


def diff_bytes(repo, rev, *, skip=()) -> bytes:
    """unittrees.fresh_tree(repo)（追跡のファイルと .gitignore に当たらない未追跡のファイルの中身・実行ビット・シンボリックリンクの木。
    本物の index・HEAD は動かさない）と rev の間の `git diff <unittrees._DIFF の旗> <rev> <その木>` のバイト（--binary・--no-renames・--no-ext-diff・--no-textconv・
    --no-color と、a/・b/ の頭を固める旗。利用者の git の設定で字が変わらない）。除くパスの頭 skip（writes.check と同じ形）の下は載せない。
    git の木でない・rev が引けなければ ValueError。fingerprint・合わせの封印・累積差分が同じこの関数を使う"""
    try:
        tree = unittrees.fresh_tree(repo)
        return unittrees._git(repo, *unittrees._DIFF, rev, tree, "--", *unittrees.pathspec_without(skip)).stdout
    except (unittrees.UnitTreeError, OSError) as e:
        raise ValueError(f"差分を組めない（{repo}・{rev}）: {e}") from e


def diff_between(repo, before, after, *, skip=()) -> bytes:
    """commit before から after までの差分のバイト（旗と除くパスの頭 skip は diff_bytes と同じ。作業ツリーを読まない）。
    周の鎖の最後の差分と、周ごとの差分が使う。git の木でない・rev が引けなければ ValueError"""
    try:
        return unittrees._git(repo, *unittrees._DIFF, before, after, "--", *unittrees.pathspec_without(skip)).stdout
    except (unittrees.UnitTreeError, OSError) as e:
        raise ValueError(f"差分を組めない（{repo}・{before}..{after}）: {e}") from e


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
       junit_unran が空でなく走った赤の段（declared_checks.ran_reds。走った赤が走らなかった段より勝つ決めの持ち主）が無い → incomplete。
       走った赤の段が在れば 4.〜6. で分け、走らなかった段は summary に添える
    4. baseline_cases が在り、今の落ちた物（failure・error）に、元で通っていたか元に無かった物（baseline_red._must_pass）が在る → introduced
    5. baseline_cases が在り、落ちた物が 1 つ以上在って全部が元でも落ちていて、broken を除く赤の段が全部 junit_steps に在って junit_unran に無い → inherited
    6. ほか（JUnit の無い赤の段・shell の test_cmd の赤・baseline_cases が None）→ ""（原因の無い赤）。試験に入ったかの証拠が無いので、
       ran_note は走らなかったと言い切らず UNVERIFIED_RUN と読む（直す前と同じログの赤も、試験が同じに落ちたのと見分けられない）
    baseline_cases は元の結末の cases。呼び手は、元の結末の exit が None の時と、1 件ごとの結末の出どころが無い時に None を渡す"""
    status = (material or {}).get("status")
    if status == "clean":
        return "", ""
    reds = [r for r in runs or [] if r.get("exit") != 0]
    broken = [r for r in reds if tree_run.launch_kind(r.get("exit")) == "broken"]
    if reds and len(broken) == len(reds):
        return ENVIRONMENT, f"赤の段は全部起こせない段: {'・'.join(str(r.get('name')) for r in broken)}"
    unran = f"JUnit の報告を宣言した段が走らなかった: {'・'.join(map(str, junit_unran))}" if junit_unran else ""
    if status in NOT_DONE or (unran and not declared_checks.ran_reds(runs, junit_unran)):
        return INCOMPLETE, "；".join([*([f"素材が {status}"] if status in NOT_DONE else []), *([unran] if unran else [])])
    cause, summary = _red_cause(reds, broken, cases, baseline_cases, set(junit_steps or []) - set(junit_unran or []))
    return cause, f"{summary}（{unran}）" if unran else summary


def _red_cause(reds, broken, cases, baseline_cases, read_steps) -> tuple:
    """classify の 4.〜6.（read_steps は試験の報告を読めた段。走らなかった段の赤は受け継いだ赤と言わない）"""
    names = "・".join(str(r.get("name")) for r in reds) or "無し"
    failed = [c for c in cases or [] if c.get("outcome") in baseline_red.FAILED]
    if baseline_cases is not None:
        base = baseline_red.outcomes(baseline_cases)
        introduced = [c for c in failed if baseline_red._must_pass(c, base)]
        if introduced:
            return INTRODUCED, (f"今回落ちて元で通っていたか元に無かった {len(introduced)} 件: {_keys(introduced)}"
                                  f"（赤の段: {names}。元の結末の 1 件ごとの結末と比べた）")
        inherited = failed and all(base.get(baseline_red._key(c)) in baseline_red.FAILED for c in failed)
        if inherited and all(r.get("name") in read_steps for r in reds if r not in broken):
            return INHERITED, (f"落ちた {len(failed)} 件は全部元でも落ちていた: {_keys(failed)}"
                                 f"（赤の段: {names}。元の結末の 1 件ごとの結末と比べた）")
    return "", f"赤の段 {names}: 元の結末と比べる 1 件ごとの事実が無い（{gatemarks.BASELINE_UNVERIFIED}）"


def ran_steps(runs, junit_unran) -> dict:
    """段の行 runs を、起こした段 ran と、起こせない（tree_run.launch_kind が broken）か JUnit の報告を宣言して試験を走らせなかった
    （junit_unran に在る）段 unran の名に分ける（runs の順）。起こした段も、試験に入った証拠ではない（UNVERIFIED_RUN）"""
    unran = set(junit_unran or [])
    split = {"ran": [], "unran": []}
    for r in runs or []:
        name = str(r.get("name"))
        side = "unran" if tree_run.launch_kind(r.get("exit")) == "broken" or name in unran else "ran"
        split[side].append(name)
    return split


def ran_note(*, green, red_cause, by, steps=None) -> str:
    """試験が走ったかを、道具の名に依らず test-gate の返りだけで言う句（#492）。緑は ""。by が GATE_BROKE_BY なら GATE_BROKE
    （試験の前か後かを問わず工場の不具合で、走らなかったとは言わない）。ほかは RAN_BY_CAUSE で、知らない赤の原因は走ったと読まずに
    UNVERIFIED_RUN。NOT_RAN の時は steps（ran_steps の形）で言い直す（_not_ran）。走っていない・確かめられていない句には、
    準備を宣言する道と工場の外の手元で回す道（RAN_GUIDE）を添える"""
    if green is True:
        return ""
    if by == GATE_BROKE_BY:
        return GATE_BROKE
    note = RAN_BY_CAUSE.get(red_cause, UNVERIFIED_RUN)
    if note == NOT_RAN:
        note = _not_ran(steps, by)
    return f"{note}。{RAN_GUIDE}" if note else ""


def _not_ran(steps, by) -> str:
    """走っていないと言える時だけ NOT_RAN。起こした段と起こせなかった段が両方在れば両方を名指した PARTLY_RAN（#514）。起こした段だけ
    なら UNVERIFIED_RUN。任せ先の CI の役の run（by が declared_checks.ROLE_NEEDED）は、走らせられなかった系統を名指さなければ
    UNVERIFIED_RUN（素材を渡さずに諦めた役も、一部の系統を回してから諦めたかもしれない）。ほか（engine が段を起こさなかった）は NOT_RAN"""
    ran, unran = (steps.get("ran"), steps.get("unran")) if isinstance(steps, dict) else (None, None)
    if isinstance(ran, list) and isinstance(unran, list) and ran and unran:
        return f"{PARTLY_RAN}（走らせた段: {'・'.join(map(str, ran))}。走らせられなかった段: {'・'.join(map(str, unran))}）"
    if ran or (by == declared_checks.ROLE_NEEDED and not unran):
        return UNVERIFIED_RUN
    return NOT_RAN


SELF_REPORTED = "任せ先の自己申告の緑（機械が走らせていない）"
# 走らせ方が決まらない道（by role_needed）の final の緑: 機械が走らせたが、実行器は AI が書き、関わる試験だけを走らせた
RUNNER_HELD = "AI が書いた実行器の緑（変更に関わる試験だけを走らせた。実行器の中身は機械が照らしていない）"


def certify(*, mode, material_status, green, before, after, now, self_reported=False, material_reason="", held_reason=SELF_REPORTED) -> tuple:
    """認証してよいか ——（ok, reason）。
    - base: material_status が clean・found・not_applicable・awaiting_human なら (True, "")。awaiting_human は一部の系統だけ走らせられた
      base・宣言の書式の誤り・任せ先の役が走らせられなかった base で、系統は素材の reason が名指し、判定の台帳の awaiting の問いと
      報告の人が確かめる物に載る（鎖を止めない）。not_run（起こした段が 1 つも走らなかった base〔試験が全部 error の段は、報告に試験が並んだ（実行器が試験を集めた）ので走った段に数える〕と、test_cmd を起こせなかった base）・
      carried_over・素材が無いなら偽（緑を仮定しない）。理由は『素材が <status>——緑を仮定しない（<material_reason>）。<RAN_GUIDE>』
    - final: before・after・now の指紋が揃わなければ偽（どれが違ったかを reason に）→ green が True（bool）でなければ (False, "緑でない")
      （原因は呼び手が red_cause と証拠で別に返す）→ self_reported（素材を機械でなく任せ先の役が書いた）なら (False, SELF_REPORTED)
      → ほかは (True, "")。赤は原因が何でも認証しない。self_reported の理由は held_reason（既定 SELF_REPORTED。走らせ方が決まらない道は
      RUNNER_HELD）。任せ先の緑は走り切る前に読んだ緑と見分けられない（今の works の
      review-loop.py の _ci_by_engine。実測 2026-09-25: 572 件の途中の 537 件で clean と書いた）"""
    if mode == "base":
        if material_status in BASE_OK:
            return True, ""
        told = f"（{material_reason}）" if material_reason else ""
        return False, f"素材が {material_status or '無い'}——緑を仮定しない{told}。{RAN_GUIDE}"
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
        return False, held_reason
    return True, ""
