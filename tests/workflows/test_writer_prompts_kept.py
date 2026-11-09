"""書き手の指示の段落の真偽を、場面ごとの代表で照らす（修正の block の writer_slots → 型の block の writer_prep.py）。

`prompt.render` は値の名の欠けを拒むが段落の真偽の誤りは拒まないので、組み立ての直しで rejected・resume・rulings_first などを
誤って偽にすると、観点の段落（前の答えが拒まれた訳・裁定の文・範囲の相談の答え）が黙って指示から落ち、ほかの試験は緑のまま。
型 1 つ（pin）の 4 つの場面（1 回目・却下の後・裁定の後の段・範囲の相談の答えの後の続きの周）を組み、場面で真になるべき段落が真、
偽になるべき段落が偽で、真の段落の字が組み上がった指示に在ることを見る。

2026-11-10 の削り（持ち主の決め `tests-guard-writes`）: 型を割る前と後の 23 の組を控え（段落の真偽・付録 A の行・値）と比べる
移しの照らしから、この代表に縮めた。移しは済み、指示の字の照らしは書き込みも承認も守らない。真偽の代表だけを残した。
"""
import contextlib
import functools
import io
import json
import pathlib
import runpy
import sys
import unittest
from unittest import mock

from tests.blocks import kit
from tests.blocks.fix import support, test_prompts

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "lib", kit.SHARED):
    if str(p) not in sys.path:
        sys.path.append(str(p))

import conflict  # noqa: E402
import prompt  # noqa: E402
import rolekit  # noqa: E402

KEY = test_prompts.KEY
WEAPON = "pin"   # 4 つの場面を全部持ち、下請けを起こす型（tdd は裁定の後の段を持たない）
# 場面 → その場面で真・偽になる段落（代表）。値は prompt.emit に渡った when
EXPECTED = {
    "first": {"rules": True, "rejected": False, "rulings_first": False, "ruled_reply": False, "resume": False},
    "rejected": {"rules": True, "rejected": True, "rulings_first": False, "resume": False},
    "ruled": {"rules": True, "rejected": False, "rulings_first": True, "ruled_reply": True, "resume": False},
    "resumed": {"rules": False, "rejected": False, "resume": True},
}


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
    """場面 kind・型 weapon の書き手の指示を組み、prompt.emit の引数と返りを受けて返す {when, values, prompt, node}。修正の block の
    writer_slots → 型の block の writer_prep.py（writerblock.prep）で組む"""
    run, pass_ = scene(case, kind)
    seen = {}
    real = prompt.emit

    def wrapped(node, values, when, n):
        out = real(node, values, when, n)
        seen.update(node=node, values=dict(values), when=dict(when), prompt=out["prompt"])
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
            record, summary = board.loop_files(place)
            summary = summary if weapon == "tdd" else ""
            values = board.fix_values(place, owed, record=record, summary=summary, answer_node=rules.answer_node("first"))
            extra = {"green": tdd.green_units(summary)}
        else:
            owed = board.ruled_owed(place)
            record, _ = board.ruled_states(place)
            values = board.fix_values(place, owed, answer_node=rules.answer_node("ruled"))
            saved = str(place / "fix-reply.json")
            extra = {"saved_reply": saved}
        call = dict(owed=owed, items=functools.partial(board.place_items, place), sources=board.brief_sources(place),
                    frozen=facts.frozen_tests(place, record, pass_), shared=ports.shared_cache(), **extra)
        slots, _ = prompts.writer_slots(place, repo, pass_, weapon, values, **call)
        block_prep(run, pass_, weapon, slots, writers)
    return seen


class WriterParagraphsCase(unittest.TestCase):
    def test_each_scene_turns_on_its_paragraphs(self):
        """場面で真になるべき段落が真、偽になるべき段落が偽。真の段落の値（却下の訳・裁定の文のファイル）が組み上がった指示に在る"""
        for kind, want in EXPECTED.items():
            with self.subTest(scene=kind):
                got = compose(kind, WEAPON, self)
                self.assertEqual({k: got["when"].get(k) for k in want}, want, "段落の真偽が場面と違う")
                if kind == "rejected":
                    self.assertIn("run the tests again", got["prompt"])
                if kind == "ruled":
                    self.assertIn(got["values"]["rulings_file"], got["prompt"])


if __name__ == "__main__":
    unittest.main()
