"""図のノードと block の札の「何をする物か」の 1 行の選び（設計は docs/design/viewer.md の 4.5。下書き docs/plans/2026-10-29-viewer-overview.md の 5.6）。

見るたびに LLM で書かせず、工場に既に在る字から、ノードの種類ごとの順で、最初に在る物の最初の文を選ぶ。読むのは設計書（docs/design/）と、
作りの読み（shape.py）が既に持つ字（YAML の説明・script の docstring・指示の md とその日本語の写し）だけで、block の src/ は読まない（E22）。

- graph と block: 自分の設計書の「役」の見出しの下の最初の文 → YAML の説明が名指す設計書の中の、そのフォルダの節の「役」→ YAML の description
- AI: 設計書の「node の設計シート: <id>」の「役」→ 設計書の node の並びの行（`<id>`（…）: 説明）→ YAML の description → 指示の md の You で始まる段落
  （日本語の写しが在れば写し）
- script: docstring の最初の文。「受け皿」「返し」で始まる物は配線（wire）
- include と workflow: 呼ぶ先の graph の 1 行と、呼ぶ側での役（呼ぶ側の設計書の node の並びの行 → with の mode の値）
- 繰り返し: 形から組む。承認・止め・bash: 設計書の node の並びの行 → YAML の description

- attach(shape, design, translate) -> problems: shape の graph に what、item に what（{line, from, why, role?, role_from?, wire?}）を足す。1 行が無い
  物は line が空。読めない設計書の節（「役」の見出しの下に段落が無い）を problems に返す（tests/viewer/test_what.py が今の木で 0 を照らす）
"""
import re
from collections.abc import Callable
from pathlib import Path

from viewer.src import shape

HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
NUMBER = re.compile(r"^[0-9.]+\s+")
SHEET = "node の設計シート"
ROLE = "役"
ID = re.compile(r"^[A-Za-z0-9_-]+$")
ITEM = re.compile(r"^(?:[-*]|\d+(?:\.\d+)*\.)\s+`([A-Za-z0-9_-]+)`")
WIRES = ("受け皿", "返し")


def attach(data: dict, design: Path, translate: Callable[[str], str] = lambda s: s) -> list[str]:
    problems, docs = [], {}

    def doc(name: str) -> "_Doc":
        if name not in docs:
            docs[name] = _Doc(name, (design.parent.parent / name).read_text(encoding="utf-8"), problems)
        return docs[name]

    graphs = data["graphs"]
    for folder, graph in graphs.items():
        graph["what"] = _graph(folder, graph, [doc(n) for n in graph.get("docs") or []])
    for folder, graph in graphs.items():
        books = [doc(n) for n in graph.get("docs") or []]
        for item in shape.walk(graph["items"]):
            item["what"] = _item(item, graph, graphs, books, translate)
    return problems


def first(text: str) -> tuple[str, str]:
    """字の最初の文と残り。文の終わりは、括弧と ` の外の「。」か、英語の「. 」"""
    text = " ".join(text.split())
    depth, code = 0, False
    for i, ch in enumerate(text):
        if ch == "`":
            code = not code
        elif code:
            continue
        elif ch in "（(「":
            depth += 1
        elif ch in "）)」":
            depth = max(0, depth - 1)
        elif depth == 0 and (ch == "。" or (ch in ".!?" and (i + 1 == len(text) or text[i + 1] == " "))):
            return text[:i + 1], text[i + 1:].strip()
    return text, ""


