"""修正役の指示の観点と返答の形（持ち主のアセット）が、型ごとの書き手に移しても減らないことの照らし（docs/plans/2026-10-24-fix-weapons.md の
付録 A・4.4 の作る物 9。docs/plans/2026-10-25-fix-weapons-stage1-b.md）。

- 表 appendix-a.json: 付録 A の行（番号・行き先・出どころ）と、その行の英語の文（移す前の指示の行の字。差し込み口は {名} のまま）。番号と
  行き先と出どころ（節の見出しが名指す置き場。機械の行 machine は A.8 の行だけ）は付録 A の本文から機械で読み直して照らし（表と付録 A が
  食い違えば赤。from を machine に替えて照らしを飛ばすこともできない。機械の行が引く置き場は .py のファイルに限るので、
  md の行を A.8 へ動かす・見出しを Python に替えて machine にすることもできない）、行き先ごとの数（共通 156・variant 29・変える 4・
  消す 11。範囲の番号 F17〜F20 などは広げて数える）も照らす。
- 付録 A は作業ツリーでなく固定した版（PLAN_PIN。計画のファイルの git の blob）から読み、作業ツリーの付録 A がその版と同じことも照らす。
  計画の側で行を動かす・見出しや引きを替えるだけでは照らしを動かせず、付録 A を直す PR は PLAN_PIN を替えるので試験の差分に出る。
  blob にしたのは、squash で main に入ると PR の commit が main の履歴から消えても、同じ字の blob は残るため。設計の枝
  work/design-seat が付録 A を直す時は、直した commit で `git rev-parse HEAD:docs/plans/2026-10-24-fix-weapons.md` の値を
  PLAN_PIN に書く（直した表 appendix-a.json と一緒に）。引けなければ見送らずに赤。
- 表の文の出どころ: 表の各行の文が、付録 A の本文がその行に引く置き場の行（`:4`・`brief.md:2-4` など）の、付録 A の行番号の版
  （PIN。#865 の後で #866 の前の main）の字に在る。表と指示の md を一緒に書き換えても、git の履歴の字は変わらないので赤になる
  （CI は fetch-depth: 0 で全履歴を取る。履歴を引けなければ見送らずに赤）。移す時に字を替えた行は REWORDED に、替えた後と前の字の対で置く。
  削る向きも照らす: 機械の行（from が machine）でない行の文は空にできず、付録 A が引く置き場の行ごとに、そこを引く行の文を全部
  抜いた残り（段落の印 <!-- --> と差し込み口 {名} を除き、空白をそろえる）が LEFT に書いた字と等しい（既定は空）。表と md から
  文の尻・真ん中を一緒に削る、行を一緒に消すと、残りが増えて赤になる。行き先が型を絞る行の置き場の行に、全部の書き手に残す字が
  在る時は、その字を表の行の rest に置く（F135 の行の返答の欄 fix_closure の残り。付録 A は残りを移すと決めていない）。rest は
  残りの照らしで覆う側に入り、組み上がった全部の書き手の指示に在ることを照らす（消す行・機械の行には置けない）。
- 組み上がった指示: 型ごとの書き手の node の md（prompts/<node>.md）を、差し込みを解き、型が選ぶ段落を src/prompts.writer_paragraphs で
  選び、ほかの段落（却下・裁定・相談・続きの周など）を全部入れて組んだ字。差し込み口の値は {名} の字のまま（表の文と比べるため）、
  借りた型の読み替え {unattended} だけは本物の値（lib/seat.overlay_body）。
- 照らす事: 行き先が「消す」の行の文はどの書き手と下請けの指示にも無い。行き先が「消す」でない行の文が、行き先の書き手の全部の組み上がった指示に在る（共通は全部の書き手、変える は変える段の
  書き手、variant は variant の書き手、variant・pin は variant と下ごしらえの書き手）。行き先が型を絞る行（変える・variant・variant・pin）の
  文は、ほかの書き手の指示に無い。下請けの指示の行（G）は variant の書き手が置く下請けのファイルの md（prompts/parts/g1-*.md を組んだ字）、
  Python が組む行（P）は値を組む関数の字で照らす。
- 例外（付録 A の行き先のまま、指示の段落が書き手の道具で決まる物）: Q10（下請けを起こすなら規則を字のまま渡す）は Agent を持つ
  variant の書き手だけに出る（今の修正役も Agent を持つので出ていた）。F135（赤を見ない clean を拒む）は付録 A では variant だが、PR A が
  受け付けの照らしを variant・remove・pin に当てた（board.RED_WEAPONS）ので、指示もその型の書き手に出す（照らしと指示をそろえる）。
- 返答の形: 型ごとの書き手の返答の形（YAML の output_format）が、PR A の前の修正役の返答の形（fixer-reply-before.json。#869 の前の
  main 5aa8530a の fixer の output_format の写し）の必須の欄と空にできない欄（minLength・minItems）を、どの深さでも減らさない。

文の意味が弱まっていないか（言い換え）は、独立のレビューが文で見る（この試験は字の在る無しだけ）。
"""
import functools
import json
import pathlib
import re
import subprocess
import sys
import unittest

