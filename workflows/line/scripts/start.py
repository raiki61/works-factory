# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""線の始めの節 start（docs/design.md の「メイングラフ」の「順と承認ノード」の 1）。

入口の入力を 1 つの形にそろえ（lib/entryshape.py）、始めの記録（lib/startrec.py の start.json の形）を run の置き場に書き、
指し札で返す。差分も依頼の行も無い・入力の組み合わせが拒まれる時は、落ちずに ok: false と止めの理由の語を返す。後ろの節は
when: で飛び、collect・report・result だけが走る（AI を起こす前に止める）。

固定材料（fix_fixture。lib/fixture.py）を名指した run は、前の run の修正の前の置き場の写しを取り込み（照らしと拒みは
fixture.adopt。拒みは AI の前）、始めの記録は写しの物を今の run の id・入力・版の控え・機能の切り替え・依頼のファイルの道にして書く。GitHub の読み・
差分の測り・入口の形・方針の固め・PR のファイルは写しの物を使うので回さない。返りの from_fixture が真で、fixture が置き場の根の
fixture.CARRIED（修正の段へ運ぶ値）のポインタ。後ろは直す前のテスト・判定・計画を飛ばし、fix-in がそれを受けて修正から始める。

入力は線の inputs:（環境変数 INPUTS_<名>）。対象のリポジトリは節の作業の置き場（cwd）。
返りの reuse_dir・user_env_dir はメイングラフの run の共有の置き場（同じ run の中の試験の結果の控え tree_run.reuse_dir と、利用者の
HOME・XDG に戻して起こした印の置き場＝run の置き場）の絶対パスで、メイングラフが入力でブロックへ渡す。拒んだ run と落ちた返りの
reuse_dir は空（後ろの節は飛ぶ）。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import answer
    import carry
    import declared_checks
    import depth
    import entry
    import entryshape
    import fixture
    import gatemarks
    import gatepolicy
    import ghreads
    import policy
    import startrec
    import stopby
    import tddloop
    import tree_run
    import versions

    DESIGN_ONLY_WORDS = ("", gatemarks.DESIGN_ONLY)
    THICKNESS = ("", "自動", *depth.HEADS)
SPEC_ON = "on"
SPEC_WORDS = ("", SPEC_ON)
AUTO = "自動"   # thickness の既定（元 works/.shared/core/entry.py 412 行の THICKNESS_DEFAULT）
PIN = ("factory/pack.json", "integration_revision_required")   # 止めた Archon の commit（ASF の止め。Archon の版の正本）
MODEL_UNKNOWN = ("run 全体の模型の 1 つの値は無い——Archon が役のノードごとに model・provider から決める"
                 "（止めた Archon の packages/workflows/src/node-model-resolution.ts）")
GATE = "gate-start"


class Refused(Exception):
    """入口の入力を受けない（人に向けた 1 行）"""


def raw_inputs() -> dict:
    return {
        "request": os.environ.get("INPUTS_REQUEST", ""),
        "base": os.environ.get("INPUTS_BASE", ""),
        "pr": os.environ.get("INPUTS_PR", ""),
        "spec": os.environ.get("INPUTS_SPEC", ""),
        "test_cmd": os.environ.get("INPUTS_TEST_CMD", ""),
        "tdd_suite": os.environ.get("INPUTS_TDD_SUITE", ""),
        "final_gate": os.environ.get("INPUTS_FINAL_GATE", ""),
        "unattended": os.environ.get("INPUTS_UNATTENDED", ""),
        "design_only": os.environ.get("INPUTS_DESIGN_ONLY", ""),
        "thickness": os.environ.get("INPUTS_THICKNESS", ""),
        "features_off": os.environ.get("INPUTS_FEATURES_OFF", ""),
        "features_on": os.environ.get("INPUTS_FEATURES_ON", ""),
        "policy_md": os.environ.get("INPUTS_POLICY_MD", ""),
        "fix_fixture": os.environ.get("INPUTS_FIX_FIXTURE", ""),
        "lang": os.environ.get("INPUTS_LANG", ""),
        "deliver": os.environ.get("INPUTS_DELIVER", ""),
    }


