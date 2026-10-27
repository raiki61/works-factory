"""AI の node の指示を、その node の md に値を入れて組む口（docs/design/README.md の 5 章）。コードは指示の文を持たない。

- render(node_id, values, when=None) -> {"prompt": 字, "system"?: 字}: 呼んだ script の在る block の prompts/<node_id>.md を読み、
  断片と段落を選び、差し込み口に値を入れた指示。prompts/<node_id>.system.md が在れば、同じ値と when で組んだ system prompt も返す
  （YAML の systemPrompt: に文を書かない。README の 13 章）。パスも文も受けない
- emit(node_id, values, when, n) -> render の返り: 組んだ物を place の <node_id>-prompt-<n>.md（と <node_id>-system-<n>.md）に書き、
  prep の返りの形で返す。AI の node の YAML は prompt: "$<prep>.output.prompt"（と systemPrompt: "$<prep>.output.system"）だけ。
  隣に <node_id>-viewer-values-<n>.json も書く（下の「見る道具のための値の記録」）
- render_part(name, values, when=None) -> str: 呼んだ script の在る block の prompts/parts/<name>.md を、render と同じ決まり（断片・段落・
  差し込み口の数え・落ち方）で組んだ字。AI の node でない物（束ね役が起こす下請けが Read する指示のファイルなど）の指示を md から組む
- render_shared(name, values, when=None) -> str: pack の .shared/prompts/<name>.md を、render と同じ決まりで組んだ字（呼んだ block を問わない）。
  2 つ以上の block が使う、AI の node でない物の指示を md から組む（書き手の型の block 全部が起こす下請けのファイルなど。本体 writerblock が呼ぶ）。
  共通の断片は {part:…} を持たない。頭の印 <!-- required-for-tools: … --> は差し込む時と同じく落とす
- round_of(node_id) -> int: place に在る <node_id>-prompt-<n>.md の数 + 1（emit に渡す、輪の何回目か）
- lang(raw) -> str: 人に見せる欄の言語の値（port lang。空なら共通の断片 .shared/prompts/lang-default.md の文）

md の書き方:
- 差し込み口 {name}（小文字・数字・_）。字の { と } は {{ と }} で書く。形の合わない {"a": 1}・{id, url} は字のまま残る
- {shared:<name>} は pack の .shared/prompts/<name>.md、{part:<name>} は同じ block の prompts/parts/<name>.md を差し込む
  （断片の中の断片も差し込む。.shared の断片は {part:…} を持たない）
- .shared の断片は、頭の 1 行に <!-- required-for-tools: <道具> <道具> --> を置ける（どれかの道具を allowed_tools に持つ AI の node の指示は
  この断片を入れる、という形の検査 7.1 の 14 の印）。差し込む時に落とすので、指示には出ない
- 差し込むかを選ぶ段落は、それぞれ 1 行の <!-- if <name> --> か <!-- if not <name> --> と <!-- end <name> --> で囲む。入れ子にしない
- 入れた値の中の字（{…}・$…）は読み直さない。Archon も prompt: の $<id>.output.prompt に入れた字を読み直さない（止めた版の
  executor-shared.ts の substituteWorkflowVariables が 1 回の走査で、入れた値を字のまま置く）

見る道具のための値の記録（持ち主の決め prompt-values-for-viewer）:
- emit が place に書く <node_id>-viewer-values-<n>.json は、工場の外の見る道具（run で LLM に入った英語の指示を、日本語の md の写しで
  同じ形に組み直して人に見せる物）のための記録で、工場の中では読まない。LLM に渡す指示の字は変えない（日本語は人が読む射影で、
  LLM には英語だけを渡す）
- 形: {"node": node_id, "block": 呼んだ block のフォルダの名, "md": {"prompt": "prompts/<node_id>.md", "system"?: "prompts/<node_id>.system.md"}
  （block からの相対パス。組んだ欄ごと）, "values": 差し込み口の値（字か整数）, "when": 段落の選び（when=None は {}）}。
  この values と when で組み直すと、同じ <node_id>-prompt-<n>.md（と system）が字のまま組み上がる

落ちる時（PromptError。ValueError の子）: md か断片が無い・断片が自分を差し込む・値の無い差し込み口が在る（選ばれない段落の中も、
system の md の中も数える）・使われない値を渡された・when の名がどの md の if にも無い・md の if の名が when に無い・if と end が
組にならない・値が字と整数の外。
"""
import json
import re
from pathlib import Path

import ports

SLOT = re.compile(r"\{([a-z0-9_]+)\}")
FRAGMENT = re.compile(r"\{(shared|part):([a-z0-9][a-z0-9_-]*)\}")
MARK = re.compile(r"^<!-- (if|if not|end) ([a-z0-9_]+) -->$")
REQUIRED_FOR_TOOLS = re.compile(r"\A<!-- required-for-tools: [A-Za-z]+(?: [A-Za-z]+)* -->\n")   # 共通の断片の頭の印（形の検査が読む。指示には出さない）
NODE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
OPEN, CLOSE = "\x00", "\x01"
LANG_DEFAULT = "lang-default"   # 共通の断片の名（lib/rolekit.py の LANG_DEFAULT と同じ意味の英語の文）
SYSTEM = ".system"
VIEWER_VALUES = "viewer-values"   # 工場の外の見る道具のための値の記録 <node_id>-viewer-values-<n>.json（工場の中では読まない）


class PromptError(ValueError):
    """指示が組めない（md と値の食い違い）"""


def lang(raw) -> str:
    return ports.text(raw).strip() or _read(ports.SHARED / "prompts" / f"{LANG_DEFAULT}.md", "断片").strip()