import yaml

from tests.bin import hermetic
from tests.blocks import kit

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
BLOCK = kit.BLOCKS / "fix"
PLAN = "docs/plans/2026-10-24-fix-weapons.md"
for p in (ROOT / "lib", kit.SHARED):
    if str(p) not in sys.path:
        sys.path.append(str(p))

import prompt  # noqa: E402
import seat  # noqa: E402

ROWS = json.loads((HERE / "appendix-a.json").read_text(encoding="utf-8"))
BEFORE = json.loads((HERE / "fixer-reply-before.json").read_text(encoding="utf-8"))
PIN = "523599ac3b62f9ad7f707c5846c4ba186b38c1f0"   # 付録 A の行番号の版（#865。A.2 の見出し「#865 で 2 行増えた後の行番号」）
PLAN_PIN = "8c277a11d84bd69245a8a1ed53acb3850de614cc"   # 計画の版（git の blob。#869 の後の main の計画。付録 A を直す PR はこの値を替える）
DEFAULT = {"A.2": "workflows/fix/prompts/parts/fixer.md", "A.4": "workflows/.shared/prompts/writer-rules.md",
           "A.5": "workflows/.shared/prompts/query-rule.md", "A.7": "lib/borrow/unattended.md"}   # 節の頭が名指す、`:行` だけの引きの置き場
SHARED_PARTS = {"brief-reading.md", "rejected.md"}   # A.3 の .shared/prompts の断片（ほかの名は fix の prompts/parts）
REWORDED = {   # 移す時に字を替えた行: 番号 → (表の字, PIN の字)
    "W21": ("one of the kinds below", "one of the 6 below"),   # 申し出の種類に red_at_base を足した（PR B の控え）
    "F135": ("`clean` without ever having seen red is rejected.", "clean without ever having seen red is rejected"),   # F135 の文を rules_red の段落へ切り出した
}
COUNTS = {"共通": 156, "variant": 29, "変える": 4, "消す": 11}   # 付録 A の A.1・1.4.2 の数（全部で 200）
LEFT = {   # 置き場の行のうち、引く行の文にも残り（rest）にも移さなかった字（付録 A の行の番号 → 残る字）
    "F21": "You are the fixer. , and fix the units you owe a fix on the working tree.",   # 型ごとの頭に言い直した（付録 A の F21）
    "F135": ";",   # F135 の文を rules_red の段落へ切り出した時に消した区切り。行の残り（返答の欄 fix_closure の行）は表の rest
    "G13": "The units fixed in the TDD loop are in the loop summary.",   # 3 文目は G14 と一緒に消す（付録 A の G13 の第 8 版）
}
MARKUP = re.compile(r"<!--.*?-->|\{[\w:.-]+\}")   # 段落の印と差し込み口（字の観点ではない）
SPAWN_ONLY = {"Q10"}
G18 = "Do not write the report to a file. Your reply is the JSON in the \"fields of the reply\" section of the instructions."   # 消した g1-no-report-file.md の字（付録 A の G16〜G19 の G18）
RED_ROWS = {"F135"}   # 付録 A は variant。PR A が受け付けの照らしを variant・remove・pin に当てたので（PR A の控えの 3 節）、指示も同じ型にそろえる   # 下請けを起こす書き手（Agent を持つ variant）だけに出る段落の行
writers = kit.load("fix", "writers")
prompts = kit.load("fix", "prompts")


