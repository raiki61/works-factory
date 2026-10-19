"""修正の前に作る独立設計（写しの graph の節 r2.design）の先行。役に貼る前提と、起こすかの決めと、控えの読みと照らしを 1 か所に置く。
実行基盤を知らない関数だけを出す。役を起こす支度・受け付け・盤面への渡しは、ブロックの script が持つ。

写しの graph の r2.design は deps に p4.assemble を持つので、盤面では修正と最後のテストの後にしか待たない。周を重ねない線では、
そこで出た作り直しの要否（R2 の redesign-needed）を拾う周が無い。graph は写しのまま（graph_sha を固めた手本と実物の盤面が
それに乗る）にして、設計の役だけを修正の前に先に起こし、受け付けた返答を盤面の根の design.json に控える。盤面が r2.design を
待った時（p4.assemble の後）に、線がその控えを渡す（目的の文の purpose.json と同じ形）。設計の役の入力は目的の文と実測した
制約・人の方針・人の関所の答え・依頼が名指した設計書の節なので、先に起こしても独立は崩れない（修正案・差分を読む口が無い）。

- unusable(b):   目的の出典が R2 に使えない理由（目的不明・狭めている。無ければ None）。式は写しの rules の purpose_unusable
                 （p4.assemble と同じ 1 本）を呼ぶ
- premises:      R2 の 2 つの役（r2.design・r2.compare）に共通して貼る節の並び（人の答え → 名指しの節 → 地図）と、貼った入力の控え {given, withheld, seen}（kind は PREMISE_KINDS の中だけ）。
                 human_answers（人の関所の答え。asked は写さず、answer の無い機械の行は withheld。seen は貼った答えの数と
                 最後の round の印で、突き合わせの側が独立設計の後に来た答えを分けて並べる）と named_sections（依頼が
                 名指した設計書の節の本文。文書の拡張子（impact.DOC_EXT）のパスのリンク・`<path>#<見出し>`・`<path>` N 節と、
                 パスの無い <名前> N 節・<名前> の「見出し」（追跡の文書の名で引く）・パスの無い N 節（依頼が名指した設計書が
                 ただ 1 本の時だけそれに結び付ける）の名指しを、固めた版 HEAD のファイルから、当たった行の形（行頭の記号の並び・
                 次の行の下線・上線と下線。.md・.markdown は囲いの外の # の見出し）で切る。貼る見出しに出どころのパス:行を添える。引けなかった・結び付けられなかった名指しは理由の
                 1 行で withheld。1 節は engine が役に貼る本文の上限 FILE_CAP バイトまで。超えた残りは行の範囲で withheld）と
                 repo_map（対象のリポジトリの根の MAP_NAMES を地図として毎回貼る。無ければ「地図なし」の 1 行と withheld）
- claims_unpassed: R2 の返答のうち『渡されていない』『渡っていない』と書いた文（独立の目の出口が控えと並べる）
- head_file(repo, path): 名指しのパスを固めた版 HEAD の追跡ファイルに解く（根から無ければ末尾の一致がただ 1 本の時だけ。独立設計の支度の印も引く）
- anchors・anchor_misses・anchor_note: 問いが立たない根拠の文の名指し（パス:行。拡張子が ANCHOR_EXT の物）を拾い、固めた版で検算し、
                 無ければ名指しなしと添える
- read_design(board_dir, schema): design.json（無ければ None。読めない・型 schema に合わなければ Reject）。made は (中身 か None,
                 壊れている理由) で拒まない。schema は r2.design の役の型で、ブロックが渡す（盤面 b を取る関数は b.design_schema を読む）
- missing(b):    設計が無い理由の 1 文（諦めた・目的が使えない・控えが無い）。事前審査の指示書と独立の目の出口が使う
- DRIFT_HEAD・UNPAIRED_HEAD: 事前審査の穴の why の頭の 2 語（構造の食い違い・対の無い仕組み）。指示書の決まり・照らし・試験が同じ名を読む
- stands(board_dir, schema): 設計が在り問いが立つ時のその返答（無い・壊れている・問いが立たないなら None）
- quote_gaps(board_dir, schema, faces, rows, design_map=None, kept=()): 2 つの頭の穴の引用と、項目の答えの design_map の誤りの行（設計が立たなければ空）。
                 design_map の行の形は converge.DESIGN_MAP_SCHEMA、案→設計で要る行は _wanted から kept を除いた物。coverage_gaps は独立設計の要素の網羅
                 （呼び手が全部の項目の答えの design_ref を合わせて当てる。planblk.coverage_gaps）
- wanted_lines(rows, kept=())・kept_keys(before, rows): design_map に案→設計の行が 1 行ずつ要る鍵（_wanted から kept を除いた物。受け付けが照らすのと
                 同じ集合）を、指示書に貼る行 {item, path, symbol} の JSON にした並び（planblk.map_items_section が貼る）と、前の往復の行 before にも
                 在った鍵（2 往復目からの審査は変わっていない鍵の行を書き直さない。呼び手 planblk が kept に渡す）
- rebound(rows, design_map): 対応表の写しで、要る鍵に無い案→設計の行のうち (path, symbol) が要る鍵のちょうど 1 つと同じ行を、その鍵の
                 項目の番号に結び直し、結び直せない余りの行を落とした物（受け付けが照らしと refs と網羅の数えの前に当てる。planblk.bound_map）
- element_gaps(reply)・element_lines(got): 立つ設計の elements（{id, adds, removes}）の空と id の重なりの誤り（boardview.check_design が呼ぶ）と、
                 要素を 1 行ずつ描く文（planblk.design_only が貼る）
- BODY_OPEN・BODY_CLOSE・QUOTE_FROM・QUOTE_FROM_ELEMENTS・QUOTE_NONE: 役の材料で独立設計の本文を挟む印と、design_quote の引き元と
                 対が無い時の句（planblk.DESIGN_ASK と design_map の拒みの行が同じ句を読む。拒みの行は、本文に無い字が要素の一覧の行か
                 案の行に在れば、どちらを貼ったかを言う）
"""
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように（必ず import より前）

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
from listcut import FILE_CAP, cap_bytes  # noqa: E402
from engine.util import Reject  # noqa: E402
import accept  # noqa: E402
import answer  # noqa: E402
import cite  # noqa: E402
import impact  # noqa: E402
import planmarks  # noqa: E402
import rolekit  # noqa: E402
from rolekit import BoardGap  # noqa: E402