def words(raw: dict, repo: Path) -> dict:
    """入力の語と名指したファイルを確かめる。受けない組み合わせ・無いファイルは Refused"""
    spec = raw["spec"].strip()
    if spec not in SPEC_WORDS:
        raise Refused(f"spec={raw['spec']!r} は知らない値（空か {SPEC_ON}）")
    try:
        gate = gatepolicy.check(raw["final_gate"], raw["unattended"], spec=bool(spec))
        off, on = entry.features_off(raw["features_off"]), entry.features_on(raw["features_on"])
        entry.deliver_word(raw["deliver"])
    except (gatepolicy.Refused, entry.InputRefused) as error:
        raise Refused(str(error)) from None
    both = sorted(set(off) & set(on))
    if both:
        raise Refused(f"features_on と features_off の両方に {', '.join(both)} を名指した（片方だけ）")
    design_only = raw["design_only"].strip()
    if design_only not in DESIGN_ONLY_WORDS:
        raise Refused(f"design_only={raw['design_only']!r} は知らない値（空か {gatemarks.DESIGN_ONLY}）")
    thickness = raw["thickness"].strip()
    if thickness not in THICKNESS:
        raise Refused(f"thickness={raw['thickness']!r} は知らない値（{' / '.join(t for t in THICKNESS if t)}）")
    clash = sorted(set(off) & set(depth.tier_adds(depth.named(thickness))))
    if clash:
        raise Refused(f"thickness={thickness} が足す機能 {', '.join(clash)} を features_off で切った（段を変えるか、切りを外す）")
    fix_fixture = fixture_dir(raw["fix_fixture"], repo)
    if fix_fixture and spec:
        raise Refused("仕様の段（spec=on）は固定材料（fix_fixture）と組めない（固定材料は判定と修正案が済んだ所の写しで、仕様の段は"
                      "判定の中に在る）")
    return {**gate, "spec": spec, "design_only": design_only, "thickness": thickness, "features_off": off, "features_on": on,
            "policy_md": policy_md(raw["policy_md"], repo), "fix_fixture": fix_fixture}


def fixture_dir(rel: str, repo: Path) -> str:
    """固定材料のフォルダの絶対パス（名指しが無ければ空）。相対なら対象の根から。フォルダでなければ Refused（元 use.sh の
    WORKS_USE_FIX_FIXTURE: 在るフォルダでなければ何も作らずに拒む）"""
    rel = rel.strip()
    if not rel:
        return ""
    path = Path(rel) if Path(rel).is_absolute() else repo / rel
    if not path.is_dir():
        raise Refused(f"名指した固定材料のフォルダ {rel} が無い（fix_fixture。前の run の報告の「固定材料」の行のフォルダを名指す）")
    return str(path.resolve())


def policy_md(rel: str, repo: Path) -> str:
    """方針の文書の絶対パス（名指しが無ければ空）。名指した文書が無ければ Refused。元 works/.shared/core/entry.py 588-593 行"""
    rel = rel.strip()
    if not rel:
        return ""
    path = Path(rel) if Path(rel).is_absolute() else repo / rel
    if not path.is_file():
        raise Refused(f"名指した方針の文書 {rel} が無い（policy_md。人の方針の文書を名指すなら先に置く）")
    return str(path)


def request(raw: dict, repo: Path) -> dict:
    """依頼のファイルを読む: {items, request_file, request_text, parts}。名指しが無ければ空"""
    rel = raw["request"].strip()
    if not rel:
        return {"items": [], "request_file": "", "request_text": "", "parts": carry.parts([])}
    path = Path(rel) if Path(rel).is_absolute() else repo / rel
    try:
        body = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refused(f"依頼のファイル {rel} が読めない（{type(error).__name__}: {error}）") from None
    try:
        doc = json.loads(body)
    except ValueError as error:
        raise Refused(f"依頼のファイル {rel} が JSON として読めない（{error}）") from None
    try:
        parts = carry.parts(doc)
    except ValueError as error:
        raise Refused(f"依頼のファイル {rel} の形: {error}") from None
    problems = entry.request_problems(parts[carry.FINDINGS]) if parts[carry.FINDINGS] else []   # 空は refuse_empty が見る
    if problems:
        raise Refused(f"依頼のファイル {rel} の形: findings の配列か {{findings, pr, issue, answers}} の形で、findings は "
                      "[{where, text, mechanism?, measured?, false_positive_if?}] の配列: " + "; ".join(problems))
    return {"items": parts[carry.FINDINGS], "request_file": str(path.resolve()), "request_text": body, "parts": parts}


