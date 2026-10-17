"""関所の答えの行（lib/answer.py）。起動の殻が置く頭で打てる行になる事と、殻の外の穴の字（FAST）"""
import ast
import json
import pathlib
import shlex
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import answer  # noqa: E402

SHELL = "/opt/works factory/bin/works-factory"
TARGET = "/home/me/my repo"


class HeadCase(unittest.TestCase):
    def test_without_env_is_the_hole(self):
        self.assertEqual(answer.head(env={}), answer.HOLE)

    def test_env_head_is_stripped(self):
        self.assertEqual(answer.head(env={answer.ENV: "  sh x  "}), "sh x")


class LineCase(unittest.TestCase):
    def test_line(self):
        self.assertEqual(answer.line("r", "continue", "n", env={answer.ENV: "H"}), 'H r continue "n"')

    def test_nothing_follows_the_note(self):
        """実行基盤の respond は一言の後ろを一言に繋ぐので、答えた者などを末尾に足さない（利用者の env に昔の名が在っても）"""
        self.assertEqual(answer.line("r", "stop", "n", env={answer.ENV: "H", "WORKS_ANSWER_WHO": "w"}), 'H r stop "n"')

    def test_unknown_verb_raises(self):
        with self.assertRaises(ValueError):
            answer.line("r", "maybe", "n", env={answer.ENV: "H"})

    def test_shell_head_makes_a_typeable_respond(self):
        env = {answer.ENV: shlex.join([SHELL, "workflow", "respond", "--cwd", TARGET])}
        self.assertEqual(shlex.split(answer.line("run-1", "continue", "x", env=env)),
                         [SHELL, "workflow", "respond", "--cwd", TARGET, "run-1", "continue", "x"])

    def test_outside_the_shell_the_head_is_the_hole(self):
        self.assertEqual(answer.head(env={}), answer.HOLE)
        self.assertTrue(answer.line("run-1", "stop", "x", env={}).startswith(answer.HOLE + " "))
        self.assertIn("bin/works-factory workflow respond --cwd", answer.HOLE)
        self.assertNotIn("use.sh", answer.HOLE)


def _named(node):
    """名で引いた物の名（VERBS・answer.VERBS・getattr(answer, "VERBS") の VERBS）。名で引いていなければ None"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "getattr" and len(node.args) >= 2 \
            and isinstance(node.args[1], ast.Constant):
        return node.args[1].value
    return None


def word_lists(source: str, name: str, words: set) -> list[str]:
    """words の語を全部並べた並び（tuple・list・set・呼び出しの引数・dict の鍵）の在りか（<name>:<行>）。並びの中の語は字のままの物も、
    answer の名（VERBS[0]・REJECT。answer. も getattr も）で引いた物も、そのファイルで語の字を代入した名で引いた物も読む"""
    tree = ast.parse(source)
    local = {t.id: n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
             and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
             for t in n.targets if isinstance(t, ast.Name)}

    def word(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            seq, at = getattr(answer, str(_named(node.value)), None), node.slice.value
            return seq[at] if isinstance(seq, tuple) and isinstance(at, int) and at < len(seq) else None
        named = _named(node) if node is not None else None
        return (local.get(named) or getattr(answer, named, None)) if isinstance(named, str) else None

    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            elts = node.elts
        elif isinstance(node, ast.Call):
            elts = node.args
        elif isinstance(node, ast.Dict):
            elts = node.keys
        else:
            continue
        if words <= {w for w in map(word, elts) if isinstance(w, str)}:
            found.add(node.lineno)
    return [f"{name}:{line}" for line in sorted(found)]


def lib_word_lists(words: set) -> list[str]:
    return [hit for f in sorted(LIB.rglob("*.py")) if "tests" not in f.relative_to(LIB).parts
            for hit in word_lists(f.read_text(encoding="utf-8"), str(f.relative_to(LIB)), words)]


class PushedCase(unittest.TestCase):
    """#552: 無人の run が推しで進んだ答えは、関所が開かなくても答えとして記録し、欄 PUSHED で人の答えと読み分ける"""
    PUSHED = {"decision": "continue", "text": "0 を返す形で通す",
              answer.PUSHED: [{"item": "修正案 1 が狭める能力: x", "answer": "continue", "note": "0 を返す形で通す", "why": "呼び手が前提"}]}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = pathlib.Path(tmp.name)

    def test_skipped_gate_with_a_push_records_the_push_as_the_answer(self):
        got = answer.taken(None, go=True, stop_reason="", place="gate-before-fix", folder=self.folder, asked=["修正案 1 …"],
                           pushed=self.PUSHED)
        want = {"decision": "continue", "text": "0 を返す形で通す", "asked": ["修正案 1 …"], answer.PUSHED: self.PUSHED[answer.PUSHED]}
        self.assertEqual(got, {"go": True, "answer": want, "stop_reason": ""})
        self.assertEqual(json.loads((self.folder / answer.ANSWERS / "gate-before-fix.json").read_text(encoding="utf-8")), want)

    def test_human_answer_wins_and_carries_no_push(self):
        got = answer.taken({"decision": "stop", "text": "やめる"}, go=True, stop_reason="", place="gate-before-fix", folder=self.folder,
                           pushed=self.PUSHED)
        self.assertNotIn(answer.PUSHED, got["answer"])
        self.assertEqual(got["stop_reason"], "human:gate-before-fix")

    def test_final_note_comes_from_the_caller_not_the_place(self):
        """止める答えの一言が空の時、最後の承認の既定の一言は呼び手が渡す印 final が真の時だけ（place の字では選ばない）"""
        stop = {"decision": "stop", "text": " "}
        for place, final, want in (("gate-final", False, answer.STOP_NOTE), ("gate-elsewhere", True, answer.FINAL_STOP_NOTE),
                                   ("gate-final", True, answer.FINAL_STOP_NOTE), ("gate-start", False, answer.STOP_NOTE)):
            with self.subTest(place=place, final=final):
                got = answer.taken(dict(stop), go=True, stop_reason="", place=place, folder=self.folder, final=final)
                self.assertEqual(got["answer"]["text"], want)
                kept = json.loads((self.folder / answer.ANSWERS / f"{place}.json").read_text(encoding="utf-8"))
                self.assertEqual(kept["text"], want)
        self.assertEqual(answer.taken(dict(stop), go=True, stop_reason="", place="gate-final", folder=self.folder)["answer"]["text"],
                         answer.STOP_NOTE)

    def test_no_push_keeps_the_skipped_answer(self):
        self.assertEqual(answer.taken(None, go=False, stop_reason="works:needs-human", place="gate-before-fix", folder=self.folder),
                         {"go": False, "answer": None, "stop_reason": "works:needs-human"})
        self.assertFalse((self.folder / answer.ANSWERS).exists())