def nodes() -> dict:
    """型ごとの書き手の node → 型の名"""
    return {writers.node(p, w): w for p in writers.SEQUENCE for w in writers.SEQUENCE[p]}


def to_nodes(to: str, row: str = "") -> set:
    if row in RED_ROWS:   # 受け付けが赤を見ない clean を拒む型（board.RED_WEAPONS）の書き手に言う
        return {n for n, w in nodes().items() if prompts.writer_when(w)["red"]}
    if to == "共通":
        return set(nodes())
    if to == "変える":
        return {n for n, w in nodes().items() if prompts.writer_when(w)["change"]}
    if to == "variant":
        return {n for n, w in nodes().items() if w == "variant"}
    if to == "variant・pin":
        return {n for n, w in nodes().items() if w in ("variant", "pin")}
    raise ValueError(to)


def flat(text: str) -> str:
    """空白をそろえた字（md の字の {{ }} は組んだ指示では { }）"""
    return re.sub(r"\s+", " ", text.replace("{{", "{").replace("}}", "}"))


def assembled(node: str, weapon: str) -> str:
    """node の md を組んだ字（型が選ぶ段落は writer_paragraphs、ほかの段落は全部入れる。値は {名} の字、{unattended} は本物）"""
    raw = prompt._expand(prompt._read(BLOCK / "prompts" / f"{node}.md", "md"), BLOCK, (), False)
    names = {m.group(2) for line in raw.split("\n") if (m := prompt.MARK.match(line.strip()))}
    pick = prompts.writer_paragraphs(weapon)
    when = {n: True for n in names}
    when.update({k: v for k, v in pick.items() if k in names})
    when.update({k: False for k in ("where_tdd", "where_rework") if k in names})   # 修正の書き手に載らない書き先（付録 A の W14・W15）
    slots = set(prompt.SLOT.findall(raw.replace("{{", "").replace("}}", "")))
    values = {s: "{" + s + "}" for s in slots}
    values["unattended"] = seat.overlay_body(seat.OVERLAY_KINDS["fix"]).rstrip("\n")
    return flat(prompt._compose(BLOCK, node, values, when)["prompt"])


def g1_text() -> str:
    """variant の書き手が置く下請けのファイルの md を組んだ字（値は {名} の字）"""
    out = []
    for name in ("g1-impl", "g1-review", "g1-scene", "g1-rest", "g1-report", "g1-impl-report", "g1-head-sha"):
        path = BLOCK / "prompts" / "parts" / f"{name}.md"
        if not path.is_file():
            continue
        raw = prompt._expand(prompt._read(path, "md"), BLOCK, (), False)
        names = {m.group(2) for line in raw.split("\n") if (m := prompt.MARK.match(line.strip()))}
        slots = set(prompt.SLOT.findall(raw.replace("{{", "").replace("}}", "")))
        out.append(prompt._compose(BLOCK, name, {s: "{" + s + "}" for s in slots}, {n: n != "spawns" for n in names},
                                   part=True)["prompt"])
    return flat("\n".join(out))


def expand(ids: str) -> list:
    m = re.fullmatch(r"([A-Z]+)(\d+)〜[A-Z]*(\d+)", ids)
    return [f"{m[1]}{i}" for i in range(int(m[2]), int(m[3]) + 1)] if m else [ids]