def version_record(root: Path, raw: dict, run_id: str) -> dict:
    """版の控え（lib/versions.py。元 works/.shared/core/versions.py）。止めた Archon の commit と模型は線が引いて渡す"""
    archon, why = versions.pinned(root / PIN[0], PIN[1])
    return versions.snapshot(root, run_id=run_id, settings={k: raw[k] for k in ("features_off", "features_on")},
                             given={"archon": (archon, f"止めた Archon の commit を引けない（{why}）"),
                                    "model": (None, MODEL_UNKNOWN)})


def depth_words(raw: dict, record: dict) -> str:
    """頭の行の段の句（元 works/.shared/core/entry.py 1215 行。名指しが無ければ「（既定）」を付ける）"""
    return f"段: {record['thickness'] or AUTO}" + ("" if raw["thickness"].strip() else "（既定）")


def test_notes(raw: dict, repo: Path) -> list:
    """テストの注: 修正前のテストの任せ先（元 entry.py 1218-1219 行。test_cmd も対象の宣言も無ければ、任せ先の役が走らせ方を探す）と、
    tdd_suite を省いた run が TDD の輪を飛ばす事（元 use.sh 1086-1089 行）"""
    notes = []
    if not raw["test_cmd"].strip() and "fallback" in declared_checks.checks_plan(repo):
        notes.append("修正前のテスト: 宣言も test_cmd も無い——任せ先の役がリポジトリから走らせ方を探す")
    if not raw["tdd_suite"].strip():
        notes.append(tddloop.SUITE_SKIPPED)
    return notes