NODE = "r2.design"
DESIGN_FILE = "design.json"             # 受け付けた設計の返答（盤面の根。run に 1 つ）
MISSING = "独立設計が取れなかった"
HANDED_OP = "r2_design_handed"         # 設計の控えを後段に渡した trace の行（元 works/.shared/core/design.py:74）
MISSING_OP = "r2_design_missing"       # 設計が無いまま先へ進んだ trace の行（元 :75）
REJECT_HEADING = rolekit.REJECT_HEADING
UNUSABLE = {"目的不明": "目的の出典が取れない（目的不明）——独立設計を回さない",
            "狭めている": "目的の文を監査が『狭めている』と判定した——狭められた目的で独立設計を回さない"}
DRIFT_HEAD = "独立設計との構造の食い違い: "
UNPAIRED_HEAD = "独立設計に対の無い仕組み: "
QUOTE_HEADS = (DRIFT_HEAD, UNPAIRED_HEAD)
ROW_QUOTE_KEYS = ("approach", "files", "allowed_paths", "shrink_first")   # 案の行のうち、引用の照らしが読む欄
TEXT_SEP = "\x00"   # 引用の照らしで文を継ぐ字（畳みの空白に化けないので、欄をまたぐ引用は字のままと数えない）
HUMAN_HEAD = "### 承認ノードの答え"
HUMAN_ASK = ("人が承認ノードで答えた前提（run の中で人が決めた物）。ほかのセクションより先に読め。答えが目的の文や前の要求を取り下げ・変えていれば、"
             "取り下げ・変えた後の要求を前提にせよ（取り下げた要求を固定の契約にしない）。設計が取り下げた要求を置いていても、"
             "そのことだけでは差にも前提の崩れにも数えず、答えに照らした目的で突き合わせよ。")
DESIGN_PREMISE_HEAD = "## 人が決めた前提（機械が貼った）"
NAMED_HEAD = "### 依頼が名指した設計書のセクション"
NAMED_ASK = "依頼が名指した設計書のセクションの本文（依頼を固めた版のファイルから機械が抜いた）。目的の文と同じく依頼の一部として読め。"
CODE_SPAN_ANCHOR = re.compile(r"`([^`\s]+\.[A-Za-z0-9]+#[^`\s]+)`")
# 持ち主の地の文の名指し: 「`<path>` 3 節」「`<path>` の §3」（見出しの頭の番号で引く。パスは拡張子つき）
CODE_SPAN_NUM = re.compile(r"`([^`\s#]+\.[A-Za-z0-9]+)`\s*(?:の\s*)?(?:§\s*(\d+(?:\.\d+)*)|(\d+(?:\.\d+)*)\s*節)")
# パスの無い名前の名指し: 「<名前> 3 節」「<名前> の §3」「<名前> の「<見出し>」」。名前は ASCII の英数字で始まる [\w.-] の並びで、前が
# ASCII の英数字・/・.・- でない（パスの途中を拾わない。仮名・漢字は頭にも前にも数えないので、日本語の地の文に続けて書いた名前
# 「詳しくはstructure-design 2 節」から地の文を名に混ぜない）。名前は追跡の文書の名から引く（_docs_named）
_NAME = r"(?<![A-Za-z0-9/.\-])([A-Za-z0-9][\w.\-]*?)"
NAME_NUM = re.compile(_NAME + r"(?:\s+|\s*の\s*)(?:§\s*(\d+(?:\.\d+)*)|(\d+(?:\.\d+)*)\s*節)")
NAME_QUOTE = re.compile(_NAME + r"\s*の\s*「([^」\n]+)」")
# パスの無い「§3」「8 節」（依頼が別の所で名指した設計書がただ 1 本の時だけ、それの節に結び付ける）
BARE_NUM = re.compile(r"§\s*(\d+(?:\.\d+)*)|(\d+(?:\.\d+)*)\s*節")
# 問いが立たない根拠の名指し「<パス>:<行>」「<パス>:<開始>-<終了>」。パスは拡張子つきで / 区切りの段を持ってよい。前が英数字・/・.・:・-
# の当たりは拾わない（URL の host:port を外す。拡張子の無い時刻 10:15 も、拡張子が英字で始まらない版の番号 3.12:1 も拾わない）。パスの字は ASCII に限る（日本語の地の文に続けて
# 書いたパスの頭に地の文を混ぜない）。当たりのうち拡張子が ANCHOR_EXT（impact のコード・設定・文書の拡張子の表）に在る物だけを名指しに
# 数える（db.internal:5432・foo.bar:12 のような host:port やドット付きの名を、固めた版に無いファイルとして拒み続けない）
_ANCHOR = r"(?<![A-Za-z0-9_/.:\-])((?:[A-Za-z0-9_.\-]+/)*[A-Za-z0-9_.\-]*[A-Za-z0-9_\-]\.[A-Za-z][A-Za-z0-9]*):(\d+)(?:-(\d+))?"
ANCHOR = re.compile(_ANCHOR + r"(?![\d:])")
# コマンドの出力（実測の measured_output）の名指し。`grep -n` の「<パス>:<行>:<中身>」のように行の後に `:` が続いてよい
OUTPUT_ANCHOR = re.compile(_ANCHOR + r"(?!\d)")
ANCHOR_EXT = impact.PY_EXT | impact.PATHREF_EXT | impact.DOC_EXT | impact.OTHER_CODE_EXT
UNANCHORED = "根拠の実物の名指しなし"
# Markdown として見出しを数える拡張子（_md_heads）と ATX 見出しの行（写しの rules の _md_slugs と同じ形）
MD_SUFFIXES = (".md", ".markdown")
MD_HEAD = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
UNPASSED = re.compile(r"渡されていない|渡っていない")
# 『渡されていない』の文が控えの given の kind を指す語。制約・前提のずれは「目的と実測した制約しか渡されていない」のような
# 地の文によく出て無関係の行まで当たるので語では当てず、what そのものが文に在る時だけ当てる。設計書の節も「設計書」の語は
# 別の設計書の文にも出るので語では当てず、what のパスか節番号が文に在る時だけ当てる（_named_hit）
# 地図は「地図」の語か、what のパスの部分（`:` の前）が文に在る時に当てる
CLAIM_WORDS = {"human_answer": ("人の答え", "承認ノード"), "repo_map": ("地図",)}
# 独立設計の指示書の頭に機械が貼ってよい前提の種類（premises の控えの kind の許す一覧）。一覧の外（ほかのブロックの出力など）を
# 貼る口は作らない（独立設計の隔て。設計書 structure-block-design 7 節）。graph の reads で描く本文はこの柵の外（graph の reads が縛り、
# その reads と prompt_append などの入口は tests/test_blk_eyes.py の test_r2_design_inputs_are_exactly_the_allowlist が許可の一覧の等式で縛る）
PREMISE_KINDS = ("human_answer", "named_section", "repo_map")
# 対象のリポジトリの地図として根から読む名（関所の決め: 根の 2 つだけ。docs/ の下や README は読まない）。中身は分類せず丸ごと貼る。
# AGENTS.md は blk-fix の fixrules.PROMPT_NAMES（役の指示書として読む名）とも重なる（core から blk-fix へは依らないので別に置く）
MAP_NAMES = ("ARCHITECTURE.md", "AGENTS.md")
MAP_HEAD = "### 対象のリポジトリの地図"
MAP_FILE_HEAD = "#### {name}:1-{total}"
NAMED_BODY_HEAD = "#### {name}（{src}）"
MAP_ASK = ("対象のリポジトリの根に在る地図の文書（依頼を固めた版のファイルから機械が貼った。見出しは出どころのパス:行）。"
           "依頼が名指していなくても、仕組みの中に既に在る実物（信用の起点・外との通信の経路・守る物）から設計を始めよ。")


