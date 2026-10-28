"""名指しの出どころが現物に在るかの確かめ（食い違いの申し出の引用の照らしと、修正前の関所の決め手の出どころの照らしが使う 1 か所）。

- CITE: 名指し `<パス>:<行>` か `<パス>:<行>-<行>` の形
- QUOTE_MIN: 引用の字数の下限（引用「…」の形 QUOTE と headdepth が使う。tddloop.MIN_QUOTE は別の下限）
- inside(p, root): p が root の中か
- resolved(path, repo) -> Path: 名指しのパスの実体（problem と、世界の解の外れの依頼のファイルの照らしが同じ規則で解く）
- problem(cite, repo, roots=()) -> str: 1 つの名指しの確かめ（通れば空）。相対のパスは作業ツリーの根から（外と .git は拒む）、
  絶対のパスは作業ツリーの中か roots（呼び手が渡す作業ツリーの外の根。conflict.cite_roots）の中だけ。ファイルが在り、行がその中に在る
- file_problem(path, repo, roots=(), label=None) -> str: 行の無いパス 1 つの確かめ（problem のパスとファイルの規則。通れば空）
- RUN_FILES: 決め手の出どころの書き方のうち run の置き場のファイルの引き方（関所の決め手の欄と修正案の欄 structure の頼みに貼る 1 文）
- flat(s) -> str: 空白の並び（改行・タブ・連続する空白）を 1 つの空白に寄せ、色の制御文字（ESC[…m）を除いた文
- quoted_in(quote, text, norm=flat) -> bool: 引いた文 quote が text の中に、両側を norm で寄せた後の部分一致で在るか（寄せて空に
  なる引用は偽。字数の下限は無い）。引用 1 つの照らしの 1 か所。既定の flat はテストの赤の引用が結末の失敗の文に在るかの照らし
  （実行器の出力は改行・色の付き方が回ごとに違いうる）。独立設計の対応表の design_quote は fold、missing_quotes も中でこれを呼ぶ
- sources_problem(text, repo, roots=(), quoted="") -> str: 決め手の文（decided_by）の出どころの確かめ（通れば空）。文の中の
  URL（http・https。形だけ見る。取りに行かない）・名指し `<パス>:<行>`（problem）・作業ツリーの中のパス（/ を含むか拡張子を持つ語で、
  在るファイル。フォルダだけは出どころに数えない）・依頼の引用「…」（文に「依頼」の語が在る時だけ。quoted＝依頼の文の中に字のまま
  在る）のどれかが 1 つ以上在り、書いた物が全部現物に在る時だけ通る。どれも無ければ「出どころが現物に無い」。
  パスの形でない名指し（時刻 12:30 など。パスの部分に / も拡張子も無い）は名指しに数えない
- fold(text)・quotes(text)・missing_quotes(text, source, folded=True) -> list[str]: 引用「…」の照らし（sources_problem の依頼の
  引用と、独立設計の引用の照らしが使う 1 か所）。fold は NFKC にして空白を 1 つに畳む。missing_quotes は text の引用のうち、source に
  quoted_in でない物。folded が真（既定）なら両側を fold してから照らす（独立設計の引用）。偽なら字のまま（sources_problem の依頼の
  引用は偽。関所の決め手の照らしを緩めない）
- unspaced(text) -> str: fold の後に空白を全部除いた物（design.py の拒みの行が、貼った字の出どころを見分けるのに使う）
- ref_problem(source, prefix, known) -> list[str]: 出どころの文の中の prefix で始まる参照（頭に字が添えてあってもよい）の id が、
  呼び手が渡した実在の id の組 known に在るかの照らし。無い id ごとに誤りの 1 文（prefix の語が無ければ空）

- named_files(text) -> list[str]: 文の中で名指されたファイルのパス（URL を除き、`<パス>:<行>` の行を外す。/ を含み、最後の段が
  名.拡張子の形の語だけ。出た順・重なりなし）。人の答えや指示ファイルが指した文書を拾う 1 か所
- elsewhere(repo, rev, paths) -> list[dict]: paths のうち版 rev に無いファイルごとに、ほかの版（git の全部の ref）で探した行
  {path, found, commit, at, text}（どの ref にも無ければ found・commit・at・text は空）。修正案（人の答えが指した文書）と構造の目
  （指示ファイルが指した文書）が使う

- CITE_IN_WHERE: 場所の文の中の名指し 1 つ分の形（CITE の錨を外した物。パスは空でもよい）
- where_cites(where) -> [(パス, 始め, 終わり)]: 場所の文の中の名指しを順に返す。パスの無い `:<行>` は直前のパス、直前が無ければ空

指し先の綴りと版に在るかの照らし（前は judge_accept・boardview に在り recount が遅れて読んでいた。README 9.3 の「指し先の照らし」の
1 か所。integration.md 4.3-4・4.5-5。使い手は recount〔fix・delta-review〕と purpose・diagnose・independent-design・design）:
- EMPTY・blank(s, min_len): 役が埋める自由文が空同然か（表と長さの両方で見る）
- Reject: 確かめられないものを拒む例外（engine.util.Reject と同じ物）
- _in_version(rels)・_resolve_target(tgt, root)・_not_in_version(full): 指し先の候補を版の一覧で引く・役が書いたパスをリポジトリ
  相対の正規形に解く・版に無いパスの事実どおりの理由
- CITE_LABELS・_cite_errors(jdir, nid, rows, rev, label): 申告された字列を現物で数え直す（findings は版 rev 全体、wrote_refs は
  作業ツリーの指し先の中）。git の向き先は呼び手が accept.in_repo で決める
- _precedent_gap(r): 先行例の 1 行に足りない物（判定者の行と修正役の行が同じ規則を使う）
- MD_LINK・MD_FENCE・_md_lines(text)・_md_slugs(text): Markdown のリンクの形・コードブロックの外の行・見出しのアンカー（GitHub の書き方）

標準ライブラリと、写しの engine の小道具 engine.util（git・grep・読了の印）だけ。works の物を何も import しない（読み手が多いので
輪を作らない）。
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import unicodedata

_GL = pathlib.Path(__file__).resolve().parent / "graphloops"
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

from engine.util import (READ_CAP, Reject, _grep as grep, git, hook_evidence, read_capped, repo_root,  # noqa: E402
                         sum_counts)

EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")   # 「書いていない」と同じ扱いにする語（元 review-loop.py:467）

CITE = re.compile(r"^(?P<path>.+?):(?P<a>[1-9][0-9]*)(?:-(?P<b>[1-9][0-9]*))?$")
CITE_IN_WHERE = re.compile(r"(?P<path>[^\s:：（()、,]*):(?P<a>[1-9][0-9]*)(?:-(?P<b>[1-9][0-9]*))?")
URL = re.compile(r"https?://[^\s）)」』、。,]+")
QUOTE_MIN = 4   # 短い字はどの文にも当たる
QUOTE = re.compile(rf"「([^」]{{{QUOTE_MIN},}})」")
TOKEN = re.compile(r"/?[A-Za-z0-9_.][A-Za-z0-9_./-]*(?::[1-9][0-9]*(?:-[1-9][0-9]*)?)?")
REQUEST_WORD = "依頼"   # 引用「…」を依頼の文と照らすのは、この語が文に在る時だけ（出典の文書の引用は照らさない）
ANSI = re.compile(r"\x1b\[[0-9;]*m")
RUN_FILES = ("run の置き場のファイル（指示書の brief・判定の judgment.json・控え）は作業ツリーの外なので、絶対パス:<行> で引け"
             "（素の名・相対のパスは作業ツリーの根から引くので、作業ツリーに無ければ出どころが現物に無いと読まれて人に回る）")
NO_SOURCE = "決め手の出どころが現物に無い（パス:行・URL・依頼の引用「…」・設計の決定の記録のパスのどれも書いていない）"


def inside(p: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def resolved(path, repo) -> pathlib.Path:
    """名指しのパスの実体（相対は作業ツリーの根 repo から。. と .. の段と symlink を解く）"""
    raw = pathlib.Path(path)
    return (raw if raw.is_absolute() else pathlib.Path(repo) / raw).resolve()


def file_problem(path, repo, roots=(), *, label=None) -> str:
    """行の無いパス 1 つの確かめ（通れば空。problem のパスの規則）。label は誤りの文に出す名指し（既定は path）"""
    label = path if label is None else label
    repo = pathlib.Path(repo).resolve()
    p = resolved(path, repo)
    allowed = [repo] + [pathlib.Path(r).resolve() for r in roots if r]
    if not any(p == r or inside(p, r) for r in allowed) or inside(p, repo / ".git"):
        return f"名指し {label!r} のパスが作業ツリー・依頼のファイル・共有ボードの外"
    if not p.is_file():
        return f"名指し {label!r} のファイルが無い"
    return ""


def problem(cite, repo, roots=()) -> str:
    """名指し `<パス>:<行>` か `<パス>:<行>-<行>` の確かめ（通れば空）"""
    if not isinstance(cite, str):
        return f"名指し {cite!r} が文字列でない"
    m = CITE.match(cite.strip())
    if not m:
        return f"名指し {cite!r} が <パス>:<行> の形でない（例 tests/test_x.py:12・src/x.py:30-34・依頼のファイルの絶対パス:3）"
    a, b = int(m["a"]), int(m["b"] or m["a"])
    if b < a:
        return f"名指し {cite!r} の行の範囲が逆"
    bad = file_problem(m["path"], repo, roots, label=cite)
    if bad:
        return bad
    p = resolved(m["path"], repo)
    try:
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError as e:
        return f"名指し {cite!r} のファイルが読めない（{type(e).__name__}）"
    if b > n:
        return f"名指し {cite!r} の行がファイルに無い（{n} 行しか無い）"
    return ""


def where_cites(where) -> list:
    """場所の文の中の名指しを順に [(パス, 始め, 終わり)] で返す（始め・終わりは字。終わりの無い名指しは None）。
    パスの無い `:<行>` は直前の名指しのパス、直前が無ければパスは空"""
    out, last = [], ""
    for m in CITE_IN_WHERE.finditer(where):
        last = m["path"] or last
        out.append((last, m["a"], m["b"]))
    return out


def flat(s) -> str:
    """空白の並びを 1 つの空白に寄せ、色の制御文字（ESC[…m）を除く。文字列でなければ空"""
    return " ".join(ANSI.sub("", s).split()) if isinstance(s, str) else ""


def quoted_in(quote, text, *, norm=flat) -> bool:
    """引いた文 quote が text の中に、両側を norm（flat・fold・字のままの str）で寄せた後の部分一致で在るか（寄せて空になる引用は偽）"""
    q = norm(quote)
    return bool(q.strip()) and q in norm(text)


def _pathish(word: str) -> bool:
    last = word.rsplit("/", 1)[-1]
    return ("/" in word or bool(re.fullmatch(r"[^.]+\.[A-Za-z][A-Za-z0-9]{0,5}", last))) and not word.startswith(".") \
        and not word.startswith("/")


NAME_EXT = re.compile(r"[^/]+\.[A-Za-z][A-Za-z0-9]{0,5}")   # named_files が数える最後の段の形（名.拡張子）


def named_files(text) -> list:
    """文 text の中で名指されたファイルのパス（出た順・重なりなし）。URL を除き、`<パス>:<行>` は行を外し、頭の ./ を外す。/ を含み、
    / で始まらず、.. の段を持たず、最後の段が名.拡張子の形の語だけ（フォルダ・枝の名・素の名は数えない）"""
    if not isinstance(text, str):
        return []
    out = []
    for word in TOKEN.findall(URL.sub(" ", text)):
        word = word.rstrip(".")
        m = CITE.match(word)
        path = (m["path"] if m else word).removeprefix("./")
        parts = path.split("/")
        if len(parts) > 1 and parts[0] and ".." not in parts and NAME_EXT.fullmatch(parts[-1]) and path not in out:
            out.append(path)
    return out


def _git_out(repo, *args) -> str | None:
    """repo で git を起こした標準出力（失敗は None）"""
    try:
        p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL)
    except OSError:
        return None
    return p.stdout if p.returncode == 0 else None


def _in(tracked: set, path: str) -> bool:
    """path か、それで終わるパス（/ の境で）が tracked に在るか（指示ファイルがフォルダからの相対で書いた名を、無いと読まない）"""
    return path in tracked or any(t.endswith("/" + path) for t in tracked)


def elsewhere(repo, rev: str, paths) -> list:
    """paths のうち版 rev に無いファイルごとに {path, found, commit, at, text}（paths の順）。版に在るかは、そのパスか、それで終わるパス
    （/ の境で）が rev に追跡されているかで見る。無い物は git の全部の ref の中で、そのパス（か、それで終わるパス）を最後に足した・
    変えた commit を探し、在れば found（その commit の中のパス）・commit（hash）・at（git name-rev の名。どの ref から辿れるか。
    名が付かなければ空）・text（その commit の本文）。どの ref にも無ければ found・commit・at・text は空。rev が読めなければ OSError"""
    listed = _git_out(repo, "ls-tree", "-r", "--name-only", rev)
    if listed is None:
        raise OSError(f"版 {rev} のファイルの一覧を git で読めない")
    tracked = set(listed.splitlines())
    out = []
    for path in paths:
        if _in(tracked, path):
            continue
        row = {"path": path, "found": "", "commit": "", "at": "", "text": ""}
        specs = [f":(literal){path}"] + ([] if any(c in path for c in "*?[\\") else [f":(glob)**/{path}"])
        got = _git_out(repo, "log", "--all", "-1", "--format=%H", "--name-only", "--diff-filter=AMR", "--", *specs) or ""
        lines = [ln for ln in got.splitlines() if ln.strip()]
        found = next((ln for ln in lines[1:] if ln == path or ln.endswith("/" + path)), "")
        text = _git_out(repo, "show", f"{lines[0]}:{found}") if found else None
        if text is not None:
            at = (_git_out(repo, "name-rev", "--name-only", "--no-undefined", lines[0]) or "").strip()
            row.update(found=found, commit=lines[0], at=at, text=text)
        out.append(row)
    return out


def fold(text) -> str:
    """引用の照らしの前に両側へ掛ける畳み: NFKC にし、空白（改行・タブ含む）の並びを 1 つの半角空白にして前後を除く"""
    return " ".join(unicodedata.normalize("NFKC", str(text)).split())


def unspaced(text) -> str:
    """fold の後に空白を全部除いた物（空白の置き方だけが違う字を同じと見る見分けに使う。受け付けの照らしには使わない）"""
    return "".join(fold(text).split())


def quotes(text) -> list:
    """文の中の引用「…」（4 字以上。前後の空白を除く）を出た順に"""
    return [q.strip() for q in QUOTE.findall(text)] if isinstance(text, str) else []


def missing_quotes(text, source, *, folded: bool = True) -> list:
    """text の引用「…」のうち、source に quoted_in でない物を出た順に（無ければ空）。folded が真なら両側に fold を掛けて照らし、
    偽なら字のまま（全角と半角・空白の違いも別の字と数える）"""
    norm = fold if folded else str
    return [q for q in quotes(text) if not quoted_in(q, source, norm=norm)]


def sources_problem(text, repo, roots=(), quoted: str = "") -> str:
    if not isinstance(text, str) or not text.strip():
        return NO_SOURCE
    found, bad = 0, []
    rest = URL.sub(" ", text)
    found += len(URL.findall(text))
    if REQUEST_WORD in rest:
        found += len(QUOTE.findall(rest))
        bad += [f"依頼の引用「{q}」が依頼の文に無い" for q in missing_quotes(rest, quoted, folded=False)]
    rest = QUOTE.sub(" ", rest)
    repo_p = pathlib.Path(repo).resolve()
    for word in TOKEN.findall(rest):
        word = word.rstrip(".")
        m = CITE.match(word)
        if m and (_pathish(m["path"]) or m["path"].startswith("/")):
            found += 1
            got = problem(word, repo_p, roots)
            if got:
                bad.append(got)
        elif not m and _pathish(word):
            p = (repo_p / word).resolve()
            if inside(p, repo_p) and p.is_file():
                found += 1
    if bad:
        return "決め手の出どころが現物に無い: " + " / ".join(bad)
    return "" if found else NO_SOURCE


def ref_problem(source, prefix, known) -> list:
    """出どころの文（source）の中の prefix で始まる参照（頭に字が添えてあってもよい）の id を、呼び手が渡した実在の id の組（known）と
    照らす。無い id ごとに誤りの 1 文を返す（prefix の語が無ければ空）。頭の字と id の組は、この住処が works の物を知らないよう呼び手が渡す"""
    if not isinstance(source, str):
        return []
    ids = dict.fromkeys(re.findall(re.escape(prefix) + r"([A-Za-z0-9][A-Za-z0-9_-]*)", source))
    return [f"{prefix}{i} が実在の行を指さない" for i in ids if i not in known]


# ---------------------------------------------------------------- 指し先の綴りと版（元 judge_accept。名は元のまま）
def blank(s, min_len) -> bool:
    """役が埋める自由文が「空同然」か（表と長さの両方で見る）。元 works/.shared/core/graphloops/rules/review-loop.py:480"""
    t = (s or "").strip() if isinstance(s, str) else ""
    return t.lower() in EMPTY or len(t) < min_len


def _repo_root():
    """元 rules:3297。対象リポジトリのルート（engine.util の git の向き先。accept.in_repo で向ける）"""
    return repo_root(git)


def _grep_count(cite_, rev):
    """元 rules:3372。固めた版に対する `git grep -F -cI`（字面として数える）。（`…:数` の文字列, ""）か（None, 理由）"""
    root = _repo_root()
    if root is None:
        return None, "git が動かない"
    return grep(["git", "grep", "-F", "-cI", "-e", cite_, rev, "--", ":(top)"], root)


def _in_version(rels):
    """元 rules:3395。指し先の候補を版の一覧で引く——{rel: "text" | "binary"}（無い rel は入らない）。git が動かなければ None"""
    got = git("ls-files", "-z", "--full-name", "--cached", "--others", "--exclude-standard", "--eol",
              "--", *[f":(top,literal){r}" for r in rels])
    if got is None:
        return None
    want, found = set(rels), {}
    for ent in got.split("\0"):
        meta, sep, path = ent.partition("\t")
        if sep and path in want:
            found[path] = "binary" if "w/-text" in meta.split() else "text"
    return found


def _resolve_target(tgt, root):
    """元 rules:3422。役が書いたパス 1 つを、リポジトリ相対の正規形 1 つに解く ——（rel, 理由）。綴りが正規形と違えば拒む"""
    rootp = pathlib.Path(root).resolve()
    try:
        real = (rootp / tgt).resolve()
        rel = real.relative_to(rootp).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None, "リポジトリの外を指している（リポジトリ相対のパスで書け。絶対パスや '..' で外へ出る指しは受け取らない）"
    if rel != tgt:
        return None, f"正規形で書け: '{rel}'（'./' 付き・'..' で戻る綴り・symlink 経由は、指し先が 1 つに決まらない）"
    return rel, ""


def _not_in_version(full):
    """元 rules:3447。版に無いパスの、事実どおりの理由（拒否文の後半）"""
    if full.is_dir():
        return "通常のファイルでない（ディレクトリなど）——ファイルを 1 つ指せ"
    if full.exists() and not full.is_file():
        return "通常のファイルでない（FIFO・ソケットなど）——ファイルを 1 つ指せ"
    if full.exists() or full.is_symlink():
        return ("在るが版の一覧に出ない（.gitignore に当たる・綴りの大文字小文字が違う・サブモジュールの中、など）——次の周に"
                "指摘側が数える版にもコミットにも入らない指し先は、他の人の手元に存在しない。リポジトリの一覧に在る綴りの、版に入るファイルを指せ")
    return "いまの作業ツリーに無い——ファイルを 1 つ指せ（綴りを確かめるか、先に作れ）"


# 元 rules:3467
CITE_LABELS = {"findings": {"what": "指摘の根拠", "target": False},
               "wrote_refs": {"what": "修正が書いた指し", "target": True}}


def _cite_errors(jdir, nid, rows, rev, label):
    """元 rules:3471。申告された字列を、現物で数え直す ——（errs, reads）。盤面の b.dir（読了の記録の置き場）は置き場 jdir に読み替えた。
    findings（指し先を持たない）は版 rev 全体を数えて件数の申告（hits）と突き合わせ、wrote_refs（指し先を持つ）は作業ツリーの
    指し先のファイルの中だけを数える。git の向き先は呼び手が accept.in_repo で決める"""
    kind = CITE_LABELS[label]
    what = kind["what"]
    if kind["target"] and rev:
        raise ValueError(f"{label}: 指し先を持つ呼び元は作業ツリーを数える（版 {rev[:12]} を渡された）")
    if not kind["target"] and not rev:
        raise Reject(f"{nid}: {what}を数え直せない（採点する版が固まっていない）——確かめられないものを合格にはしない")
    probed = {}
    errs, reads, pend = [], [], []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errs.append((i, f"{label}[{i}]: 素の文字列は受け取らない（cite を持つ形で出せ）——"
                            "裏取りの柵が入る前の形が、数え直されないまま毎周の判定材料に載り続けていた"))
            continue
        rk = row.get("kind") if kind["target"] else "text"
        if rk not in ("file", "text"):
            errs.append((i, f"{label}[{i}]: kind が {rk!r}——file（ファイルそのものを指した）か text（ファイルの中の"
                            "セクション名・見出し・引用を指した）で書け"))
            continue
        cite_ = (row.get("cite") or "").strip()
        if rk == "text" and not cite_:
            errs.append((i, f"{label}[{i}]: cite（作業ツリーで引ける字列）が空"))
            continue
        if "\n" in cite_ or "\r" in cite_:
            errs.append((i, f"{label}[{i}]: cite に改行が入っている——" + (
                "1 行 1 件で書け（書いた指しの 1 か所を、指し先の 1 行から写す）" if kind["target"] else
                "数えは行単位の git grep なので『どれか 1 行が在れば合格』に化ける（空行を混ぜれば必ず通る。-F でも同じ）。"
                "1 行 1 件に割って出せ")))
            continue
        if "\0" in cite_ or "\0" in (row.get("target") or "") or "\0" in (row.get("where") or ""):
            errs.append((i, f"{label}[{i}]: cite / target / where に NUL が入っている"
                            "——検索語にもパスにも使えない（現物から写し直せ）"))
            continue
        if not kind["target"]:
            _count_in_version(nid, what, label, i, row, cite_, rev, probed, errs)
            continue
        tgt = (row.get("target") or "").strip()
        if not tgt:
            errs.append((i, f"{label}[{i}]: target（この指しが指しているファイル）が空"
                            "——どこを見れば在ると言えるのかを書け（柵はそのファイルの中だけを数える）"))
            continue
        if "root" not in probed:
            probed["root"] = _repo_root()
        if not probed["root"]:
            raise Reject(f"{nid}: {what}の指し先を確かめられない（リポジトリのルートを引けない——git が動かないか、"
                         "リポジトリの外で打った）——確かめられないものを合格にはしない")
        rel, why = _resolve_target(tgt, probed["root"])
        if rel is None:
            errs.append((i, f"{label}[{i}]: 指し先 '{tgt}' は{why}"))
            continue
        where = (row.get("where") or "").strip()
        if not where:
            errs.append((i, f"{label}[{i}]: where（この指しを書き込んだファイル）が空"
                            "——書いた場所が分からないと、指し先と同じファイルかを誰も見られない"))
            continue
        wrel, why = _resolve_target(where, probed["root"])
        if wrel is None:
            errs.append((i, f"{label}[{i}]: 書いた場所 '{where}' は{why}"))
            continue
        pend.append((i, rk, cite_, rel, wrel))
    if pend:
        seen = _in_version(sorted({p for _, _, _, rel, wrel in pend for p in (rel, wrel)}))
        if seen is None:
            raise Reject(f"{nid}: {what}を数え直せない（git が動かない）——確かめられないものを合格にはしない")
        cache = {}
        for i, rk, cite_, rel, wrel in pend:
            full = pathlib.Path(probed["root"]) / rel
            if rel not in seen or not full.is_file():
                errs.append((i, f"{label}[{i}]: 指し先 '{rel}' は{_not_in_version(full)}"))
                continue
            wfull = pathlib.Path(probed["root"]) / wrel
            if wrel not in seen or not wfull.is_file():
                errs.append((i, f"{label}[{i}]: 書いた場所 '{wrel}' は{_not_in_version(wfull)}"))
                continue
            data = None
            if rk == "text":
                if seen[rel] == "binary":
                    errs.append((i, f"{label}[{i}]: 指し先 '{rel}' はバイナリなので中を数えられない"
                                    "——字列で確かめられる指し先（テキスト）を指すか、ファイルそのものの指しなら kind を file にせよ"))
                    continue
                data, why = read_capped(full, READ_CAP)
                if data is None:
                    errs.append((i, f"{label}[{i}]: 指し先 '{rel}' は版には在るが、作業ツリーで数えられない（{why}）"
                                    "——消した・置き換えた指し先なら、書いた指しの方を直せ"))
                    continue
            state, hwhy = hook_evidence(pathlib.Path(jdir), str(full), cache=cache, data=data)
            reads.append({"kind": rk, "cite": cite_[:60] or None, "target": rel, "where": wrel,
                          "self": wrel == rel, "state": state, "why": hwhy})
            if rk == "text" and cite_.encode("utf-8") not in data:
                hint = "（このファイルをこの run で読んだ記録が無い——記憶で書いていないか）" if state == "absent" else ""
                errs.append((i, f"{label}[{i}]: '{cite_[:40]}' は指し先 '{rel}' の中に無い{hint}"
                                "——文書に書いた指しを指し先に在る綴りへ直し、その字列で申告し直せ（申告だけ差し替えても文書の誤りは残る）"))
    return [m for _, m in sorted(errs, key=lambda e: e[0])], reads


def _count_in_version(nid, what, label, i, row, cite_, rev, probed, errs):
    """元 rules:3612。指摘の根拠の字列を版 rev で数え、0 件・件数の申告（hits）の違いを errs に積む。数えられなければ Reject"""
    got, why = _grep_count(cite_, rev)
    if why:
        if "alive" not in probed:
            probed["alive"] = git("rev-parse", "--is-inside-work-tree") is not None
            probed["rev"] = git("rev-parse", "--verify", f"{rev}^{{commit}}") is not None
        if not probed["alive"]:
            raise Reject(f"{nid}: {what}を数え直せない（git が動かない）——確かめられないものを合格にはしない")
        if not probed["rev"]:
            raise Reject(f"{nid}: {what}を数え直せない（採点する版 {rev[:12]} を解決できない）"
                         "——版が消えた run では、数えた結果も『現物に無い』も言えない")
        raise Reject(f"{nid}: {what}を数え直せない（{why}）——確かめられないものを合格にはしない")
    hits = sum_counts(got)
    if hits is None:
        raise Reject(f"{nid}: {what}を数え直せない（git grep -c の出力が `…:数` の形でない: {got.splitlines()[:1]}）")
    if hits == 0:
        errs.append((i, f"{label}[{i}]: '{cite_[:40]}' が現物に 1 件も無い"
                        "——現物に無い字列は受け取らない（現物を開いて、在る字列で出し直せ）"))
    elif row.get("hits") != hits:
        errs.append((i, f"{label}[{i}]: '{cite_[:40]}' の件数の申告 {row.get('hits')} が数え直し {hits} と違う"))


def _precedent_gap(r):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2437。先行例の 1 行に足りない物（無ければ空文字）。判定者の行と修正役の行が
    同じ規則を使う——見つからないなら何を探したか、それ以外は一次情報の出典"""
    if r.get("verdict") == "not_found":
        return "searched（何をどう探したか）が無い" if blank(r.get("searched"), 4) else ""
    return "source（一次情報の出典）が無い" if blank(r.get("source"), 4) else ""


# ---------------------------------------------------------------- Markdown のリンクと見出し（元 boardview。元 review-loop.py:2822-2837）
MD_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\((?:<([^>\n]+)>|([^()\s<]+))(?:\s+\"[^\"]*\")?\)")   # :2822


MD_FENCE = re.compile(r"^\s{0,3}(```|~~~)")                                                      # :2823


def _md_lines(text):
    """(行番号, 行) を、コードブロック（``` / ~~~ の囲い）の外の行だけ返す（元 review-loop.py:2827）"""
    fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if MD_FENCE.match(line):
            fence = not fence
        elif not fence:
            yield i, line


def _md_slugs(text):
    """見出しのアンカー（GitHub の書き方。重複は -1, -2 …）の集合（元 review-loop.py:2837）"""
    seen, out = {}, set()
    for _, line in _md_lines(text):
        m = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1).strip())
        s = re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-")
        n = seen.get(s, 0)
        seen[s] = n + 1
        out.add(s if n == 0 else f"{s}-{n}")
    return out
