"""書き手の指示の段落の真偽・組み上がった字・付録 A の行の在る無し・値を、修正の block を型ごとの block に割る前と後で比べる
（docs/plans/2026-10-24-fix-weapons.md の 11.6 の D1 の縛る試験の 8）。

縛る事: 書き手の 6 つの型（tdd・pin・tidy・static・variant・remove）× 4 つの場面（1 回目・却下の後・裁定の後の段・範囲の相談の答えの
後の続きの周。裁定の後の段に tdd は無い）の 23 の組を組み、組ごとに次の 4 つが控え writer-prompts-before.json と等しいことを見る。
- (a) 段落の真偽: `prompt.emit` に渡った when の全部。`prompt.render` は名の欠けを拒むが真偽の誤りは拒まないので、割った組み立てが
  rejected・resume・where_writer などを誤って偽にして観点の文が落ちても、ほかの試験は緑のまま。ここが赤にする
- (b) 組み上がった指示の字（`emit` の返りの prompt）。置き字（下）に替えた後の字
- (c) 付録 A の行（下請けの行 G と機械の行を除く。tests/workflows/test_weapon_assets.py の ROWS）のうち、組み上がった字に在る行の id。値を差し込み口の
  字（`{名}`）に替え（ただし unattended は本物の字）、`prompt.render` でもう 1 度組み、test_weapon_assets.py の flat と同じ照らし方（`in`）で見る。
  md だけの直しで文が段落の間を動いて、ある場面から観点が消える道を赤にする
- (d) 値（`emit` に渡った values に置き字を当てた物。字が md から来る unattended は鍵だけ残して字を `{MD}`）。writer_slots 相当の値の誤り
  （却下の文や裁定の値が空になる）を赤にする

置き字（場で変わるパスだけ。この順）: first_prompt の値 → `{FIRST_PROMPT}`、指示を組んだ place（型の block の place。下請けのファイルの名指しが
持つ。variant だけ。控えは下請けのファイルが修正の block の place に在った時の字なので、場所の違いを `{PLACE}` に揃える）→ `{PLACE}`、試験を回す python の実行ファイル（事前の確かめのコマンド
check_cmd が持つ。uv run --isolated の度に一時のパスが変わる）→ `{PYTHON}`、修正の block の place → `{PLACE}`、対象のリポジトリの根 →
`{REPO}`、対象のリポジトリの種の commit（commit の時刻で hash が run ごとに変わる。下請けの差分を取るコマンドが持つ）→ `{BASE}`、工場のリポジトリの根 → `{ROOT}`。これで消えない違いが出たら置き字を足して通さず、指示が変わった印として調べる。

組み立ての助けは `compose` の 1 つだけ。`prompt.emit` を包んで引数と返りを受ける。割る前は修正の block の `prompts.writer` を呼んだ。
割った後は、6 つの型（tdd・pin・tidy・static・variant・remove）とも、修正の block の `prompts.writer_slots` を同じ引数で呼び、返りの slots と注文を
`writers.hand_over` で pointer にして、その型の block の `scripts/writer_prep.py`（`writerblock.prep(render)`）を、`ports.caller_block()` がその block
を返すように script のファイルのまま起こして組む（variant も D2 で型の block になり、割る前の `prompts.writer` の道は無い）。
割る commit と variant を block にした commit は `compose` だけを替え、場面の作り（`scene`）と控えは替えていない。node の名は控えない（裁定の後の段の node は、割る前は `<型>-ruled`、割った後は型の block の中の `<型>` で、指示の中身ではない）。控えは最初の commit の後に書き直さない
（`git log --format=%h -- tests/workflows/writer-prompts-before.json` が 1 つだけ）。

(b) の字の比べは D2 の最後の commit で外し、(a)・(c)・(d) を残す（指示の文だけを変える依頼を md 1 本で閉じるため）。

控えを書く口: `uv run --isolated python3 -m tests.workflows.test_writer_prompts_kept --write`（通常の試験の走りでは書かない）。
"""
import contextlib
import functools
import io
import json
import pathlib
import re
import runpy
import sys
import unittest
from unittest import mock

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.fix import support, test_prompts
from tests.workflows import test_weapon_assets as test_assets

ROOT = pathlib.Path(__file__).resolve().parents[2]
BEFORE = pathlib.Path(__file__).resolve().parent / "writer-prompts-before.json"
for p in (ROOT / "lib", kit.SHARED):
    if str(p) not in sys.path:
        sys.path.append(str(p))

import conflict  # noqa: E402
import prompt  # noqa: E402
import rolekit  # noqa: E402
import seat  # noqa: E402