def human_answers(b) -> tuple:
    """(R2 の 2 つの役に貼る人の関所の答え（record.process.human_items）の節 か 空, 貼った行, 機械の行, 見た印 {count, last_round})。
    聞いた項目の本文（asked）は判定の一覧・決着済み論点に当たるので写さず、round・node・kinds・answer・note だけを取る。
    answer の無い行（守りのファイル・食い違い・無人の停止で機械が積んだ行）と、無人の run が推しで通した行（欄 answer.PUSHED）は
    人の答えでないので貼らず、控えの withheld に回す"""
    rows, machine, last = [], [], None
    for h in (b.record.get("process") or {}).get("human_items") or []:
        if not isinstance(h, dict):
            continue
        at = f"周 {h.get('round')}" + (f"・{h['node']}" if h.get("node") else "")
        kinds = "・".join(str(k) for k in h.get("kinds") or []) or "種類なし"
        if h.get("answer") is None or answer.by_push(h):
            machine.append(f"{at}（{kinds}）")
            continue
        note = h.get("note") or "（一言なし）"
        rows.append(f"{at}（{kinds}）: {h['answer']}（一言: {note}）")
        last = h.get("round")
    text = (f"{HUMAN_HEAD}\n\n{HUMAN_ASK}\n\n" + "\n".join(f"- {r}" for r in rows)) if rows else ""
    return text, rows, machine, {"count": len(rows), "last_round": last}


def _is_doc(path) -> bool:
    """名指しのパスを設計書に数えるか: URL でなく、拡張子が文書の拡張子（impact.DOC_EXT。コードを含まない）に在る"""
    return "://" not in path and pathlib.PurePosixPath(path).suffix[1:].lower() in impact.DOC_EXT


def _tracked(repo) -> list:
    """固めた版 HEAD の追跡ファイルの名（根からの相対。並べた順）"""
    got = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "-z", "HEAD"], capture_output=True)
    return [n for n in got.stdout.decode("utf-8", "replace").split("\0") if n] if got.returncode == 0 else []


def _docs_named(repo, name) -> list:
    """固めた版の追跡ファイルのうち、設計書に数える拡張子で、拡張子を除いた名が name と等しいか -・_・. の後に name で終わる物
    （日付を頭に付けた設計書に届くため）"""
    return [n for n in _tracked(repo) if _is_doc(n)
            and ((stem := pathlib.PurePosixPath(n).stem) == name or any(stem.endswith(f"{c}{name}") for c in "-_."))]


def _named_targets(b, text, repo) -> tuple:
    """(依頼の文が設計書の節を名指す相対の指し先, 結び付けられなかった名指しの [(元の文字列, 理由)])。設計書は拡張子が文書の物
    （_is_doc）だけで、コードへのリンクは数えない。拾う順は Markdown のリンク・コードスパンの `<path>#<見出し>` → コードスパンの後の
    「N 節」「§N」→ パスの無い名前の「<名前> N 節」「<名前> の「<見出し>」」（名の一致する追跡の文書がただ 1 本ならそれ。2 本以上は
    推測せずに理由と返し、0 本は名前に数えない）→ パスの無い「N 節」「§N」。番号の名指しは `<path> N 節` の形で返す。パスの無い番号は、
    依頼が名指した設計書のパスがただ 1 本の時だけそれに結び付け、0 本か 2 本以上なら推測せずに理由と返す（head_file が末尾の一致が
    複数の時に決めないのと同じ）。出た順・重複なし"""
    found = [m.group(1) or m.group(2) for m in b.rules.MD_LINK.finditer(text)] + CODE_SPAN_ANCHOR.findall(text)
    out, docs, unbound = [], [], []

    def add(t, path):
        if path not in docs:
            docs.append(path)
        if t and t not in out:
            out.append(t)

    for t in found:
        path, _, anchor = t.partition("#")
        if _is_doc(path):
            add(t if anchor else "", path)
    for m in CODE_SPAN_NUM.finditer(text):
        if _is_doc(m.group(1)):
            add(f"{m.group(1)} {m.group(2) or m.group(3)} 節", m.group(1))
    rest = list(CODE_SPAN_NUM.sub("", b.rules.MD_LINK.sub("", text)))
    plain = "".join(rest)
    for rx in (NAME_NUM, NAME_QUOTE):
        for m in rx.finditer(plain):
            name = m.group(1)
            cands = [] if re.fullmatch(r"[\d.]+", name) else _docs_named(repo, name)
            if not cands:
                continue
            rest[m.start():m.end()] = " " * (m.end() - m.start())   # パスの無い番号に回さない
            if len(cands) > 1:
                unbound.append((m.group(0), f"名の一致する追跡の文書が {len(cands)} 本あって決められない（候補: {', '.join(cands)}）"))
            elif rx is NAME_NUM:
                add(f"{cands[0]} {m.group(2) or m.group(3)} 節", cands[0])
            else:
                add(f"{cands[0]}#{m.group(2)}", cands[0])
    bare = list(BARE_NUM.finditer("".join(rest)))
    if len(docs) == 1:
        for m in bare:
            add(f"{docs[0]} {m.group(1) or m.group(2)} 節", docs[0])
        return out, unbound
    why = (f"依頼が名指した設計書のパスが {len(docs)} 本あって決められない" if docs else
           "結び付けられる形の設計書の名指しが依頼に無い（リンク・`<path>#<見出し>`・`<path>` N 節・<名前> N 節 の形だけを数える）")
    return out, unbound + [(w, why) for w in dict.fromkeys(m.group(0) for m in bare)]