class _Doc:
    """設計書 1 本の見出しの木と、node の並びの行"""

    def __init__(self, name: str, text: str, problems: list):
        self.name, self.heads, self.lines = name, [], text.split("\n")
        fence = ""
        for n, line in enumerate(self.lines):
            mark = re.match(r"\s*(`{3,}|~{3,})", line)
            if mark and (not fence or (mark[1][0] == fence[0] and len(mark[1]) >= len(fence) and not line.strip()[len(mark[1]):])):
                fence = "" if fence else mark[1]
                continue
            hit = not fence and HEAD.match(line)
            if hit:
                self.heads.append({"n": n, "level": len(hit[1]), "title": hit[2], "name": NUMBER.sub("", hit[2])})
        for i, head in enumerate(self.heads):
            head["up"] = [h for h in self.heads[:i] if h["level"] < head["level"]]
            head["up"] = [h for j, h in enumerate(head["up"]) if all(o["level"] > h["level"] for o in head["up"][j + 1:])]
            if head["name"] == ROLE and not self.paragraph(head):
                problems.append(f"docs/design/{Path(name).name}: 「{head['title']}」の見出しの下に段落が無い（札の 1 行が選べない）")

    def paragraph(self, head: dict) -> str:
        """見出しの下の最初の段落（次の見出しまで）"""
        got = []
        for line in self.lines[head["n"] + 1:]:
            if HEAD.match(line):
                break
            if not line.strip():
                if got:
                    break
                continue
            got.append(line.strip())
        return " ".join(got)

    def where(self, head: dict) -> str:
        return f"設計書 {self.name} の「{head['title']}」"

    def role(self, folder: str, own: bool) -> dict | None:
        """graph・block の役。自分の設計書なら設計シートの外の最初の「役」、ほかの設計書ならフォルダの名で始まる節の下の「役」"""
        for head in self.heads:
            if head["name"] != ROLE or any(SHEET in up["name"] for up in head["up"]):
                continue
            if own or any(re.match(rf"{re.escape(folder)}(?![A-Za-z0-9_-])", up["name"]) for up in head["up"]):
                return self._from(head)
        return None

    def sheet(self, ident: str) -> dict | None:
        """「node の設計シート: <id>」の下の「役」"""
        for i, head in enumerate(self.heads):
            if not head["name"].startswith(SHEET + ":") or ident not in _ids(head["name"][len(SHEET) + 1:]):
                continue
            for kid in self.heads[i + 1:]:
                if kid["level"] <= head["level"]:
                    break
                if kid["name"] == ROLE:
                    return self._from(kid)
        return None

    def listed(self, ident: str) -> dict | None:
        """node の並びの行「`<id>`（…）: 説明」の説明"""
        for line in self.lines:
            hit = ITEM.match(line.strip())
            if not hit or hit[1] != ident:
                continue
            rest = _after_paren(line.strip()[hit.end():])
            if rest is not None and rest[:1] in (":", "："):
                line_, why = first(rest[1:].strip())
                if line_:
                    return {"line": line_, "why": why, "from": f"設計書 {self.name} の node の並びの `{ident}` の行"}
        return None

    def _from(self, head: dict) -> dict | None:
        text = self.paragraph(head)
        if not text:
            return None
        line, why = first(text)
        return {"line": line, "why": why, "from": self.where(head)}


def _ids(text: str) -> list[str]:
    text = re.sub(r"（[^）]*）|\([^)]*\)", " ", text)
    return [part.strip().strip("`") for part in re.split(r"と|・|、|,", text) if ID.match(part.strip().strip("`"))]


def _after_paren(text: str) -> str | None:
    """頭の全角の括弧（入れ子を数える）の後ろ。括弧が無ければそのまま。閉じなければ None"""
    if not text.startswith("（"):
        return text
    depth = 0
    for i, ch in enumerate(text):
        depth += {"（": 1, "）": -1}.get(ch, 0)
        if depth == 0:
            return text[i + 1:]
    return None


def _desc(text: str, where: str) -> dict | None:
    line, why = first(text or "")
    return {"line": line, "why": why, "from": where} if line else None


def _graph(folder: str, graph: dict, books: list) -> dict:
    own = f"docs/design/{folder}.md"
    for book in books:
        got = book.role(folder, book.name == own)
        if got:
            return got
    return _desc(graph.get("desc"), f"YAML {graph['file']} の description") or _none()


def _item(item: dict, graph: dict, graphs: dict, books: list, translate: Callable[[str], str]) -> dict:
    kind, ident = item["kind"], item["id"]
    yaml = f"YAML {graph['file']} の {ident} の description"
    if kind == "ai":
        return (_pick(book.sheet(ident) for book in books) or _pick(book.listed(ident) for book in books) or _desc(item.get("desc"), yaml)
                or _prompt(item, translate) or _none())
    if kind == "script":
        got = _desc(item.get("doc"), f"script {item.get('script_file') or item.get('script')} の docstring")
        if got and got["line"].startswith(WIRES):
            got["wire"] = True
        return got or _none()
    if kind in ("block", "child"):
        callee = graphs.get(item.get("target") or "")
        got = dict(callee["what"]) if callee else (_pick(book.listed(ident) for book in books) or _desc(item.get("desc"), yaml) or _none())
        role = _pick(book.listed(ident) for book in books) if callee else None
        if role:
            got.update(role=role["line"], role_from=role["from"])
        elif (item.get("with") or {}).get("mode"):
            got.update(role=f"形 {item['with']['mode']}", role_from=f"YAML {graph['file']} の {ident} の with の mode")
        return got
    if kind == "loop":
        kids, most = len(item.get("kids") or []), item.get("max")
        line = f"下の {kids} ノードを最大 {most} 周回す器。" if most else f"下の {kids} ノードを回す器。"
        return {"line": line, "why": "", "from": "繰り返しの形（loop_group のノードの数と max_iterations）から組んだ"}
    return _pick(book.listed(ident) for book in books) or _desc(item.get("desc"), yaml) or _none()


def _prompt(item: dict, translate: Callable[[str], str]) -> dict | None:
    md = item.get("md") or {}
    for paragraph in re.split(r"\n\s*\n", md.get("text") or ""):
        if paragraph.strip().startswith("You "):
            japanese = translate(paragraph.strip())
            line, why = first(japanese)
            note = "の日本語の写し" if japanese != paragraph.strip() else "（訳が無いので英語）"
            return {"line": line, "why": why, "from": f"指示の md {md.get('file')} の You で始まる段落{note}"}
    return None


def _pick(found) -> dict | None:
    return next((f for f in found if f), None)


def _none() -> dict:
    return {"line": "", "why": "", "from": ""}