KEY = test_prompts.KEY
WEAPONS = ("tdd", "pin", "tidy", "static", "variant", "remove")
SCENES = ("first", "rejected", "ruled", "resumed")
COMBOS = [(scene, weapon) for scene in SCENES for weapon in WEAPONS if not (scene == "ruled" and weapon == "tdd")]
FROM_MD = ("unattended",)   # 値の字が md から来る物（seat.overlay_body が lib/borrow/unattended.md を読む）
APPENDIX = [r for r in test_assets.ROWS if r["from"] in ("writer", "unattended")]   # 下請けの行 G（g1）と機械の行を除く


def scene(case, kind: str):
    """場面 kind の run を作る（作った run と段 pass_ を返す）。型は選ばない（組み立ての口に直に渡す）"""
    run = test_prompts.seeded(case)
    if kind == "ruled":
        run.script("intake", mode="whole", judgment=test_prompts.JUDGMENT, parallel="false")
        run.script("prep")
        ids = conflict.park(run.artifacts, [{"unit_key": KEY, "between": ["stats.py:2", "stats.py:1"],
                                             "why_both_cannot_hold": "期待と実装が両立しない", "which_is_right": "code",
                                             "kind": "not_red"}], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(run.artifacts, {ids[0]: {"decision": "fix_code_as", "text": "分母が 0 の時は 0 を返すように直す",
                                                        "limits": []}}, by="role:rule")
        return run, "ruled"
    run.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}),
               judgment=test_prompts.JUDGMENT, plan=test_prompts.PLAN, fix_plan=test_prompts.FIX_PLAN,
               tdd_suite=str(test_prompts.RUNNER))
    run.script("group_start")
    if kind == "resumed":   # 範囲の相談の答えの後の周（test_consult_resume_round_has_no_rules の道具）
        run.script("fix_prep")
        reply = {**test_prompts.REPLY, "consult": [{"item": 1, "paths": ["README.md"], "tests": [], "why": "直しに伴う記録を README に足す要がある",
                                                    "tried": ["stats.py の分母を直した"], "blocked": "直しは済んだが記録の置き場が範囲の外",
                                                    "evidence": [{"path": "stats.py", "line": 4}]}]}
        asked = run.script("consult_check", reply_variant=support.reply_json(reply), **{"pass": "first"})
        assert asked["go"], asked
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["README.md"], "tests": [], "spec": "",
                               "reason": "直しの記録は範囲に入れてよい"}]}
        run.script("consult_accept", answer=json.dumps(answer), **{"pass": "first"})
    return run, "first"


def put_rejection(run, pass_: str, weapon: str, writers) -> None:
    """同じ型の受け付けの却下の控え（受け付けが積む rejects-<名>.json の行。rolekit.rejected が読む）を置く。at は組ごとに同じ字にする"""
    rows = [{"at": "2026-01-01T00:00:00+00:00", "reason": r} for r in ("the reply left a unit without a change", "run the tests again")]
    rolekit.rejects_path(run.artifacts, writers.accept_name(pass_, weapon)).write_text(json.dumps(rows), encoding="utf-8")


def block_prep(run, pass_: str, weapon: str, slots: dict, writers) -> None:
    """型 weapon の書き手の block の writer_prep.py を、script のファイルのまま（ports.caller_block がその block を返す）この過程で起こす。
    入力 order・slots は fix-prep が返す形（注文 orders/<型>.json と slots のファイルを指す pointer）にして env に置く。place は
    <修正の block の place>/<include の id>（ARCHON_NODE_EXECUTION の path が include の道を作る）"""
    block = kit.BLOCKS / f"weapon-{writers.block_of(weapon)}"
    doc = kit.fixture(block.name, "standalone")["fixture"]["inputs"]["order"]   # 筋書きの注文の字（形に合う。weapon は表の ORDER_WEAPON）
    orders = run.artifacts / "orders"
    orders.mkdir(exist_ok=True)
    (orders / f"{weapon}.json").write_text(doc, encoding="utf-8")
    handed = writers.hand_over(run.artifacts, pass_, weapon, slots)
    include = f"{writers.node(pass_, weapon)}__{writers.block_of(weapon)}-prep"
    env = {**run.environ(include, order=json.dumps(handed["order"]), slots=json.dumps(handed["slots"]))}
    for name in [n for n in sys.modules if n == "src" or n.startswith("src.")]:
        del sys.modules[name]   # block ごとに src の名が重なる（kit.load と同じ）
    keep = list(sys.path)
    try:
        with mock.patch.dict("os.environ", env), contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(block / "scripts" / "writer_prep.py"), run_name="__main__")
    finally:
        sys.path[:] = keep
        for name in [n for n in sys.modules if n == "src" or n.startswith("src.")]:
            del sys.modules[name]