def head_file(repo, path) -> str:
    """名指しのパスを固めた版 HEAD の追跡ファイルに解く。根から無ければ、末尾が一致する追跡ファイルがただ 1 つの時だけそれ
    （持ち主は pack の下から見た相対で書くことがある）。引けなければ ValueError（理由）"""
    rel = pathlib.PurePosixPath(urllib.parse.unquote(path))
    if rel.is_absolute() or ".." in rel.parts or ".git" in rel.parts:
        raise ValueError("作業ツリーの根の外か .git を指す")
    names = _tracked(repo)
    if str(rel) in names:
        return str(rel)
    tail = [n for n in names if n.endswith(f"/{rel}")]
    if len(tail) == 1:
        return tail[0]
    raise ValueError("固めた版にファイルが無い" if not tail else f"同じ末尾の追跡ファイルが {len(tail)} 本あって決められない")


def _marks(line) -> tuple:
    """(記号 1 文字, 並びの長さ, 並びの後の残り)。行頭の空白 3 つまでを除いた後が英数字でも空白でもない同じ文字の連なりで
    なければ ("", 0, "")"""
    s = line[len(line) - len(line.lstrip(" ")):] if len(line) - len(line.lstrip(" ")) <= 3 else ""
    if not s or s[0].isalnum() or s[0].isspace():
        return "", 0, ""
    n = len(s) - len(s.lstrip(s[0]))
    return s[0], n, s[n:]


def _md_heads(text, md_lines) -> list:
    """Markdown の見出しの行（_heads と同じ形）。写しの rules の _md_lines（``` / ~~~ の囲いの外の行）の ATX 見出しだけを数える
    （下線の見出しも箇条・引用・表の行も数えない。依頼 238 の前の .md の数え方と同じ）"""
    out = []
    for n, line in md_lines(text):
        m = MD_HEAD.match(line)
        if m:
            out.append({"line": n, "kind": "prefix", "mark": "#", "depth": len(m.group(1)), "title": m.group(2)})
    return out


def _heads(lines) -> list:
    """見出しの行 [{line（1 始まり）, kind（prefix: 行頭の同じ記号の並びと空白と題 / under: 題の行の次の行が 1 種類の記号の
    3 文字以上だけ。上線と下線が同じ記号で 1 行を挟む題も under で、mark は記号を 2 つ重ねた物）, mark, depth, title}]。
    Markdown でない文書に使う（Markdown は _md_heads）。形式の名前は持たない。記号だけの行が挟む区間（囲み）の中は数えず、
    隣の行と同じ記号・同じ長さの前置きの行は列（箇条・表）とみなして数えない。depth は前置きなら並びの長さ、下線なら下線の
    mark が文書の中で初めて現れた順（0 始まり）。囲みと列の見分けは形式に依る推測（docs/language-neutral-inventory.md 7-7）"""
    marks = [_marks(x) for x in lines]
    only = [n >= 3 and not rest.strip() for _, n, rest in marks]

    def body(i):
        return bool(lines[i].strip()) and not only[i]

    def over(i):   # 上線つきの題: 記号だけの行・題の 1 行・同じ記号だけの行（前の行が本文なら上線でなく前の題の下線）
        return (only[i] and i + 2 < len(lines) and only[i + 2] and marks[i + 2][0] == marks[i][0] and body(i + 1)
                and not (i > 0 and body(i - 1)))

    inside, titled, i = set(), set(), 0
    while i < len(lines):   # 囲み: 3 文字以上の記号の並び（と空白の無い 1 語）で開き、下線でなく、次の行が空でない
        if over(i):
            titled.add(i)
            i += 3
            continue
        c, n, rest = marks[i]
        word = rest.rstrip()   # 並びの直後に空白を挟む行（`### A`）は前置きの形で、囲みを開かない
        opens = (n >= 3 and not any(ch.isspace() for ch in word) and not (only[i] and i > 0 and body(i - 1))
                 and i + 1 < len(lines) and lines[i + 1].strip())
        close = next((j for j in range(i + 1, len(lines)) if only[j] and marks[j][0] == c and marks[j][1] >= n),
                     None) if opens else None
        if close is None:
            i += 1
            continue
        inside.update(range(i, close + 1))
        i = close + 1

    def prefix(i):
        c, n, rest = marks[i]
        return n > 0 and i not in inside and rest[:1].isspace() and bool(rest.strip())

    out, order, skip = [], [], set()
    for i in range(len(lines)):
        if i in inside or i in skip:
            continue
        if i in titled:
            c = marks[i][0] * 2
            if c not in order:
                order.append(c)
            out.append({"line": i + 1, "kind": "under", "mark": c, "depth": order.index(c), "title": lines[i + 1].strip()})
            skip.update((i + 1, i + 2))
            continue
        if prefix(i):
            c, n, rest = marks[i]
            if any(0 <= j < len(lines) and prefix(j) and marks[j][:2] == (c, n) for j in (i - 1, i + 1)):
                continue
            out.append({"line": i + 1, "kind": "prefix", "mark": c, "depth": n, "title": rest.strip().rstrip(c).strip()})
        elif (i + 1 < len(lines) and i + 1 not in inside and i + 1 not in titled and only[i + 1] and body(i)
              and not prefix(i)):
            c = marks[i + 1][0]
            if c not in order:
                order.append(c)
            out.append({"line": i + 1, "kind": "under", "mark": c, "depth": order.index(c), "title": lines[i].strip()})
    return out


def _section_lines(text, *, num="", anchor="", slugs=None, md_lines=None) -> tuple:
    """名指し（番号 num か見出しのアンカー anchor）に当たる節の (開始行, 終了行)。1 始まりで両端を含む。引けなければ ValueError（理由）。
    アンカーは slugs（写しの rules の _md_slugs。GitHub の書き方で重複は -1）で作った物と等しい見出し、無ければ題がアンカーを含む見出し。
    md_lines（写しの rules の _md_lines）を渡せば Markdown として _md_heads で、渡さなければ行の形の推測 _heads で見出しを数える"""
    lines = text.splitlines()
    heads = _md_heads(text, md_lines) if md_lines else _heads(lines)
    if num:
        by_num = re.compile(rf"(?:第)?{re.escape(num)}(?:\.?(?:\s|$)|節)")
        hits = [h for h in heads if by_num.match(h["title"].lstrip("§ \t"))]
    else:
        want = urllib.parse.unquote(anchor).lower()
        hits = []
        if slugs is not None:
            titles = [x["title"] for x in heads]
            for k, h in enumerate(heads):   # 見出し k のアンカー: 題を ATX の行に並べた文書の k 番目までの slug から、k より前の slug を引いた物
                if want in slugs("\n# ".join(["", *titles[:k + 1]])) - slugs("\n# ".join(["", *titles[:k]])):
                    hits.append(h)
        if not hits:
            hits = [h for h in heads if want and want in h["title"].lower()]
    if not hits:
        raise ValueError("見出しが無い")
    if len(hits) > 1:
        raise ValueError(f"当たる見出しが {len(hits)} 個あって決められない（行 {', '.join(str(h['line']) for h in hits)}）")
    hit = hits[0]

    def ends(h):
        if hit["kind"] == "prefix":
            return h["kind"] == "prefix" and h["mark"] == hit["mark"] and h["depth"] <= hit["depth"]
        return h["kind"] == "under" and (h["mark"] == hit["mark"] or h["depth"] < hit["depth"])
    end = next((h["line"] - 1 for h in heads if h["line"] > hit["line"] and ends(h)), len(lines))
    while end > hit["line"] and not lines[end - 1].strip():
        end -= 1
    return hit["line"], end