def appendix_rows() -> list:
    """付録 A の本文の行 (番号, 行き先, 出どころ)。行き先は 共通・variant・variant・pin・変える・消す（数に入れない行と、A.2 の Q の
    写しの行は除く）。出どころは節の見出しが名指す置き場: A.6 の下請けの指示は g1、A.7 の unattended.md は unattended、A.8 の
    Python が組む行は machine、ほかは writer"""
    body = appendix_a("\n".join(git_show(PLAN_PIN, PLAN)))
    out = []
    for sec in re.split(r"^### ", body, flags=re.M)[1:]:
        head = sec.split("\n", 1)[0]
        place = head.split(" ", 2)[1]
        src = ("g1" if place == "下請けの指示" else "unattended" if place == "`lib/borrow/unattended.md`"
               else "machine" if place == "Python" else "writer")
        for ids, dest in re.findall(r"^- (\S+?) `[^`]*`.*?→ \**([^／]*?)\**\s*／", sec, re.M):
            dest = dest.strip()
            if dest.startswith("数に入れない") or (head.startswith("A.2") and ids.startswith("Q1")):
                continue
            to = ("消す" if dest.startswith("消す") or ids == "F26" else "variant・pin" if dest.startswith("variant・pin")
                  else "variant" if dest.startswith("variant") else "変える" if dest.startswith("変える") else "共通")
            out.append((ids, to, src))
    return out


def appendix_a(text: str) -> str:
    return text[text.index("## 付録 A"):text.index("## 付録 B")]


@functools.lru_cache(maxsize=None)
def git_show(spec: str, path: str) -> list:
    """git の版の字の行（spec は commit:パス か blob）。引けなければ見送らずに赤"""
    done = subprocess.run(["git", "-C", str(ROOT), "show", spec], env=hermetic.child_env(), capture_output=True, text=True)
    if done.returncode:
        raise AssertionError(f"固定した版の {path}（{spec}）を git から引けない（履歴の浅い clone か）: {done.stderr.strip()}")
    return done.stdout.split("\n")


def pinned_lines(path: str) -> list:
    return git_show(f"{PIN}:{path}", path)


def appendix_sources() -> dict:
    """付録 A の本文の行の番号 → その行が引く置き場の行 [(パス, 頭, 尻)]（`:4`・`brief.md:2-4`・`.shared/prompts/lib-docs.md:1` の形）"""
    body = appendix_a("\n".join(git_show(PLAN_PIN, PLAN)))
    out = {}
    for sec in re.split(r"^### ", body, flags=re.M)[1:]:
        head = sec.split("\n", 1)[0][:3]
        for ids, said in re.findall(r"^- (\S+?) (.*?) → ", sec, re.M):
            refs = re.findall(r"`([\w./-]*):(\d+)(?:-(\d+))?`", said)
            if not refs:
                continue
            paths = [DEFAULT[head] if not name else "workflows/" + name if name.startswith(".shared/")
                     else "workflows/.shared/prompts/" + name if name in SHARED_PARTS else "workflows/fix/prompts/parts/" + name
                     for name, _, _ in refs]
            out.setdefault(ids, []).append([(p, int(a), int(b or a)) for p, (_, a, b) in zip(paths, refs)])
    return out