def gate_text(shape: dict, record: dict, run_id: str, notes: list) -> str:
    happened = f"run を始める前で止まった。入口: {startrec.words(shape)}"
    rest = [*fixture.lines(record), depth_words(record["inputs"], record),
            entry.features_part(record["features_off"], record["features_on"], adds(record),
                                depth.tier_auto(depth.named(record.get("thickness")))), gatepolicy.head_words(record), *notes]
    lines = gatemarks.head3(happened, "この入力で run を始めるか、止めるか（打つ行は末尾の答え方）", gatemarks.NO_PUSH)
    lines += ["", *[f"- {x}" for x in rest if x], "", "答え方:",
              f"- 始める: {answer.line(run_id, 'continue', '<一言>')}",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return "\n".join(lines) + "\n"


def write(artifacts: Path, doc) -> dict:
    """始めの記録を run の置き場の根を盤面の根として startrec の置き場に書き、指し札を返す（lib の読み手と同じ所。L-E24）"""
    startrec.write(artifacts, doc)
    return boundary.pointer(startrec.REL)


def adds(checked: dict) -> tuple:
    return depth.tier_adds(depth.named(checked.get("thickness")))


def features(checked: dict) -> dict:
    """始めの記録の機能の切り替えの 4 つの欄（名指した段の足しを入れる。名指した段の足しと features_off のぶつかりは words が拒む）"""
    off, on, more = checked["features_off"], checked["features_on"], adds(checked)
    return {entry.FEATURES_KEY: off, entry.FEATURES_ON_KEY: on, entry.FEATURES_CUT_KEY: entry.features_cut(off, on, more),
            "features": entry.feature_words(off, on, more)}


def from_fixture(raw: dict, checked: dict, asked: dict, repo: Path, artifacts: Path, run_id: str, versions_doc: dict) -> dict:
    """固定材料を取り込んで始めの記録を書き、start の返りを組む。取り込めなければ Refused（何も書かない）"""
    try:
        doc, _ = fixture.adopt(artifacts, checked["fix_fixture"], repo, run_id=run_id, inputs=raw,
                               request_text=asked["request_text"])
    except fixture.FixtureRefused as error:
        raise Refused(f"固定材料を取り込まない: {error}") from None
    named = asked["request_file"]
    doc.update({"versions": versions_doc, **features(checked), "request_file": named,
                "input": {**startrec.shape(doc), "request_file": named}})
    prior = boundary.pointer(carry.PRIOR_IN_FILE) if (artifacts / carry.PRIOR_IN_FILE).is_file() else None
    return begun(doc, startrec.shape(doc), prior, raw, repo, artifacts, run_id, boundary.pointer(fixture.CARRIED))


def begun(record: dict, shape: dict, prior, raw: dict, repo: Path, artifacts: Path, run_id: str, carried=None) -> dict:
    """始めの記録 record を書き、start の通った返りを組む。carried は固定材料の run の運ぶ値のポインタ（ほかの run は None）"""
    unattended = gatepolicy.unattended_of(record)
    return {"ok": True, "stop_reason": "", "reason": "", "record": write(artifacts, record), "prior_failures": prior,
            "ask": not unattended, "gate_text": gate_text(shape, record, run_id, test_notes(raw, repo)),
            "unattended": unattended, "design_only": record["design_only"] == gatemarks.DESIGN_ONLY,
            "final_gate": record[gatepolicy.FINAL_KEY], "spec": bool(record["spec"]),
            "from_fixture": carried is not None, "fixture": carried, "reuse_dir": str(tree_run.reuse_dir(artifacts)),
            "user_env_dir": str(artifacts)}


def start(raw: dict, repo: Path, artifacts: Path, run_id: str) -> dict:
    record = {"run_id": run_id, "inputs": raw, "versions": version_record(boundary.lib_root().parent, raw, run_id)}
    try:
        checked = words(raw, repo)
        asked = request(raw, repo)
        if checked["fix_fixture"]:
            return from_fixture(raw, checked, asked, repo, artifacts, run_id, record["versions"])
        reads = entryshape.github_reads(artifacts, repo, raw)
        if reads is not None:
            ghreads.place(artifacts, reads)
        change = entryshape.change_base(raw, repo, reads)
        entryshape.refuse_empty(asked["items"], change, repo)
        inp = {"items": asked["items"], "request_file": asked["request_file"], "request_text": asked["request_text"],
               "base": change["base"] if change else None, "pr": change["pr"] if change else None,
               "spec": bool(checked["spec"])}
        pr = inp["pr"] or {}
        if checked["spec"] and not asked["items"] and not (pr.get("title") or pr.get("body")):
            raise Refused("spec=on なのに依頼の文が無い（依頼の findings も PR の題と本文も無い）——仕様の書き手が読む物が無い。"
                          "findings を書いた依頼か PR を名指すか、仕様の段を外す")
        shape = entryshape.build(inp, repo)
    except (Refused, entryshape.Refused) as error:
        record["refused"] = str(error)
        return {"ok": False, "stop_reason": stopby.START_REFUSED, "reason": str(error),
                "record": write(artifacts, record), "prior_failures": None, "ask": False, "gate_text": "",
                "unattended": False, "design_only": False, "final_gate": "", "spec": False, "from_fixture": False, "fixture": None,
                "reuse_dir": "", "user_env_dir": str(artifacts)}
    parts = asked["parts"]
    record.update({
        "input": shape, "base_rev": shape["head_rev"], "review_rev": shape["head_rev"], "request_file": asked["request_file"],
        "test_cmd": raw["test_cmd"], "tdd_suite": raw["tdd_suite"],
        gatepolicy.FINAL_KEY: checked[gatepolicy.FINAL_KEY], gatepolicy.UNATTENDED_KEY: checked[gatepolicy.UNATTENDED_KEY],
        "design_only": checked["design_only"], "thickness": checked["thickness"], "spec": checked["spec"],
        "policy_md": checked["policy_md"], "policy": policy.freeze(artifacts, repo, checked["policy_md"]), "lang": raw["lang"],
        **features(checked),
        "answers": parts[carry.ANSWERS], "request_text": entryshape.request_text(inp),
        "pr_file": entryshape.write_pr_file(artifacts, inp),
    })
    prior = None
    if parts[carry.PRIOR]:
        carry.place_prior(artifacts, parts[carry.PRIOR])
        prior = boundary.pointer(carry.PRIOR_IN_FILE)
    return begun(record, shape, prior, raw, repo, artifacts, run_id)


def fallback(reason: str) -> dict:
    return {"ok": False, "stop_reason": boundary.LINE_SCRIPT, "reason": reason, "record": None, "prior_failures": None,
            "ask": False, "gate_text": "", "unattended": False, "design_only": False, "final_gate": "", "spec": False, "from_fixture": False,
            "fixture": None, "reuse_dir": "", "user_env_dir": os.environ.get("ARTIFACTS_DIR", "")}


if __name__ == "__main__":
    boundary.run(lambda: start(raw_inputs(), Path.cwd(), Path(os.environ["ARTIFACTS_DIR"]), os.environ["WORKFLOW_ID"]),
                fallback)