def _split_target(target) -> tuple:
    """名指しの文字列 `<path>#<anchor>` か `<path> <N> 節` を (path, anchor, num) に分ける（path の拡張子は問わない）"""
    num = re.fullmatch(r"(.+) (\S+) 節", target)
    if num:
        return num.group(1), "", num.group(2)
    path, _, anchor = target.partition("#")
    return path, anchor, ""


def _section(b, repo, target) -> tuple:
    """(名指し 1 つの節の本文（依頼を固めた版 HEAD のファイルから）, 出どころ `<パス>:<開始>-<終了>`,
    engine の FILE_CAP で切った残りの範囲 `<パス>:<k>-<終了>` か "")。引けなければ ValueError（理由）"""
    path, anchor, num = _split_target(target)
    rel = head_file(repo, path)
    got = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    if got.returncode != 0:
        raise ValueError("固めた版にファイルが無い")
    md = b.rules._md_lines if pathlib.PurePosixPath(rel).suffix.lower() in MD_SUFFIXES else None
    start, end = _section_lines(got.stdout, num=num, anchor=anchor, slugs=b.rules._md_slugs, md_lines=md)
    body = "\n".join(got.stdout.splitlines()[start - 1:end])
    cut = []
    capped = cap_bytes(body, target, cut)
    rest = ""
    if cut:   # 切った後の本文に丸ごと残った行の数の次の行から
        kept = body.encode("utf-8")[:FILE_CAP].decode("utf-8", "ignore").count("\n")
        rest = f"{rel}:{start + kept}-{end}"
    return capped, f"{rel}:{start}-{end}", rest


def named_sections(b, repo) -> tuple:
    """(R2 の 2 つの役に貼る、依頼（盤面の inputs.request）が名指した設計書の節の本文 か 空, 控えの given, 控えの withheld)。
    引けなかった名指しは本文を貼らずに理由の 1 行にする。貼る見出しと切った残りには出どころの行の範囲を添える"""
    parts, given, withheld = [], [], []
    targets, unbound = _named_targets(b, (b.state.get("inputs") or {}).get("request") or "", repo)
    for t, why in unbound:
        parts.append(f"- 依頼が名指したが引けなかった: {t}（{why}）")
        withheld.append({"kind": "named_section", "what": t, "why": why})
    for t in targets:
        try:
            body, src, rest = _section(b, repo, t)
        except ValueError as e:
            parts.append(f"- 依頼が名指したが引けなかった: {t}（{e}）")
            withheld.append({"kind": "named_section", "what": t, "why": str(e)})
            continue
        parts.append(f"{NAMED_BODY_HEAD.format(name=t, src=src)}\n\n{body}")
        given.append({"kind": "named_section", "what": t})
        if rest:
            withheld.append({"kind": "named_section", "what": t, "why": f"{FILE_CAP} バイトを超えた残り（{rest}）"})
    text = (f"{NAMED_HEAD}\n\n{NAMED_ASK}\n\n" + "\n\n".join(parts)) if parts else ""
    return text, given, withheld


def repo_map(repo) -> tuple:
    """(R2 の 2 つの役に貼る対象のリポジトリの地図の節（空にならない）, 控えの given, 控えの withheld)。固めた版 HEAD の根に追跡されて
    いる MAP_NAMES を出どころのパス:行つきで丸ごと貼る。FILE_CAP を超えたら切り、切った行の範囲を withheld に書く。1 つも無ければ
    「地図なし」の 1 行を貼る。根のパスだけを読む（head_file の末尾の一致は使わない）"""
    names = set(_tracked(repo))
    parts, given, withheld = [], [], []
    for n in MAP_NAMES:
        if n not in names:
            continue
        got = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{n}"], capture_output=True, text=True, encoding="utf-8")
        if got.returncode != 0:
            continue
        body = got.stdout.rstrip("\n")
        total = len(body.splitlines())
        if not total:
            withheld.append({"kind": "repo_map", "what": n, "why": "空のファイル"})
            continue
        cut = []
        parts.append(f"{MAP_FILE_HEAD.format(name=n, total=total)}\n\n{cap_bytes(body, n, cut)}")
        given.append({"kind": "repo_map", "what": f"{n}:1-{total}"})
        if cut:   # 切った後の本文に丸ごと残った行の数の次の行から
            k = 1 + body.encode("utf-8")[:FILE_CAP].decode("utf-8", "ignore").count("\n")
            withheld.append({"kind": "repo_map", "what": n, "why": f"{FILE_CAP} バイトを超えた残り（{n}:{k}-{total}）"})
    if not parts:
        parts.append(f"- 地図なし: 根の {'・'.join(MAP_NAMES)} は固めた版に無い")
        if not withheld:
            withheld.append({"kind": "repo_map", "what": "・".join(MAP_NAMES), "why": "対象のリポジトリの根に追跡されていない"})
    return f"{MAP_HEAD}\n\n{MAP_ASK}\n\n" + "\n\n".join(parts), given, withheld


