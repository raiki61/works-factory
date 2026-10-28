"""日本語の写し（AI のノードへの英語の指示を段落ごとに日本語に訳した、人が読むための射影。LLM には渡さない。持ち主の決め
prompt-values-for-viewer・viewer-in-repo の 4。設計は docs/design/viewer.md の 6.6）。訳は見るたびに LLM で作らず、訳の控えから引く。

訳の控えは、段落の字の sha1 の頭 16 字を鍵、訳を値にした JSON で、2 か所に分ける（計画 docs/plans/2026-10-28-viewer.md の 5.2 の案 J1）:
- REPO（このフォルダの隣の ja/paragraphs.json）: 工場の指示の md（pack の <block>/prompts/ と .shared/prompts/）の段落の訳。リポジトリに入れる
- 利用者のキャッシュ（殻と同じ取り置きの置き場 bin/_lib/place.py の cache_dir の下の viewer/ja-cache.json）: それ以外の段落（Claude Code の
  字・run の時に入った字。対象のリポジトリの字を含みうるので、リポジトリに入れない）

段落は、空の行と、組み立ての印の行（段落の選びの印・道具の印・断片だけの行）で区切った行の塊。英字が 40 字を超え、かなが英字の 3 分の 1
未満の塊だけを訳す。訳は、差し込み口（{name}・{shared:…}・{part:…}）と字の {{・}} と印の頭の字を英語と同じだけ持ち、印の行を持たない
物だけを使う（fits）。合わない訳は取り込まず、組む時も英語のまま残すので、日本語の写しの md の木は英語の木と同じ値と段落の選びで組める。

- table(env) -> 訳の控え（REPO とキャッシュを合わせた物。REPO が勝つ）
- translate(text, table) -> (訳した字, 訳の無い段落 {鍵: 英語})
- attach(data, pack, env) -> 訳の無い段落: 見る道具のデータに日本語の写しを足す。図の md（item の md・system_md の ja）、run の出来事ごとに
  値の記録（<node>-viewer-values-<n>.json）から工場の組み立ての口 prompt.compose で組み直した写し（出来事の prompts）、会話の字の写し
  （texts_ja）、訳の無い段落の数（ja）。pack は図を作った pack のフォルダ（run の写しか今の木）
- export(todo, folder) -> 束の数: 訳の無い段落を約 3.5 万字ずつの束 batch-<n>.en.txt に書く（訳すのは取り次ぐ会話）
- take(folder, env) -> (REPO に入れた数, キャッシュに入れた数, 拒んだ行): 束の訳 batch-<n>.ja.txt を取り込む。今の木の md の段落の鍵だけを
  REPO に、ほかをキャッシュに書く。置き場か束が無ければ何も書かずに拒む
- prune() -> 消した数: REPO から、今の木の md の段落に無い鍵を消す（md を直して古くなった訳。残っていても英語で出るだけで、赤にはしない）
"""
import hashlib
import json
import re
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from bin._lib import place
from viewer.src import shape

ROOT = Path(__file__).resolve().parents[2]
_OURS = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]
_SHARED = ROOT / _OURS["folder"] / ".shared"
if str(_SHARED) not in sys.path:
    sys.path.append(str(_SHARED))
import ports  # noqa: E402  pack の共通の部品（層の地図の shared）
import prompt  # noqa: E402

REPO = Path(__file__).resolve().parents[1] / "ja" / "paragraphs.json"
CACHE = Path("viewer") / "ja-cache.json"   # place.cache_dir の下
TREE = ROOT / _OURS["folder"]
BATCH = 35000
SEP = re.compile(r"^%%% ([0-9a-f]{16})$", re.M)
TOKENS = re.compile("|".join([r"\{\{", r"\}\}", prompt.SLOT.pattern, prompt.FRAGMENT.pattern, r"<!-- (?:if|end) "]))


def key(paragraph: str) -> str:
    return hashlib.sha1(paragraph.strip().encode()).hexdigest()[:16]


def wanted(paragraph: str) -> bool:
    english = len(re.findall(r"[A-Za-z]", paragraph))
    return english > 40 and len(re.findall(r"[ぁ-んァ-ン]", paragraph)) * 3 < english


def fits(english: str, japanese: str) -> bool:
    """訳が英語と同じ差し込み口と印の字を持ち、印の行を持たない（組み立てが英語と同じ値と段落の選びで通る）"""
    def tokens(text: str) -> list[str]:
        return sorted(m[0] for m in TOKENS.finditer(text))
    return bool(japanese.strip()) and tokens(english) == tokens(japanese) and not any(_structural(line) for line in japanese.split("\n"))