class TableCase(unittest.TestCase):
    def test_the_plan_is_the_pinned_plan(self):
        """作業ツリーの計画の付録 A が PLAN_PIN の版の付録 A と同じ（付録 A を直すなら PLAN_PIN を替えるので、試験の差分に出る）"""
        self.assertEqual(appendix_a((ROOT / PLAN).read_text(encoding="utf-8")), appendix_a("\n".join(git_show(PLAN_PIN, PLAN))),
                         "計画の付録 A が PLAN_PIN の版と違う。付録 A を直したなら PLAN_PIN を新しい blob に替える")

    def test_the_table_is_appendix_a(self):
        self.assertEqual([(r["id"], r["to"], r["from"]) for r in ROWS], appendix_rows())
        for r in ROWS:
            with self.subTest(row=r["id"]):
                self.assertLessEqual(set(r), {"id", "to", "from", "text", "rest"})
                if "rest" in r:   # 残りは全部の書き手に照らすので、消す行・機械の行には置けない
                    self.assertTrue(r["to"] != "消す" and r["from"] == "writer" and r["rest"], "残りを置けない行")

    def test_machine_rows_cite_only_python(self):
        """機械の行（from が machine）が付録 A の本文で引く置き場は、全部 .py のファイル（指示の md の行を machine にして照らしを飛ばせない）"""
        sources = appendix_sources()
        for r in ROWS:
            if r["from"] != "machine":
                continue
            with self.subTest(row=r["id"]):
                paths = [p for refs in sources.get(r["id"], []) for p, _, _ in refs]
                self.assertTrue(paths and all(p.endswith(".py") for p in paths), f"機械の行が .py でない置き場を引く: {paths}")

    def test_counts_by_destination_match_appendix_a(self):
        got = {k: 0 for k in COUNTS}
        for r in ROWS:
            n = len(expand(r["id"]))
            if r["id"] == "G16〜G19":   # G18 だけ消す（付録 A の G16〜G19）
                got["variant"] += 3
                got["消す"] += 1
                continue
            got["variant" if r["to"] == "variant・pin" else r["to"]] += n
        self.assertEqual(got, COUNTS)

    def test_the_table_text_is_the_text_before_the_move(self):
        """表の各行の文は、付録 A がその行に引く置き場の行の PIN の版の字に在る（表と md を一緒に弱めると赤）"""
        sources = appendix_sources()
        cache = {}
        for r in ROWS:
            for line in r["text"] + r.get("rest", []):
                with self.subTest(row=r["id"]):
                    self.assertIn(r["id"], sources, "付録 A の本文に置き場の行の引きが無い")
                    new, old = REWORDED.get(r["id"], ("", ""))
                    want = flat(line.replace(new, old) if new else line).strip()
                    places = [flat(" ".join(" ".join(cache.setdefault(p, pinned_lines(p))[a - 1:b]) for p, a, b in refs))
                              for refs in sources[r["id"]]]
                    self.assertTrue(any(want in place for place in places), f"PIN の版の字に無い: {want[:80]}")

    def test_the_table_text_covers_the_text_before_the_move(self):
        """付録 A が引く置き場の行ごとに、そこを引く行の文を抜いた残りが LEFT の字と等しい（表と md から一緒に削る・行を消すと赤）"""
        sources = appendix_sources()
        cache = {}
        cited = {}
        for r in ROWS:
            if r["from"] == "machine":
                continue
            with self.subTest(row=r["id"], what="空でない"):
                self.assertTrue(r["text"] and all(line.strip() for line in r["text"]), "機械の行でない行の文が空")
            new, old = REWORDED.get(r["id"], ("", ""))
            texts = r["text"] + r.get("rest", []) + ([G18] if r["id"] == "G16〜G19" else [])   # G18 は表の G16〜G19 の行に無い（消す。下の G18）
            for refs in sources.get(r["id"], []):
                for ref in refs:
                    cited.setdefault(ref, []).append((r["id"], [flat(t.replace(new, old) if new else t).strip() for t in texts]))
        for (path, a, b), rows in cited.items():
            ids = "・".join(dict.fromkeys(i for i, _ in rows))
            rest = flat(" ".join(cache.setdefault(path, pinned_lines(path))[a - 1:b]))
            for want in sorted((t for _, texts in rows for t in texts), key=len, reverse=True):
                rest = rest.replace(want, "", 1)
            with self.subTest(row=ids, place=f"{path}:{a}-{b}"):
                self.assertEqual(flat(MARKUP.sub("", rest)).strip(), LEFT.get(ids, ""), "表の文が置き場の行の字を覆わない")


class AssetCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {n: assembled(n, w) for n, w in nodes().items()}
        cls.g1 = g1_text()

    def test_every_row_that_is_not_removed_is_in_its_writers(self):
        for r in ROWS:
            if r["to"] == "消す" or r["from"] == "machine":
                continue
            for line in r["text"]:
                want = flat(line)
                if r["from"] == "g1":
                    with self.subTest(row=r["id"], where="g1"):
                        self.assertIn(want, self.g1)
                    continue
                targets = {n for n in to_nodes(r["to"], r["id"]) if r["id"] not in SPAWN_ONLY or prompts.writer_paragraphs(nodes()[n])["spawns"]}
                for n in sorted(targets):
                    with self.subTest(row=r["id"], node=n):
                        self.assertIn(want, self.text[n])

    def test_the_rest_of_a_row_is_in_every_writer(self):
        """表の行の残り（rest。行き先が型を絞る行が引く置き場の行のうち、その行の文に移さなかった字）は、全部の書き手に在る"""
        for r in ROWS:
            for line in r.get("rest", []):
                for n in sorted(nodes()):
                    with self.subTest(row=r["id"], node=n):
                        self.assertIn(flat(line).strip(), self.text[n])

    def test_removed_rows_are_in_no_writer(self):
        """行き先が「消す」の行の文は、どの書き手の指示にも下請けの指示にも無い（G16〜G19 の行は variant なので、消す G18 の文は G18 で足す）"""
        removed = [(r["id"], r["from"], line) for r in ROWS if r["to"] == "消す" for line in r["text"]]
        removed.append(("G18", "g1", G18))
        for rid, src, line in removed:
            places = {"g1": self.g1, **self.text}   # 下請けの行（G）も、下請けを起こさない周に書き手の指示へ直に載っていた
            for name, text in places.items():
                with self.subTest(row=rid, where=name):
                    self.assertNotIn(flat(line), text)

    def test_rows_of_a_weapon_are_not_in_other_writers(self):
        for r in ROWS:
            if r["to"] in ("共通", "消す") or r["from"] != "writer":
                continue
            for n in sorted(set(nodes()) - to_nodes(r["to"], r["id"])):
                for line in r["text"]:
                    with self.subTest(row=r["id"], node=n):
                        self.assertNotIn(flat(line), self.text[n])

    def test_the_writers_node_md_names_its_weapon_part(self):
        for n, w in nodes().items():
            with self.subTest(node=n):
                self.assertEqual((BLOCK / "prompts" / f"{n}.md").read_text(encoding="utf-8").strip(), "{part:%s}" % writers.node("first", w))

    def test_python_built_rows(self):
        rules = kit.load("fix", "rules")
        board = kit.load("fix", "board")
        self.assertIn(f"・{rules.NOT_NOW}: b", rules.unit_note(["a", "b"], ["a"]))   # P1: 項目の単位のうち今の注文に無い物を直させない
        recount = (ROOT / "lib" / "recount.py").read_text(encoding="utf-8")
        self.assertIn("退行を注入して赤を見てから出せ", recount)   # P2: F135 の拒否の文（赤を見ない clean を拒む型だけに届く）
        self.assertIn("variant", board.RED_WEAPONS)
        self.assertNotIn("static", board.RED_WEAPONS)
        rolekit = (ROOT / "lib" / "rolekit.py").read_text(encoding="utf-8")
        self.assertIn("前の回の拒否も直したままにする", rolekit)   # P3: 拒否の並びの頭（前の回の拒否も直したままにする）


def requirements(shape, path="") -> set:
    """形の必須の欄と空にできない欄の印（パス・種類・値）の集まり。allOf の then も同じ深さで数える"""
    out = set()
    if not isinstance(shape, dict):
        return out
    for k in shape.get("required") or []:
        out.add((path, "required", k))
    for key in ("minLength", "minItems"):
        if key in shape:
            out.add((path, key, shape[key]))
    for name, sub in (shape.get("properties") or {}).items():
        out |= requirements(sub, f"{path}.{name}")
    if isinstance(shape.get("items"), dict):
        out |= requirements(shape["items"], f"{path}[]")
    for i, branch in enumerate(shape.get("allOf") or []):
        out |= {(f"{path}.allOf{i}{p}", kind, v) for p, kind, v in requirements(branch.get("then") or {}, "")}
    return out


class ReplyShapeCase(unittest.TestCase):
    def test_writer_replies_keep_every_required_and_non_empty_field(self):
        doc = yaml.safe_load((BLOCK / "works-factory-fix.yaml").read_text(encoding="utf-8"))
        found = {}

        def walk(ns):
            for n in ns:
                found[n["id"]] = n
                walk((n.get("loop_group") or {}).get("nodes") or [])
        walk(doc["nodes"])
        base = requirements(BEFORE)
        self.assertGreater(len(base), 30)
        for n in nodes():
            with self.subTest(node=n):
                got = requirements(found[n]["output_format"])
                self.assertEqual(sorted(base - got), [], "PR A の前の修正役の返答の形から減った欄")


if __name__ == "__main__":
    unittest.main()