def premises(b, repo) -> tuple:
    """(R2 の 2 つの役に共通して貼る、人が決めた前提の節の並び（人の関所の答え・依頼が名指した設計書の節・対象のリポジトリの地図。
    空の節は除く。地図の節は空にならない）,
    控え {given, withheld, seen})。控えは貼った本文と同じ呼び出しから作る（別の源から組み直さない）"""
    human, rows, machine, seen = human_answers(b)
    named, given, withheld = named_sections(b, repo)
    mapped, map_given, map_withheld = repo_map(repo)
    given = [{"kind": "human_answer", "what": r} for r in rows] + given + map_given
    outside = sorted({g["kind"] for g in given} - set(PREMISE_KINDS))
    if outside:   # 一覧の外の源（ほかのブロックの出力など）から貼る口を作らない
        raise BoardGap(f"独立設計に渡す入力の種類が許す一覧（{' / '.join(PREMISE_KINDS)}）の外: {', '.join(outside)}")
    withheld = [{"kind": "human_item", "what": m, "why": "answer の無い行（機械が積んだ。人の答えでない）"} for m in machine] + withheld + map_withheld
    return [s for s in (human, named, mapped) if s], {"given": given, "withheld": withheld, "seen": seen}


def claims_unpassed(reply) -> list:
    """R2 の返答（reason と differences の text）のうち、入力が渡されていない・渡っていないと書いた文（。と改行で切る）"""
    texts = [str((reply or {}).get("reason") or "")] + [str(d.get("text") or "") for d in (reply or {}).get("differences") or []
                                                         if isinstance(d, dict)]
    return [s.strip() for t in texts for s in re.split(r"[。\n]", t) if UNPASSED.search(s)]


def claims_given(claims, given) -> list:
    """claims_unpassed の文のうち、控えの given（渡した前提の入力）に当たる物の [{claim, kind, what}]。claim が what そのもの
    （設計書の節は what のパスか節番号）か given の kind の語（CLAIM_WORDS）を含めば当たる。判定はせず、並べて人に突き合わせさせる"""
    return [{"claim": c, "kind": g.get("kind"), "what": g.get("what")} for c in claims for g in given or []
            if isinstance(g, dict) and (str(g.get("what")) in c or any(w in c for w in CLAIM_WORDS.get(g.get("kind"), ()))
                                        or g.get("kind") == "named_section" and _named_hit(str(g.get("what")), c)
                                        or g.get("kind") == "repo_map" and str(g.get("what")).partition(":")[0] in c)]


def _named_hit(what, claim) -> bool:
    """設計書の節の what（`<path>#<見出し>` か `<path> N 節`）のパスか節番号（見出しの頭の番号）が claim に在るか"""
    path, anchor, num = _split_target(what)
    n = num or (re.match(r"\d+", anchor) or [""])[0]
    return path in claim or bool(n and re.search(rf"§\s*{re.escape(n)}(?![\d.])|(?<![\d.]){re.escape(n)}\s*節", claim))


def unusable(b):
    """目的の出典が R2 に使えない理由（None／目的不明／狭めている）。写しの p4.assemble が loop.purpose_unusable に置くのと同じ
    1 本（写しの rules の purpose_unusable）を、p4.assemble より前に呼ぶ"""
    return b.rules.purpose_unusable(b)


def read_design(board_dir, schema):
    """盤面の根の design.json（無ければ None）。読めない・型 schema（r2.design の役の型。ブロックが渡す）に合わなければ Reject"""
    obj = accept.read_board(board_dir, DESIGN_FILE)
    if obj is not None:
        accept.type_errors(obj, schema, f"共有ボードの {DESIGN_FILE} ")
    return obj


def made(board_dir, schema) -> tuple:
    """(控えの中身 か None, 控えが壊れている時の理由)"""
    try:
        return read_design(board_dir, schema), ""
    except Reject as e:
        return None, f"{MISSING}: {e}"


def _anchor_matches(text, output=False) -> list:
    """ANCHOR（output ならコマンドの出力の OUTPUT_ANCHOR）の当たりのうち、拡張子が ANCHOR_EXT に在る物（出た順）"""
    return [m for m in (OUTPUT_ANCHOR if output else ANCHOR).finditer(str(text or ""))
            if pathlib.PurePosixPath(m.group(1)).suffix[1:].lower() in ANCHOR_EXT]


def anchors(text, output=False) -> list:
    """文の中の `パス:行` と `パス:開始-終了` を (パス, 開始, 終了) で出た順に（`パス:行` は開始と終了が同じ。_anchor_matches の物だけ。
    output はコマンドの出力として読む）"""
    return [(m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))) for m in _anchor_matches(text, output)]


def anchor_misses(text, repo) -> list:
    """anchors のうち固めた版 HEAD の追跡ファイルと行の範囲に当たらない物ごとに「<パス>:<開始>[-<終了>]（<理由>）」（字は文のまま）"""
    out = []
    for m in _anchor_matches(text):
        start, end = int(m.group(2)), int(m.group(3) or m.group(2))
        try:
            rel = head_file(repo, m.group(1))
            got = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{rel}"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            if got.returncode != 0:
                raise ValueError("固めた版にファイルが無い")
            n = len(got.stdout.splitlines())
            if not 1 <= start <= end <= n:
                raise ValueError(f"行の範囲の外（ファイルは {n} 行）")
        except ValueError as e:
            row = f"{m.group(0)}（{e}）"
            if row not in out:
                out.append(row)
    return out


def anchor_note(text) -> str:
    """根拠の文に名指し（anchors）が無ければ「（根拠の実物の名指しなし）」、在れば ""（事前審査の指示書と報告が添える）"""
    return "" if anchors(text) else f"（{UNANCHORED}）"


def missing(b) -> str:
    """設計が無い理由の 1 文（控えが在れば空）"""
    got, broken = made(b.dir, b.design_schema)
    if got is not None or broken:
        return broken
    gave = rolekit.given_up_reason(b.dir, NODE)
    if gave:
        return f"{MISSING}: {gave}"
    why = unusable(b)
    if why:
        return UNUSABLE[why]
    return f"{MISSING}: 修正の前に設計の役を起こしていない（{DESIGN_FILE} が無い）"


# design_quote の引き元（受け付けが照らすのは独立設計の本文 design だけ。要素の一覧の行は機械が本文の後ろに描いた別の字）
BODY_OPEN, BODY_CLOSE = "=====独立設計ここから=====", "=====独立設計ここまで====="   # 役の材料で独立設計の本文を挟む印（planblk.design_only）
QUOTE_FROM = f"独立設計の本文（{BODY_OPEN} と {BODY_CLOSE} の間）の文を字のまま引け"
QUOTE_FROM_ELEMENTS = "本文の後ろの要素の一覧の行（`D1: 足す: …／消す: …`）の字"
QUOTE_NONE = "対が無ければ null"
ELEMENTS_HEAD = "### 独立設計の要素（design_map の design_ref が指す id）"