def table(env: Mapping[str, str]) -> dict[str, str]:
    return {**_load(place.cache_dir(env) / CACHE), **_load(REPO)}


def translate(text: str, got: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    out, missing = [], {}
    for chunk, is_paragraph in _chunks(text):
        if is_paragraph and wanted(chunk):
            mark = key(chunk)
            if mark in got and fits(chunk, got[mark]):
                out.append(got[mark])
                continue
            missing[mark] = chunk.strip()
        out.append(chunk)
    return "\n".join(out), missing


def attach(data: dict, pack: Path, env: Mapping[str, str]) -> dict[str, str]:
    got = table(env)
    with tempfile.TemporaryDirectory() as tmp:
        md_missing = _tree(pack, Path(tmp), got)
        for graph in data["shape"]["graphs"].values():
            for item in shape.walk(graph["items"]):
                for name in ("md", "system_md"):
                    if (item.get(name) or {}).get("text"):
                        item[name]["ja"] = translate(item[name]["text"], got)[0]
        if data.get("run"):
            _prompts(data, Path(tmp))
    text_missing, texts_ja = {}, {}
    for mark in _session_marks(data.get("run")):
        japanese, missing = translate(data["texts"][mark], got)
        text_missing.update(missing)
        if japanese != data["texts"][mark]:
            texts_ja[mark] = japanese
    data["texts_ja"] = texts_ja
    data["ja"] = {"md": len(md_missing), "texts": len(set(text_missing) - set(md_missing))}
    return {**text_missing, **md_missing}


def export(todo: Mapping[str, str], folder: Path) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    batches, size = [[]], 0
    for mark, english in sorted(todo.items(), key=lambda kv: kv[1]):
        if batches[-1] and size + len(english) > BATCH:
            batches.append([])
            size = 0
        batches[-1].append((mark, english))
        size += len(english)
    batches = [b for b in batches if b]
    for n, batch in enumerate(batches):
        (folder / f"batch-{n}.en.txt").write_text("\n".join(f"%%% {mark}\n{english}\n" for mark, english in batch), encoding="utf-8")
    return len(batches)


def take(folder: Path, env: Mapping[str, str]) -> tuple[int, int, list[str]]:
    if not sorted(folder.glob("batch-*.ja.txt")):
        return 0, 0, [f"{folder}: 訳の束 batch-<n>.ja.txt が無い" if folder.is_dir() else f"{folder}: 置き場が無い"]
    ours = tree_keys()
    repo, cache = _load(REPO), _load(place.cache_dir(env) / CACHE)
    to_repo = to_cache = 0
    refused = []
    for ja_file in sorted(folder.glob("batch-*.ja.txt")):
        en_file = ja_file.with_name(ja_file.name.replace(".ja.", ".en."))
        if not en_file.is_file():
            refused.append(f"{ja_file.name}: 英語の束 {en_file.name} が無い")
            continue
        english, japanese = _parse(en_file.read_text(encoding="utf-8")), _parse(ja_file.read_text(encoding="utf-8"))
        refused += [f"{ja_file.name}: 訳の無い段落 {mark}" for mark in sorted(set(english) - set(japanese))]
        for mark, text in japanese.items():
            if mark not in english or key(english[mark]) != mark:
                refused.append(f"{ja_file.name}: 英語の束に無い鍵 {mark}")
            elif not fits(english[mark], text):
                refused.append(f"{ja_file.name}: {mark} の訳が差し込み口か印の字を英語と同じに持たない")
            elif mark in ours:
                repo[mark], to_repo = text, to_repo + 1
            else:
                cache[mark], to_cache = text, to_cache + 1
    _save(REPO, repo)
    _save(place.cache_dir(env) / CACHE, cache)
    return to_repo, to_cache, refused


def prune() -> int:
    ours, repo = tree_keys(), _load(REPO)
    kept = {mark: text for mark, text in repo.items() if mark in ours}
    _save(REPO, kept)
    return len(repo) - len(kept)


def tree_keys() -> set[str]:
    """今の木の md の、訳す段落の鍵"""
    return {key(chunk) for path in _md_files(TREE) for chunk, is_paragraph in _chunks(path.read_text(encoding="utf-8"))
            if is_paragraph and wanted(chunk)}


def _structural(line: str) -> bool:
    line = line.strip()
    return bool(prompt.MARK.match(line) or prompt.REQUIRED_FOR_TOOLS.match(line + "\n") or prompt.FRAGMENT.fullmatch(line))


def _chunks(text: str) -> list[tuple[str, bool]]:
    """字を、段落（行の塊）と、段落でない行（空の行と印の行）の並びにする。"\\n" でつなぐと元の字に戻る"""
    out, block = [], []
    for line in text.split("\n"):
        if not line.strip() or _structural(line):
            if block:
                out.append(("\n".join(block), True))
                block = []
            out.append((line, False))
        else:
            block.append(line)
    if block:
        out.append(("\n".join(block), True))
    return out


def _md_files(pack: Path) -> list[Path]:
    return sorted(pack.glob("*/prompts/**/*.md"))


def _tree(pack: Path, dest: Path, got: Mapping[str, str]) -> dict[str, str]:
    """pack の md を訳に差し替えて dest に同じ形で書き、訳の無い段落を返す"""
    missing = {}
    for path in _md_files(pack):
        japanese, lack = translate(path.read_text(encoding="utf-8"), got)
        missing.update(lack)
        out = dest / path.relative_to(pack)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(japanese, encoding="utf-8")
    return missing


def _prompts(data: dict, tree: Path) -> None:
    """出来事ごとに、同じ place の値の記録から日本語の写しの木で組み直した指示。どの記録がその出来事の指示かは、place に書かれた英語の
    指示（<md>-prompt-<n>.md）の字が、出来事の会話に入った指示の字と同じかで決める（md の名がノードの id と違う prep・会話を続ける輪
    にも当たる）。当たった中にノードの id と同じ名の md の記録が在ればそれだけにする（続けた会話には前のノードの指示も入っている）。
    会話の記録が無ければ、ノードの id と同じ名の md の記録を引く。同じ所（run と node の道）の出来事の数と記録の数が同じなら
    書いた順に 1 つずつ当て、違えば全部の回を並べる"""
    sessions, texts = data["run"].get("sessions") or {}, data["texts"]
    groups: dict[tuple, tuple[dict, list]] = {}
    for event in data["run"]["events"]:
        if not event.get("artifacts") or not event["tokens"]:
            continue
        folder = Path(event["artifacts"]).joinpath(*ports.include_folders(event["path"]))
        said = sessions.get(event.get("session") or "")
        sent = {texts[row[1]].strip() for row in said["seq"] if row[0] == "user"} if said else None
        rounds = {}
        for path in folder.glob(f"*-{prompt.VIEWER_VALUES}-*.json"):
            md, _, n = path.name[:-len(".json")].rpartition(f"-{prompt.VIEWER_VALUES}-")
            english = folder / f"{md}-prompt-{n}.md"
            if not n.isdigit() or not english.is_file():
                continue
            if (english.read_text(encoding="utf-8").strip() in sent) if sent is not None else md == event["tokens"][-1]:
                rounds[(path.stat().st_mtime_ns, md, int(n))] = path
        rounds = {at: path for at, path in rounds.items() if at[1] == event["tokens"][-1]} or rounds
        if rounds:
            group = groups.setdefault((event["run"], event["path"]), ({}, []))
            group[0].update(rounds)
            group[1].append(event)
    for rounds, group in groups.values():
        built = [_rebuild(md, n, rounds[(at, md, n)], tree) for at, md, n in sorted(rounds)]
        for index, event in enumerate(group):
            event["prompts"] = [built[index]] if len(group) == len(built) else built


def _rebuild(md: str, n: int, path: Path, tree: Path) -> dict:
    try:
        kept = json.loads(path.read_text(encoding="utf-8"))
        built = prompt.compose(tree / kept["block"], kept["node"], kept["values"], kept["when"], shared_root=tree / ports.SHARED.name)
    except (OSError, ValueError, KeyError, TypeError) as error:   # PromptError は ValueError の子
        return {"md": md, "n": n, "ja": {}, "error": f"{path.name} から組めない（{error}）"}
    return {"md": md, "n": n, "ja": built, "error": ""}


def _session_marks(run: dict | None) -> list[str]:
    marks = []
    for got in ((run or {}).get("sessions") or {}).values():
        marks += got["system"] + [i[1] for i in got["inject"]] + [row[1] for row in got["seq"] if row[0] == "user"]
    return list(dict.fromkeys(marks))


def _parse(text: str) -> dict[str, str]:
    parts = SEP.split(text)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def _load(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _save(path: Path, got: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(got.items())), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
