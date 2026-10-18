"""固定材料（元 works/.shared/core/fixture.py）: 修正の前の run の置き場を写し、次の run が同じ所（判定・承認済みの修正案が済み、
修正を待つ所）から始める。同じ依頼を同じ起点から回し直し、修正の段だけを比べるのに使う。lib からは startrec・oneline だけを import する。

語:
- 固定材料: <run の置き場>/DIR/ のフォルダ。中身は次の 2 つ。
  - COPY（place/）: 写した時の run の置き場を丸ごと写した物（DIR 自身を除く）。
  - MANIFEST（fixture.json）: 控え。{format, source_run, head, tree, place_root, repo_root, request_sha256, commits: {commit: 木},
    files: {DIR からの相対パス: sha256}, carried}。時刻を書かない。
    - format は固定材料の形の版（FORMAT）。運ぶ値の欄・置き場の形を変える時に上げ、違う版の固定材料は取り込まない。
    - head・tree は写した時の作業ツリーの `git rev-parse HEAD`・`HEAD^{tree}`。place_root・repo_root は写した run の置き場と作業ツリー。
    - request_sha256 は始めの記録の依頼のファイルの文の sha256（依頼が無ければ空の文の sha256）。
    - commits は写しの字に現れる commit（HEAD を除く）とその木。
    - carried は修正の段へ運ぶ値（呼び手が渡す JSON の値。中身はこのモジュールが決めない）。
- 取り込みの決まりは 1 つ: 写しの字のうち取り込み先で違う物は、新しい値に置き換える。
  - 置き場のパス（渡された字と resolve した字の両方）・run の id・HEAD を新しい値にする。
  - commit: 対象に無い commit は同じ木で作り直し（親は今の HEAD）、名を置き換える。木も無ければ拒む。
- 控えの照らしは手の誤り（写しの書き換え・欠け）を防ぐ物。写しと控えの両方を揃えて書き換えた物は見分けない。
- 作業ツリーの汚れは照らさない（元は照らした）。run の作業ツリーは起動が対象の今の姿から切った commit から新しく作られるので、
  取り込む時に汚れは無い。汚れた対象は包んだ commit が run ごとに変わるが、木は同じなので tree の照らしと HEAD の置き換えで足りる。

口:
- capture(place, repo, *, run_id, carried): 固定材料を作って控えを返す。控えが既に在れば何も書かずにそれを返す。
- noted_capture(place, repo, *, run_id, carried): capture の結果を始めの記録の CAPTURED_KEY {dir, error} に書く。落ちない
- adopt(place, src, repo, *, run_id, inputs, request_text): 固定材料 src を place へ取り込み、(書き換えた始めの記録, 書き換えた
  carried) を返す。carried は place の CARRIED にも置く。合わなければ FixtureRefused（何が違うかを名指す 1 行）。拒む時は何も書かない
- lines(doc): 始めの記録 doc の固定材料の行（取り込んだ run・写した run。起動の承認ノードの文と報告の入口が同じ字を出す）
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess

import oneline
import startrec

DIR = "fix-fixture"              # run の置き場の下
MANIFEST = "fixture.json"        # DIR の下の控え
COPY = "place"                   # DIR の下の run の置き場の写し
CARRIED = "fixture-carried.json"  # 取り込んだ run の置き場の根の、書き換えた carried
FORMAT = 8                       # 8: 7（5 の計画と修正の控えの出力の欄〔#681〕に、直す前のテストの受け皿の欄 optional〔#516〕と事前審査の隣のファイルの出力の欄〔#723〕を重ねた形）に、構造の目の控えを計画から分けたブロックの受け皿で運ぶ形（#560）を重ねた
KEY = "fixture"                  # 始めの記録の鍵 {source_run, manifest_sha256, at}（取り込んだ run の印）
CAPTURED_KEY = "fixture_captured"  # 始めの記録の鍵 {dir, error}（写した run の印）
# 取り込みで今の値にする入力の欄（ほかの入力の欄は写した始めの記録と今の入力が同じでなければ拒む）。request は名指しの字が違っても
# よい（中身は request_sha256 で照らす）。features_off・features_on は同じ所から替えて比べる欄（判定・修正案の側の機能は写しの物の
# ままで、修正の段から後ろの機能だけが効く）。deliver は封じた後の渡し方だけを変え、写しの中身に効かない
CURRENT = ("fix_fixture", "request", "features_off", "features_on", "deliver")
_STR_KEYS = ("source_run", "head", "tree", "place_root", "repo_root", "request_sha256")
_MAP_KEYS = ("commits", "files")
HEX40 = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")   # 写しの字の中の commit の名の候補
# 作り直す commit の作者（利用者の設定に左右されない）
SNAPSHOT_IDENT = {"GIT_AUTHOR_NAME": "works-fixture", "GIT_AUTHOR_EMAIL": "works-fixture@localhost",
                  "GIT_COMMITTER_NAME": "works-fixture", "GIT_COMMITTER_EMAIL": "works-fixture@localhost"}


class FixtureRefused(Exception):
    """固定材料を取り込まない。文は何が違うかを名指す 1 行"""

    def __init__(self, msg):
        super().__init__(oneline.one_line(msg))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _files(root: pathlib.Path) -> dict:
    """root の下の全部のファイル（MANIFEST を除く）の {相対パス（/ 区切り）: sha256}"""
    return {p.relative_to(root).as_posix(): _sha(p.read_bytes()) for p in sorted(root.rglob("*"))
            if p.is_file() and p.relative_to(root).as_posix() != MANIFEST}


def _git(repo, *args, stdin: str | None = None, env: dict | None = None) -> str:
    """対象で git を呼ぶ。引けなければ OSError（写す側は run を止めない・取り込む側は拒みに替える）"""
    got = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", input=stdin,
                         env={**os.environ, **env} if env else None)
    if got.returncode != 0:
        raise OSError(f"git {' '.join(args)} が引けない: {got.stderr.strip() or got.returncode}")
    return got.stdout.strip()


def _lacking(repo, names: list) -> set:
    """names（`<名>^{commit}` などの git の名）のうち対象に無い物（git cat-file --batch-check を 1 回）"""
    if not names:
        return set()
    rows = _git(repo, "cat-file", "--batch-check", stdin="\n".join(names) + "\n").splitlines()
    return {n for n, r in zip(names, rows) if r.endswith(" missing")}


def _texts(root: pathlib.Path):
    """root の下の UTF-8 で読めるファイルの (パス, 文)"""
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        try:
            yield p, p.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue


def _commits(texts: list, repo, head: str) -> dict:
    """texts に現れる commit（HEAD を除く）の {commit: 木}"""
    names = [f"{n}^{{commit}}" for n in sorted({m for text in texts for m in HEX40.findall(text)} - {head})]
    lack = _lacking(repo, names)
    return {n[:40]: _git(repo, "rev-parse", f"{n[:40]}^{{tree}}") for n in names if n not in lack}


def _write_json(path: pathlib.Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _request_sha(place: pathlib.Path) -> str:
    """始めの記録の依頼のファイルの文の sha256（取り込む側は start が読んだ依頼の文で同じ式を引く）。依頼が無ければ空の文の sha256"""
    named = startrec.request_file(startrec.read(place))
    return _sha((pathlib.Path(named).read_text(encoding="utf-8") if named else "").encode("utf-8"))


def capture(place, repo, *, run_id: str, carried) -> dict:
    """run の置き場 place を place/DIR/COPY へ写し（DIR を除く）、MANIFEST を書いて返す。MANIFEST が既に在れば書き直さずに返す。
    写しの途中で落ちた残り（MANIFEST の無い DIR）は消して写し直す。控えは最後に置く
    （控えが在れば写しは揃っている）"""
    given = pathlib.Path(place)
    dest = given / DIR
    man_path = dest / MANIFEST
    if man_path.is_file():
        return json.loads(man_path.read_text(encoding="utf-8"))
    request_sha = _request_sha(given)
    head, tree = _git(repo, "rev-parse", "HEAD"), _git(repo, "rev-parse", "HEAD^{tree}")
    if dest.exists():
        shutil.rmtree(dest)
    top = given.resolve()
    shutil.copytree(given, dest / COPY, ignore=lambda d, names: [DIR] if pathlib.Path(d).resolve() == top else [])
    texts = [t for _, t in _texts(dest / COPY)] + [json.dumps(carried, ensure_ascii=False)]
    man = {"format": FORMAT, "source_run": run_id, "head": head, "tree": tree, "place_root": str(given),
           "repo_root": str(pathlib.Path(repo)), "request_sha256": request_sha, "commits": _commits(texts, repo, head),
           "files": _files(dest), "carried": carried}
    _write_json(man_path, man)
    return man


def noted_capture(place, repo, *, run_id: str, carried) -> None:
    """capture を呼び、写したフォルダか写せなかった訳を始めの記録の CAPTURED_KEY {dir, error} に書く。写せなくても落ちない
    （固定材料は比べるための道具で、run を止める訳にしない）。始めの記録の無い置き場は何も書かない"""
    try:
        capture(place, repo, run_id=run_id, carried=carried)
        note = {"dir": str(pathlib.Path(place) / DIR), "error": ""}
    except (OSError, ValueError) as e:
        note = {"dir": "", "error": oneline.one_line(f"{type(e).__name__}: {e}")}
    if not startrec.path(place).is_file():
        return
    doc = startrec.read(place)
    doc[CAPTURED_KEY] = note
    startrec.write(place, doc)


def _manifest(src: pathlib.Path) -> tuple:
    """(控え, 控えのバイトの sha256)。無い・読めない・版が違う・欄の型が違えば FixtureRefused"""
    path = src / MANIFEST
    try:
        raw = path.read_bytes()
        man = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as e:
        raise FixtureRefused(f"固定材料の控え {path} が無いか読めない（{type(e).__name__}: {e}）") from None
    if not isinstance(man, dict):
        raise FixtureRefused(f"固定材料の控え {path} が JSON の object でない")
    if man.get("format") != FORMAT:
        raise FixtureRefused(f"固定材料 {src} は前の版の固定材料（形の版 {man.get('format')!r}。今の版は {FORMAT}）"
                             "——この版の works で写し直す")
    ok = all(isinstance(man.get(k), str) for k in _STR_KEYS) and all(
        isinstance(man.get(k), dict) and all(isinstance(a, str) and isinstance(b, str) for a, b in man[k].items())
        for k in _MAP_KEYS) and "carried" in man
    if not ok:
        raise FixtureRefused(f"固定材料の控え {path} の欄の型が違う（{', '.join(_STR_KEYS)} は文字列、"
                             f"{', '.join(_MAP_KEYS)} は文字列から文字列への辞書、carried が要る）")
    return man, _sha(raw)


def _check_copy(src: pathlib.Path, man: dict) -> None:
    """固定材料のファイルが控えの sha256 と同じか。違う・足りない・多いファイルを名指して FixtureRefused"""
    got = _files(src)
    changed = sorted(p for p in got.keys() & man["files"].keys() if got[p] != man["files"][p])
    missing = sorted(man["files"].keys() - got.keys())
    extra = sorted(got.keys() - man["files"].keys())
    parts = [f"{what}: {', '.join(ps)}" for what, ps in (("書き換わった", changed), ("足りない", missing), ("多い", extra)) if ps]
    if parts:
        raise FixtureRefused(f"固定材料 {src} が控えと違う（{'・'.join(parts)}）——写した後に書き換えた写しは取り込まない")
    if f"{COPY}/{startrec.REL}" not in man["files"]:
        raise FixtureRefused(f"固定材料 {src} に始めの記録 {COPY}/{startrec.REL} が無い")


def _check_repo(repo, man: dict) -> tuple:
    """対象の木が控えの木と同じで、作り直せない commit が無いか。通れば (今の HEAD, 作り直す commit)"""
    try:
        tree, head = _git(repo, "rev-parse", "HEAD^{tree}"), _git(repo, "rev-parse", "HEAD")
        lack = _lacking(repo, [f"{c}^{{commit}}" for c in man["commits"]] + [f"{t}^{{tree}}" for t in man["commits"].values()])
    except OSError as e:
        raise FixtureRefused(f"対象 {repo} の git を読めない: {e}") from None
    if tree != man["tree"]:
        raise FixtureRefused(f"対象の木（HEAD^{{tree}} {tree[:12]}）が固定材料の tree {man['tree'][:12]} と違う"
                             "——対象の中身が写した時と違う")
    remake = {c: t for c, t in man["commits"].items() if f"{c}^{{commit}}" in lack}
    stuck = sorted(c for c, t in remake.items() if f"{t}^{{tree}}" in lack)
    if stuck:
        raise FixtureRefused(f"写しが指す commit {', '.join(c[:12] for c in stuck)} もその木も対象に無い——作り直せない")
    return head, remake


def _remade(repo, remake: dict, head: str) -> dict:
    """対象に無い commit を同じ木・親を今の HEAD にして作り直す。{古い commit: 新しい commit}"""
    out = {}
    for rev, rev_tree in remake.items():
        try:
            out[rev] = _git(repo, "commit-tree", rev_tree, "-p", head, "-m", f"works fix-fixture: {rev}", env=SNAPSHOT_IDENT)
        except OSError as e:
            raise FixtureRefused(f"写しが指す commit {rev[:12]} を対象に作り直せない: {e}") from None
    return out


def _paths(old: str, new) -> dict:
    """置き場のパスの置き換え: 渡された字と resolve した字の両方（macOS の /var と /private/var のように、同じ所が 2 つの字で
    書かれていても外れないように）"""
    new = pathlib.Path(new)
    return {old: str(new), str(pathlib.Path(old).resolve()): str(new.resolve())}


def _swapper(swap: dict):
    """文の中の swap の字（古い値）を新しい値に 1 度で置き換える関数（長い字から当てる。置き換えた字をもう 1 度置き換えない）"""
    olds = sorted((o for o, n in swap.items() if o and o != n), key=len, reverse=True)
    if not olds:
        return lambda text: text
    pat = re.compile("|".join(re.escape(o) for o in olds))
    return lambda text: pat.sub(lambda m: swap[m.group(0)], text)


def _rewrite(paths, swap: dict) -> None:
    """paths のうち UTF-8 で読めるファイルの中の字を _swapper で置き換える。読めないファイルはそのまま"""
    fn = _swapper(swap)
    for p in paths:
        try:
            text = p.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        new = fn(text)
        if new != text:
            p.write_text(new, encoding="utf-8")


def adopt(place, src, repo, *, run_id: str, inputs: dict, request_text: str) -> tuple:
    """固定材料 src（DIR のフォルダ）を run の置き場 place へ取り込み、(始めの記録, carried) を返す。始めの記録は写しの物の字を置き換え、
    run_id・inputs（今の入力）・KEY を今の値にした dict（書くのは呼び手）。carried は字を置き換えて place/CARRIED に置く。
    拒む物（FixtureRefused。何も書かない）: 控えが無い・読めない・版が違う・欄の型が違う／ファイルの sha256 が違う・足りない・多い／
    place に始めの記録が既に在る／今の HEAD^{tree} が控えの tree と違う／写しが指す commit もその木も対象に無い／request_text の
    sha256 が違う／写した始めの記録の入力の欄が inputs と違う（CURRENT の欄を除く。名指す）"""
    src, place = pathlib.Path(src), pathlib.Path(place)
    man, man_sha = _manifest(src)
    _check_copy(src, man)
    if startrec.path(place).exists():
        raise FixtureRefused(f"取り込む先の run の置き場 {place} に始めの記録が既に在る——固定材料は始めたばかりの run にだけ取り込む")
    head, remake = _check_repo(repo, man)
    if _sha(request_text.encode("utf-8")) != man["request_sha256"]:
        raise FixtureRefused("依頼の文の sha256 が固定材料と違う——同じ依頼の run だけが固定材料から始める")
    swap = {**_paths(man["place_root"], place), **_paths(man["repo_root"], repo), man["source_run"]: run_id, man["head"]: head}
    doc = json.loads(_swapper(swap)((src / COPY / startrec.REL).read_text(encoding="utf-8")))
    before = doc.get("inputs") if isinstance(doc.get("inputs"), dict) else {}
    bad = sorted(k for k, v in inputs.items() if k not in CURRENT and before.get(k) != v)
    if bad:
        raise FixtureRefused("写した始めの記録の入力が今の入力と違う: " + "・".join(f"{k}={before.get(k)!r}→{inputs[k]!r}" for k in bad)
                             + "（同じ入力の run だけが固定材料から始める。今の値にするのは " + "・".join(CURRENT) + " だけ）")
    swap.update(_remade(repo, remake, head))
    shutil.copytree(src / COPY, place, dirs_exist_ok=True)
    copied = [place / rel.removeprefix(f"{COPY}/") for rel in man["files"] if rel.startswith(f"{COPY}/")]
    _rewrite(copied, swap)
    carried = json.loads(_swapper(swap)(json.dumps(man["carried"], ensure_ascii=False)))
    _write_json(place / CARRIED, carried)
    doc = startrec.load(startrec.path(place))
    doc.update({"run_id": run_id, "inputs": inputs,
                KEY: {"source_run": man["source_run"], "manifest_sha256": man_sha,
                      "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}})
    return doc, carried


def lines(doc: dict) -> list:
    """始めの記録 doc の固定材料の行: 取り込んだ印（KEY）と写した印（CAPTURED_KEY）。どちらも無ければ空"""
    out = []
    mark = doc.get(KEY) if isinstance(doc, dict) else None
    if isinstance(mark, dict):
        out.append(f"固定材料から: run {mark.get('source_run') or '—'} の修正の前の写し（判定・修正案・直す前のテスト・修正前の承認の"
                   "答えは写しの物。役は修正から起こす）")
    note = doc.get(CAPTURED_KEY) if isinstance(doc, dict) else None
    if isinstance(note, dict):
        out.append(f"固定材料: {note.get('dir')}（次の run の入力 fix_fixture に渡すと、判定と修正案を作り直さずに修正から始める）"
                   if note.get("dir") else f"固定材料を写せなかった: {note.get('error') or '訳が無い'}")
    return out
