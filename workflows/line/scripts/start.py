# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""line の始めの node start（docs/design/line.md の 1.3 の 1・1.6・9 節の start。決まりは今の start.py のまま）。

入口の入力を 1 つの形にそろえ（lib/entryshape.py）、始めの記録（src/startrec.py の start.json の形）を run directory の根に書き、
pointer で返す。差分も依頼の行も無い・入力の組み合わせが拒まれる時は、落ちずに ok: false と止めの語を返す。後ろの node は
when: で飛び、collect・report・result だけが走る（AI を起こす前に止める）。書いた記録から block に配る値を引いて出力の欄 ports に
並べる（src/deal.py。block は始めの記録を読まない）。拒んだ run の ports は全部の欄を空の値で持つ。

固定材料（fix_fixture。src/fixture.py）を名指した run は、前の run の修正の前の置き場の写しを取り込み（照らしと拒みは
fixture.adopt。拒みは AI の前）、始めの記録は写しの物を今の run の id・入力・版の控え・機能の切り替え・依頼のファイルの道にして書く。
GitHub の読み・差分の測り・入口の形・方針の固め・PR のファイルは写しの物を使うので回さない。返りの from_fixture が真で、fixture が
run directory の根の fixture.CARRIED（修正の段へ運ぶ値）の pointer。配る値は取り込んだ記録から同じ式で引く。

依頼の容器の constraints（前の run が運んだ前提の実測）は src/files.py の CARRIED に置き、配る値 carried がその pointer を持つ。

入力は line の inputs:（環境変数 INPUTS_<名>）。対象のリポジトリは node の作業の置き場（cwd）。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

# lib と src は compute の中で読む（読めなければ fallback の止めの語。docs/design/line.md の 9 節の L-G52）
LIBS = ("answer", "carry", "declared_checks", "entry", "entryshape", "gatemarks", "ghreads", "jsonfile", "policy", "stopby", "suitewrite",
        "tree_run")
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
        "design_talk": os.environ.get("INPUTS_DESIGN_TALK", ""),
        "thickness": os.environ.get("INPUTS_THICKNESS", ""),
        "features_off": os.environ.get("INPUTS_FEATURES_OFF", ""),
        "features_on": os.environ.get("INPUTS_FEATURES_ON", ""),
        "policy_md": os.environ.get("INPUTS_POLICY_MD", ""),
        "fix_fixture": os.environ.get("INPUTS_FIX_FIXTURE", ""),
        "lang": os.environ.get("INPUTS_LANG", ""),
        "deliver": os.environ.get("INPUTS_DELIVER", ""),
        "spec_table": os.environ.get("INPUTS_SPEC_TABLE", ""),
    }


def words(raw: dict, repo: Path) -> dict:
    """入力の語と名指したファイルを確かめる。受けない組み合わせ・無いファイルは Refused"""
    spec = raw["spec"].strip()
    if spec not in SPEC_WORDS:
        raise Refused(f"spec={raw['spec']!r} は知らない値（空か {SPEC_ON}）")
    try:
        gate = gates.check(raw["final_gate"], raw["unattended"], spec=bool(spec))
        off, on = entry.features_off(raw["features_off"]), entry.features_on(raw["features_on"])
        entry.deliver_word(raw["deliver"])
    except (gates.Refused, entry.InputRefused) as error:
        raise Refused(str(error)) from None
    both = sorted(set(off) & set(on))
    if both:
        raise Refused(f"features_on と features_off の両方に {', '.join(both)} を名指した（片方だけ）")
    design_talk = raw["design_talk"].strip()
    if design_talk not in ("", gatemarks.DESIGN_ONLY):
        raise Refused(f"design_talk={raw['design_talk']!r} は知らない値（空か {gatemarks.DESIGN_ONLY}）")
    thickness = raw["thickness"].strip()
    words_ok = ("", AUTO, *tiers.HEADS)
    if thickness not in words_ok:
        raise Refused(f"thickness={raw['thickness']!r} は知らない値（{' / '.join(t for t in words_ok if t)}）")
    clash = sorted(set(off) & set(tiers.tier_adds(tiers.named(thickness))))
    if clash:
        raise Refused(f"thickness={thickness} が足す機能 {', '.join(clash)} を features_off で切った（段を変えるか、切りを外す）")
    fix_fixture = fixture_dir(raw["fix_fixture"], repo)
    table = spec_table(raw, repo, fix_fixture)
    if fix_fixture and spec:
        raise Refused("仕様の段（spec=on）は固定材料（fix_fixture）と組めない（固定材料は判定と修正案が済んだ所の写しで、仕様の段は"
                      "判定の中に在る）")
    return {**gate, "spec": spec, "design_talk": design_talk, "thickness": thickness, "features_off": off, "features_on": on,
            "policy_md": policy_md(raw["policy_md"], repo), "fix_fixture": fix_fixture, "spec_table": table}