def _read(path: Path, what: str) -> str:
    try:
        return path.read_text(encoding="utf-8").rstrip("\n")
    except FileNotFoundError:
        raise PromptError(f"{what} {path} が無い") from None


def _expand(text: str, block: Path, stack: tuple, in_shared: bool) -> str:
    def one(match: re.Match) -> str:
        kind, name = match.groups()
        if kind == "part" and in_shared:
            raise PromptError(f"共通の断片 {stack[-1]} が block の断片 {{part:{name}}} を差し込む（.shared の断片は part を持たない）")
        key = f"{kind}:{name}"
        if key in stack:
            raise PromptError(f"断片が自分を差し込む: {' → '.join(stack + (key,))}")
        path = (ports.SHARED / "prompts" if kind == "shared" else block / "prompts" / "parts") / f"{name}.md"
        body = REQUIRED_FOR_TOOLS.sub("", _read(path, "断片") + "\n", count=1).rstrip("\n") if kind == "shared" else _read(path, "断片")
        return _expand(body, block, stack + (key,), in_shared or kind == "shared")
    return FRAGMENT.sub(one, text)


def _select(text: str, when: dict) -> tuple[str, set]:
    """段落を when で選ぶ。印の行は消す。返り (選んだ字, md の段落の名)"""
    out, open_name, keep, names = [], None, True, set()
    for line in text.split("\n"):
        mark = MARK.match(line.strip())
        if not mark:
            if "<!-- if " in line or "<!-- end " in line:
                raise PromptError(f"段落の印は 1 行に 1 つだけ置く: {line.strip()!r}")
            if keep:
                out.append(line)
            continue
        word, name = mark.groups()
        if word == "end":
            if name != open_name:
                raise PromptError(f"<!-- end {name} --> が開いた段落 {open_name!r} と組にならない")
            open_name, keep = None, True
            continue
        if open_name is not None:
            raise PromptError(f"段落 {open_name!r} の中に段落 {name!r} を開く（入れ子にしない）")
        if name not in when:
            raise PromptError(f"md の段落 {name!r} の真偽が when に無い")
        names.add(name)
        open_name, keep = name, bool(when[name]) == (word == "if")
    if open_name is not None:
        raise PromptError(f"段落 {open_name!r} が閉じていない")
    return "\n".join(out), names


def _compose(block: Path, node_id: str, values: dict, when: dict | None, *, part: bool = False, shared: bool = False) -> dict:
    if not NODE_ID.fullmatch(node_id):
        raise PromptError(f"{'断片' if part or shared else 'node'} の id の形でない: {node_id!r}")
    when = dict(when or {})
    if not all(isinstance(v, bool) for v in when.values()):
        raise PromptError("when の値は真偽だけ")
    if shared:
        files = {"prompt": ports.SHARED / "prompts" / f"{node_id}.md"}
    else:
        files = {"prompt": block / "prompts" / ("parts" if part else "") / f"{node_id}.md"}
    if not (part or shared) and (system := block / "prompts" / f"{node_id}{SYSTEM}.md").is_file():
        files["system"] = system

    def read(path: Path) -> str:
        text = _read(path, "指示の md")
        return REQUIRED_FOR_TOOLS.sub("", text + "\n", count=1).rstrip("\n") if shared else text
    texts = {key: _expand(read(path), block, (f"shared:{node_id}",) if shared else (), shared).replace("{{", OPEN).replace("}}", CLOSE)
             for key, path in files.items()}
    slots = {name for text in texts.values() for name in SLOT.findall(text)}
    missing, unused = sorted(slots - set(values)), sorted(set(values) - slots)
    if missing:
        raise PromptError(f"{node_id} の md の置き換えの印 {missing} に値が無い")
    if unused:
        raise PromptError(f"値 {unused} の置き換えの印が {node_id} の md に無い")
    bad = sorted(k for k, v in values.items() if isinstance(v, bool) or not isinstance(v, (str, int)))
    if bad:
        raise PromptError(f"値 {bad} が字でも整数でもない（材料は prep が字に組む）")
    out, seen = {}, set()
    for key, text in texts.items():
        chosen, names = _select(text, when)
        seen |= names
        chosen = re.sub(r"\n{3,}", "\n\n", chosen).strip("\n")
        out[key] = SLOT.sub(lambda m: str(values[m.group(1)]), chosen).replace(OPEN, "{").replace(CLOSE, "}") + "\n"
    if set(when) - seen:
        raise PromptError(f"when の名 {sorted(set(when) - seen)} が md の段落に無い")
    return out


def render(node_id: str, values: dict, when: dict | None = None) -> dict:
    return _compose(ports.caller_block(), node_id, values, when)


def render_part(name: str, values: dict, when: dict | None = None) -> str:
    return _compose(ports.caller_block(), name, values, when, part=True)["prompt"]


def render_shared(name: str, values: dict, when: dict | None = None) -> str:
    return _compose(ports.SHARED, name, values, when, shared=True)["prompt"]


def emit(node_id: str, values: dict, when: dict | None, n: int) -> dict:
    block = ports.caller_block()
    out = _compose(block, node_id, values, when)
    place = ports.place()
    for key, text in out.items():
        (place / f"{node_id}-{key}-{n}.md").write_text(text, encoding="utf-8")
    md = {key: f"prompts/{node_id}{SYSTEM if key == 'system' else ''}.md" for key in out}
    kept = {"node": node_id, "block": block.name, "md": md, "values": values, "when": dict(when or {})}
    (place / f"{node_id}-{VIEWER_VALUES}-{n}.json").write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def round_of(node_id: str) -> int:
    return len(list(ports.place().glob(f"{node_id}-prompt-*.md"))) + 1