def compose(kind: str, weapon: str, case) -> dict:
    """場面 kind・型 weapon の書き手の指示を組み、prompt.emit の引数と返りを受けて返す {when, prompt, values, node}。修正の block の
    writer_slots → 型の block の writer_prep.py（writerblock.prep）で組む。割る commit と variant を block にした commit はこの関数だけを替えた"""
    run, pass_ = scene(case, kind)
    seen = {}
    real = prompt.emit

    def wrapped(node, values, when, n):
        out = real(node, values, when, n)
        slots = {k: v if k in FROM_MD else "{" + k + "}" for k, v in values.items()}
        again = prompt.render(node, slots, when)["prompt"]
        seen.update(node=node, values=dict(values), when=dict(when), prompt=out["prompt"], slotted=again, emit_place=str(ports.place()))
        return out

    with run.env(), mock.patch.object(prompt, "emit", wraps=wrapped):
        prompts = kit.load("fix", "prompts")
        board, facts, tdd, writers, rules = (kit.load("fix", m) for m in ("board", "facts", "tdd", "writers", "rules"))
        import ports
        place, repo = run.artifacts, run.repo
        if kind == "rejected":
            put_rejection(run, pass_, weapon, writers)
        saved = ""
        if pass_ == "first":
            owed = board.group_owed(place, [KEY])
            state, summary = board.loop_files(place)
            summary = summary if weapon == "tdd" else ""
            values = board.fix_values(place, owed, state=state, summary=summary, answer_node=rules.answer_node("first"))
            extra = {"green": tdd.green_units(summary)}
        else:
            owed = board.ruled_owed(place)
            state, _ = board.ruled_states(place)
            values = board.fix_values(place, owed, answer_node=rules.answer_node("ruled"))
            saved = str(place / "fix-reply.json")
            extra = {"saved_reply": saved}
        call = dict(owed=owed, items=functools.partial(board.place_items, place), sources=board.brief_sources(place),
                    frozen=facts.frozen_tests(place, state, pass_), shared=ports.shared_cache(), **extra)
        slots, _ = prompts.writer_slots(place, repo, pass_, weapon, values, **call)
        block_prep(run, pass_, weapon, slots, writers)
    seen["place"], seen["repo"], seen["first_prompt"] = str(place), str(repo), seen["values"].get("first_prompt", "")
    seen["base"] = git(repo, "rev-parse", "HEAD")
    return seen


def paths(text, got: dict):
    """置き字を当てる（この順）。macOS の /var と /private/var の両方の姿を替える"""
    def forms(path):
        found = {str(path), str(pathlib.Path(path).resolve())}
        return sorted(found, key=len, reverse=True)
    for old, new in ((got["first_prompt"], "{FIRST_PROMPT}"), (got["emit_place"], "{PLACE}"), (sys.executable, "{PYTHON}"), (got["place"], "{PLACE}"), (got["repo"], "{REPO}"), (got["base"], "{BASE}"), (str(ROOT), "{ROOT}")):
        if old:
            for form in forms(old):
                text = text.replace(form, new)
    return text


def record(kind: str, weapon: str, case) -> dict:
    got = compose(kind, weapon, case)
    values = {k: "{MD}" if k in FROM_MD else paths(v, got) for k, v in got["values"].items()}
    text = test_assets.flat(got["slotted"])
    return {"when": got["when"], "prompt": paths(got["prompt"], got), "values": values,
            "appendix": [r["id"] for r in APPENDIX if all(test_assets.flat(line) in text for line in r["text"])]}


def all_records(case) -> dict:
    return {f"{kind}/{weapon}": record(kind, weapon, case) for kind, weapon in COMBOS}


class WriterPromptsKeptCase(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.before = json.loads(BEFORE.read_text(encoding="utf-8"))

    def test_the_combos_are_the_23_of_the_scenes_and_the_weapons(self):
        self.assertEqual(len(COMBOS), 23)
        self.assertEqual(sorted(self.before), sorted(f"{k}/{w}" for k, w in COMBOS))

    def test_every_combo_equals_the_record(self):
        for kind, weapon in COMBOS:
            with self.subTest(scene=kind, weapon=weapon):
                got, want = record(kind, weapon, self), self.before[f"{kind}/{weapon}"]
                self.assertEqual(got["when"], want["when"], "(a) 段落の真偽が違う")
                self.assertEqual(got["appendix"], want["appendix"], "(c) 付録 A の行の在る無しが違う")
                self.assertEqual(got["values"], want["values"], "(d) 値が違う")
                self.assertEqual(got["prompt"], want["prompt"], "(b) 組み上がった指示の字が違う")

    def test_the_record_is_not_a_dummy(self):
        """控えが空・全部同じでない（段落の真偽・付録 A の行・字が組ごとに違う）"""
        for part in ("when", "appendix", "prompt"):
            self.assertGreater(len({json.dumps(r[part], sort_keys=True) for r in self.before.values()}), 5, part)


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        class _Case(unittest.TestCase):
            def runTest(self):
                pass
        case = _Case()
        BEFORE.write_text(json.dumps(all_records(case), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {BEFORE}")
    else:
        unittest.main()