class GoWordsOwner(unittest.TestCase):
    """関所を通す語の並びを宣言するのは answer.GO_WORDS の 1 か所（#392。ほかは引く。写すと語を足した時に片方だけ変わる）"""
    WORDS = set(answer.GO_WORDS)

    def test_declared_once_in_lib(self):
        found = lib_word_lists(self.WORDS)
        self.assertEqual([hit.partition(":")[0] for hit in found], ["answer.py"], found)

    def test_a_second_copy_is_red(self):
        """宣言の形（tuple・list・set・frozenset・3 つ組・dict の鍵）と語の引き方（字・answer の名・getattr・語を代入した名）を問わない"""
        copies = ['PASS = ("continue", "approve")', "GATE_GO = ('approve', VERBS[0])", 'PASS = ["continue", "approve"]',
                  'PASS = {"approve", answer.VERBS[0]}', 'PASS = frozenset(["approve", "continue"])',
                  'PASS = frozenset({"approve", "continue"})', 'PASS = ("approve", "continue", "approved")',
                  'PASS = {"approve": True, "continue": True}', 'PASS = ("approve", getattr(answer, "VERBS")[0])',
                  'GO = "continue"\nPASS = ("approve", GO)', 'PASS = set_of("approve", "continue")']
        for copy in copies:
            with self.subTest(copy=copy):
                self.assertEqual(len(word_lists(copy, "x.py", self.WORDS)), 1)
        for other in ('ASKED = ("approve", "stop")', 'line(run_id, "continue", note)', "VERBS = ('continue', 'stop')"):
            with self.subTest(other=other):
                self.assertEqual(word_lists(other, "x.py", self.WORDS), [])


class StopWordsOwner(unittest.TestCase):
    """関所を止める語の並びを宣言するのは answer.STOP_WORDS の 1 か所（通す語の GoWordsOwner と同じ訳）"""
    WORDS = set(answer.STOP_WORDS)

    def test_declared_once_in_lib(self):
        found = lib_word_lists(self.WORDS)
        self.assertEqual([hit.partition(":")[0] for hit in found], ["answer.py"], found)

    def test_a_second_copy_is_red(self):
        copies = ['STOPS = (VERBS[1], "reject")', "GATE_STOP = ('stop', 'reject')", "STOPS = (VERBS[1], REJECT)",
                  'STOPS = ("reject", "stop")', "STOPS = (answer.VERBS[1], answer.REJECT)", 'STOPS = ["stop", REJECT]',
                  'STOPS = {"stop", "reject"}', 'STOPS = frozenset((VERBS[1], "reject"))', 'STOPS = ("stop", "reject", "cancel")']
        for copy in copies:
            with self.subTest(copy=copy):
                self.assertEqual(len(word_lists(copy, "x.py", self.WORDS)), 1)


if __name__ == "__main__":
    unittest.main()