SPEC_CLASH = ("request", "base", "pr", "spec")   # 仕様駆動の道の表と組めない入力（表が依頼と差分の代わり。仕様の段は判定の中に在る）


def spec_table(raw: dict, repo: Path, fix_fixture: str) -> str:
    """仕様駆動の道の表の絶対パス（名指しが無ければ空。docs/design/spec-driven.md の 6.2 の変える node の 1）。相対なら対象の根から。
    在るファイルでない・組めない入力（依頼・差分の根・PR・仕様の段・固定材料）と一緒なら Refused。表の中身（YAML）は読まない
    （PyYAML を持たない。中身の確かめは block works-factory-spec-driven の形 entry）。周の鎖の入口は spec_table を拒むので、鎖の子では使えない"""
    rel = raw.get("spec_table", "").strip()
    if not rel:
        return ""
    clash = [name for name in SPEC_CLASH if raw[name].strip()] + (["fix_fixture"] if fix_fixture else [])
    if clash:
        raise Refused(f"仕様駆動の道の表（spec_table）は {'・'.join(clash)} と組めない（表が依頼の代わりで、差分の根は HEAD）")
    path = Path(rel) if Path(rel).is_absolute() else repo / rel
    if not path.is_file():
        raise Refused(f"名指した仕様駆動の道の表 {rel} が無い（spec_table。表は対象の根からの相対か絶対パスで名指す）")
    return str(path.resolve())


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
    tdd_suite を省いた run で修正前のテストの後に TDD の実行器を用意し、照らしが通れば TDD の輪を回す事（元 use.sh 1086-1089 行）"""
    notes = []
    if not raw["test_cmd"].strip() and "fallback" in declared_checks.checks_plan(repo):
        notes.append("修正前のテスト: 宣言も test_cmd も無い——任せ先の役がリポジトリから走らせ方を探す")
    if not raw["tdd_suite"].strip():
        notes.append(suitewrite.GATE_NOTE)
    return notes


def gate_text(shape: dict, record: dict, run_id: str, notes: list) -> str:
    happened = f"run を始める前で止まった。入口: {startrec.words(shape)}"
    rest = [*fixture.lines(record), *([f"仕様駆動の道: 表 {record['spec_table']}"] if record.get("spec_table") else []),
            depth_words(record["inputs"], record),
            entry.features_part(record["features_off"], record["features_on"], adds(record),
                                tiers.tier_auto(tiers.named(record.get("thickness")))), gates.head_words(record),
            entry.deliver_line(entry.deliver_word(record["inputs"]["deliver"])), *notes]
    lines = gatemarks.head3(happened, "この入力で run を始めるか、止めるか（打つ行は末尾の答え方）", gatemarks.NO_PUSH)
    lines += ["", *[f"- {x}" for x in rest if x], "", "答え方:",
              f"- 始める: {answer.line(run_id, 'continue', '<一言>')}",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return "\n".join(lines) + "\n"


def write(artifacts: Path, doc) -> dict:
    """始めの記録を run directory の根の startrec の置き場に書き、pointer を返す（起動の殻と包みと bin/ の読み手と同じ所。L-E24）"""
    startrec.write(artifacts, doc)
    return ports.pointer(startrec.path(artifacts))


def adds(checked: dict) -> tuple:
    return tiers.tier_adds(tiers.named(checked.get("thickness")))


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
    prior = ports.pointer(artifacts / carry.PRIOR_IN_FILE) if (artifacts / carry.PRIOR_IN_FILE).is_file() else None
    return begun(doc, startrec.shape(doc), prior, raw, repo, artifacts, run_id, ports.pointer(artifacts / fixture.CARRIED))


def begun(record: dict, shape: dict, prior, raw: dict, repo: Path, artifacts: Path, run_id: str, carried=None) -> dict:
    """始めの記録 record を書き、start の通った返りを組む。carried は固定材料の run の運ぶ値の pointer（ほかの run は None）"""
    unattended = gates.unattended_of(record)
    pointer = write(artifacts, record)
    return {"ok": True, "stop_reason": "", "reason": "", "record": pointer, "prior_failures": prior,
            "ask": not unattended, "gate_text": gate_text(shape, record, run_id, test_notes(raw, repo)),
            "unattended": unattended, "design_talk": record["design_talk"] == gatemarks.DESIGN_ONLY,
            "final_gate": record[gates.FINAL_KEY], "from_fixture": carried is not None, "fixture": carried,
            "from_spec": bool(record.get("spec_table")), "ports": deal.ports_of(record, artifacts)}


def place_carried(artifacts: Path, rows: list) -> None:
    """依頼の容器の constraints（前の run が運んだ前提の実測）を CARRIED に置く（行が無ければ置かない。配る値 carried は "[]"）"""
    if rows:
        jsonfile.write(artifacts / files.CARRIED, list(rows), parents=True)


def start(raw: dict, repo: Path, artifacts: Path, run_id: str) -> dict:
    record = {"run_id": run_id, "inputs": raw, "versions": version_record(ports.lib_root().parent, raw, run_id)}
    try:
        checked = words(raw, repo)
        asked = request(raw, repo)
        if checked["fix_fixture"]:
            return from_fixture(raw, checked, asked, repo, artifacts, run_id, record["versions"])
        reads = entryshape.github_reads(artifacts, repo, raw)
        if reads is not None:
            ghreads.place(artifacts, reads)
        change = entryshape.change_base(raw, repo, reads)
        if not checked["spec_table"]:   # 仕様駆動の道の表は依頼の代わりの入口（依頼の行も差分も要らない）
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
                "unattended": False, "design_talk": False, "final_gate": "", "from_fixture": False, "fixture": None,
                "from_spec": False, "ports": deal.empty()}
    parts = asked["parts"]
    record.update({
        "input": shape, "base_rev": shape["head_rev"], "review_rev": shape["head_rev"], "request_file": asked["request_file"],
        "test_cmd": raw["test_cmd"], "tdd_suite": raw["tdd_suite"],
        gates.FINAL_KEY: checked[gates.FINAL_KEY], gates.UNATTENDED_KEY: checked[gates.UNATTENDED_KEY],
        "design_talk": checked["design_talk"], "thickness": checked["thickness"], "spec": checked["spec"],
        "policy_md": checked["policy_md"], "policy": policy.freeze(artifacts, repo, checked["policy_md"]), "lang": raw["lang"],
        **features(checked),
        "answers": parts[carry.ANSWERS], "request_text": entryshape.request_text(inp),
        "pr_file": entryshape.write_pr_file(artifacts, inp),
        **({"spec_table": checked["spec_table"]} if checked["spec_table"] else {}),
    })
    place_carried(artifacts, parts[carry.CONSTRAINTS])
    prior = None
    if parts[carry.PRIOR]:
        carry.place_prior(artifacts, parts[carry.PRIOR])
        prior = ports.pointer(artifacts / carry.PRIOR_IN_FILE)
    return begun(record, shape, prior, raw, repo, artifacts, run_id)


def load() -> None:
    """lib と src のモジュールを読み、この script の名に置く（読めない訳は ports.run が fallback に畳む）"""
    import importlib
    for name in LIBS:
        globals()[name] = importlib.import_module(name)
    from src import deal, files, fixture, gates, startrec, tiers, versions
    globals().update(deal=deal, files=files, fixture=fixture, gates=gates, startrec=startrec, tiers=tiers, versions=versions)


def compute() -> dict:
    load()
    artifacts = ports.place()
    return start(raw_inputs(), Path.cwd(), artifacts, os.environ["WORKFLOW_ID"])


def fallback(reason: str) -> dict:
    from src import deal, guard

    return {"ok": False, "stop_reason": guard.LINE_SCRIPT, "reason": reason, "record": None, "prior_failures": None,
            "ask": False, "gate_text": "", "unattended": False, "design_talk": False, "final_gate": "", "from_fixture": False,
            "fixture": None, "from_spec": False, "ports": deal.empty()}


if __name__ == "__main__":   # 試験は名で読み、load の後に start を直に呼ぶ
    ports.run(compute, fallback)