def element_gaps(reply) -> list:
    """立つ設計の返答 reply（question_stands が真）の elements の誤りの行: 空・id の重なり（立たない返答は空。id の形 ^D[0-9]+$ と
    adds・removes の型は役の型が先に照らす）。design_ref の実在（_map_gaps）と設計→案の網羅（coverage_gaps）は要素の一覧が
    要るので、立つ設計は必ず要素を持つ。design.json を書くのは boardview.check_design だけで、そこが呼ぶ"""
    if not (isinstance(reply, dict) and reply.get("question_stands") is True):
        return []
    elements = reply.get("elements")
    ids = element_ids(elements)
    out = []
    if not ids:
        out.append("elements が空（問いが立つ設計は、設計の要素を id（D1…）と足す物・消す物の字を持つ行で 1 つ以上並べる。"
                   "審査役が案の行を要素の id で指せるように）")
    out += [f"elements の id {i} が {ids.count(i)} 行ある（id は重ならない）" for i in dict.fromkeys(ids) if ids.count(i) > 1]
    return out


def element_lines(got) -> str:
    """立つ設計の返答 got の要素を 1 行ずつ描いた文（`- D1: 足す: …／消す: …`。先頭に ELEMENTS_HEAD）。要素が無ければ空
    （planblk.design_only が独立設計の本文の後に貼る。審査役が id で指せる）"""
    rows = [e for e in (got or {}).get("elements") or [] if isinstance(e, dict) and isinstance(e.get("id"), str)]
    if not rows:
        return ""
    def side(e, key):
        return "・".join(str(x) for x in e.get(key) or []) or "無し"
    return f"{ELEMENTS_HEAD}\n\n" + "\n".join(f"- {e['id']}: 足す: {side(e, 'adds')}／消す: {side(e, 'removes')}" for e in rows)


def stands(board_dir, schema):
    """設計が在り問いが立つ時のその返答（設計が無い・控えが壊れている・問いが立たないなら None）"""
    got, _ = made(board_dir, schema)
    return got if got is not None and got.get("question_stands") else None


def _texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _texts(v)
    elif isinstance(value, list):
        for v in value:
            yield from _texts(v)


def _row_text(row) -> str:
    return TEXT_SEP.join(t for k in ROW_QUOTE_KEYS for t in _texts(row.get(k)))


def _ref_of(e: dict):
    return e.get("design_ref")


def _wanted(rows) -> list:
    """案の行 rows の、対応表に 1 行ずつ要る (項目の番号, path, symbol): files の change=add の symbol・change=remove の symbol（消す側も入れる）
    と、op が create・delete・rename の行（symbol は None）。現れた順・重なりは 1 つ"""
    out = []
    for r in rows:
        for row in planmarks.file_rows(r):
            path = row.get("path")
            if not isinstance(path, str):
                continue
            if row.get("op") in ("create", "delete", "rename"):
                out.append((r.get("item"), path, None))
            out += [(r.get("item"), path, s["name"]) for s in planmarks.symbol_rows(row)
                    if s.get("change") in planmarks.SYMBOL_CHANGES and isinstance(s.get("name"), str)]
    return list(dict.fromkeys(out))


def rebound(rows, design_map) -> list:
    """対応表 design_map の写し。案→設計の行のうち、鍵 (item, path, symbol) が案の行 rows の要る鍵（_wanted）に無く、(path, symbol) が
    要る鍵のちょうど 1 つと同じ行は、その鍵の項目の番号に結び直す（項目の番号だけの取り違えで拒まない。#687）。結び直しても要る鍵に
    無い行は落とす（余りの行は照らさず、その design_ref も要素の網羅に数えない）"""
    want = _wanted(rows)
    out = []
    for e in design_map if isinstance(design_map, list) else []:
        if isinstance(e, dict) and e.get("item") is not None and (e.get("item"), e.get("path"), e.get("symbol")) not in want:
            hits = [k for k in want if k[1:] == (e.get("path"), e.get("symbol"))]
            if len(hits) != 1:
                continue
            e = {**e, "item": hits[0][0]}
        out.append(e)
    return out


def wanted_lines(rows, kept=()) -> list:
    """案の行 rows の、design_map に案→設計の行が 1 行ずつ要る鍵（_wanted から kept を除いた物。受け付けの _map_gaps が照らすのと同じ
    集合）を、役の指示書に貼る行にした並び。1 行は design_map の行の頭 {"item": n, "path": "…", "symbol": "…" か null} の JSON"""
    return [json.dumps({"item": i, "path": p, "symbol": s}, ensure_ascii=False) for i, p, s in _wanted(rows) if (i, p, s) not in kept]


def kept_keys(before, rows) -> set:
    """案の行 rows の design_map の鍵（_wanted）のうち、前の往復の行 before（同じ item の番号を付けた物）にも在った鍵"""
    return set(_wanted(rows)) & set(_wanted(before))


def _label(item, path, symbol) -> str:
    return f"項目 {item} の {path}" + (f"::{symbol}" if symbol is not None else "（行）")


def element_ids(elements) -> list:
    """独立設計の要素 elements（{id, adds, removes} の行の並び。役の返答の欄 elements）の id の並び（字の物だけ・現れた順）"""
    return [e["id"] for e in elements if isinstance(e, dict) and isinstance(e.get("id"), str)] if isinstance(elements, list) else []


def refs_of(design_map) -> list:
    """対応表 design_map の design_ref の並び（字の物だけ・重なりは 1 つ）"""
    return list(dict.fromkeys(e["design_ref"] for e in design_map if isinstance(e, dict) and isinstance(e.get("design_ref"), str))) \
        if isinstance(design_map, list) else []


def coverage_gaps(elements, refs) -> list:
    """独立設計の要素 elements のうち、refs（design_ref の集まり）に出ない物の誤りの行（設計→案の向きの網羅。要素の漏れ）。refs は
    今の往復の全部の項目の答えの対応表の design_ref と、閉じた項目の控えに残した design_ref を合わせた物（呼び手が集める。1 つの答え
    だけでは、ほかの項目が受ける要素を『どの項目も受けない』と見分けられない）"""
    have = set(refs)
    return [f"独立設計の要素 {i} が、どの行の design_ref にも出ない（受ける鍵の行の design_ref に {i} を書くか、鍵の一覧に対の行が無いなら item・"
            f"path・symbol を null にした行に design_ref {i} を書け）" for i in element_ids(elements) if i not in have]


def _map_gaps(source, rows, design_map, elements=None, kept=()) -> list:
    """design_map の誤りの行。行は {item, path, symbol, design_ref, design_quote, why} の 2 つの向き:
    - 案→設計: 案の行 rows の files の (項目, path, symbol) ごとにちょうど 1 行（対象は change=add の symbol・change=remove の symbol・
      op が create・delete・rename の行（symbol は null）。kept の鍵は行を求めない（書けば照らす）。要る鍵に無い行（rows の項目の外の項目の行・
      項目の files の add・remove でない記号の行・op が modify の行を symbol null で指す行）は余りとして鍵の数えに入れず拒まない（受け付けは rebound で、項目の番号の取り違えを
      結び直し、残りの余りの行を照らす前に落とす）。design_ref は指す要素の id（対が無ければ null）
    - 設計→案: item・path・symbol が null で design_ref が必須（要る鍵のどの行にも対の無い要素を挙げる。対が鍵の無い files の行——
      op が modify で add・remove の無い行——にだけ在る要素も）
    design_ref は elements（独立設計の要素）に在る id だけ。同じ鍵の行の重なりは誤り。design_quote が在れば独立設計の文に字のまま
    在る（null は対が無い）。要素の網羅はここで照らさない（一部の項目の答えでは、ほかの項目が受ける要素を「どの項目も受けない」と
    見分けられない。呼び手が全部の答えを合わせて coverage_gaps を当てる）"""
    entries = [e for e in design_map if isinstance(e, dict)] if isinstance(design_map, list) else []
    ids = set(element_ids(elements))
    every = _wanted(rows)
    wanted = [k for k in every if k not in kept]
    count = {}
    out = []
    for e in entries:
        key = (e.get("item"), e.get("path"), e.get("symbol"))
        if key[0] is None:
            if key[1] is not None or key[2] is not None:
                out.append(f"design_map の設計→案の行（item が null）は path・symbol も null にする（今は {key[1]}・{key[2]}）")
            elif not isinstance(_ref_of(e), str):
                out.append("design_map の設計→案の行（item・path・symbol が null）には design_ref が要る（案に対の無い要素の id）")
            else:
                count[("design", _ref_of(e))] = count.get(("design", _ref_of(e)), 0) + 1
            continue
        count[key] = count.get(key, 0) + 1
    out += [f"design_map に{_label(*k)}の行が無い（files の add・remove の symbol と op が create・delete・rename の行ごとにちょうど 1 行）"
            for k in wanted if not count.get(k)]
    out += [f"design_map に{_label(*k)}の行が {count[k]} 行ある（ちょうど 1 行）" for k in every if count.get(k, 0) > 1]
    out += [f"design_map の設計→案の行の design_ref {k[1]} が {n} 行ある（1 行にまとめよ）" for k, n in count.items()
            if k[0] == "design" and n > 1]
    for e in entries:
        ref = _ref_of(e)
        if ref is not None and ref not in ids:
            out.append(f"design_map の design_ref {ref} は独立設計の要素に無い（在るのは {sorted(ids) or '無し'}。"
                       "案に対が無い行の design_ref は null）")
    listed = element_lines({"elements": elements})
    planned = TEXT_SEP.join(_row_text(r) for r in rows)
    for e in entries:
        quote = e.get("design_quote")
        if quote is None:
            continue
        inner = str(quote).strip()
        inner = inner[1:-1] if inner.startswith("「") and inner.endswith("」") else inner
        if not cite.quoted_in(inner, source, norm=cite.fold):
            where = _label(e.get("item"), e.get("path"), e.get("symbol")) if e.get("item") is not None else f"設計→案 {_ref_of(e)}"
            out.append(f"design_map の{where}の design_quote「{inner}」が独立設計の文に字のまま無い（{_pasted(inner, listed, planned)}）")
    return out


def _pasted(quote, listed, planned) -> str:
    """独立設計の文に無い design_quote の拒みの行の直し方: 引いた字が要素の一覧の行 listed か案の行 planned に在れば、どちらを貼ったか
    （見分けは空白を全部除いて比べる。`足す: … ／ 消す: …` のように空白を足して貼った字も一覧の行と見る）"""
    if cite.quoted_in(quote, listed, norm=cite.unspaced):
        return f"{QUOTE_FROM_ELEMENTS}を貼った。対がある時は{QUOTE_FROM}（{QUOTE_NONE}）"
    if cite.quoted_in(quote, planned, norm=cite.unspaced):
        return f"修正案の行の字を貼った。対がある時は{QUOTE_FROM}（{QUOTE_NONE}）"
    return QUOTE_NONE


def quote_gaps(board_dir, schema, faces, rows, design_map=None, kept=()) -> list:
    """事前審査の穴の引用の誤りの行（設計が無い・問いが立たない run では空）。faces は unit_keys を単位の名にした穴、rows は案の行
    （unit_keys は単位の名・item は項目の番号）。why が DRIFT_HEAD か UNPAIRED_HEAD で始まる穴ごとに、why の引用「…」が
    独立設計の文に字のまま在る物と、穴の unit_keys が重なる案の行（どれにも重ならなければ rows の全部）の approach・files・
    allowed_paths・shrink_first に字のまま在る物が 1 つ以上ずつ要り、どちらにも無い引用は誤り。design_map を渡した時（None は
    求めない）は rows の files の (項目, path, symbol) ごとに 1 行を求め（_map_gaps。kept の鍵は求めない）、design_quote の実在を照らす"""
    got = stands(board_dir, schema)
    if got is None:
        return []
    source = got.get("design") or ""
    rows = [r for r in rows if isinstance(r, dict)]
    out = []
    for f in faces if isinstance(faces, list) else []:
        why = f.get("why") if isinstance(f, dict) else None
        if not (isinstance(why, str) and why.startswith(QUOTE_HEADS)):
            continue
        keys = {str(k) for k in f.get("unit_keys") or []}
        mine = [r for r in rows if keys & {str(k) for k in r.get("unit_keys") or []}] or rows
        off_design = cite.missing_quotes(why, source)
        off_rows = cite.missing_quotes(why, TEXT_SEP.join(_row_text(r) for r in mine))
        found = cite.quotes(why)
        name = f"穴 {f.get('key')}"
        if len(off_design) == len(found):
            out.append(f"{name}: why に独立設計の文に字のまま在る引用「…」が無い（独立設計の行を「…」で引け）")
        if len(off_rows) == len(found):
            out.append(f"{name}: why に案の行（{'・'.join(ROW_QUOTE_KEYS)}）に字のまま在る引用「…」が無い（案の行を「…」で引け）")
        out += [f"{name}: 引用「{q}」が独立設計にも案の行にも字のまま無い（「」は独立設計と案の行の引用だけに使い、"
                "ほかの引用は『』か `…` で書く）" for q in dict.fromkeys(off_design) if q in off_rows]
    if design_map is not None:
        out += _map_gaps(source, rows, design_map, got.get("elements"), kept)
    return out
