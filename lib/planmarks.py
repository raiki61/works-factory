"""修正案の項目の works 側の欄（依頼 217 = 206 + 207）。

修正案の役（p2.fix_plan）の項目の行に、直し方の道（route・route_why）・受け入れのテスト（tests）・書き換える既存のテスト
（rewrite_tests）・整えの申告（refactor）・書いてよいパス（allowed_paths）・触らない物（out_of_scope。依頼 218）を書かせる。承認された案は後で項目ごとの brief に切り出され、修正役・TDD の役が従う
要求の正本になる。欄は役の型（block の output_format）にだけ在り、受け付けが盤面へ渡す前に外して盤面の plan-fields.json（FIELDS_FILE）に置く。
- gaps(reply, repo, exists=): 欠けと誤りの行（files の行の誤り——symbols の name がパスの形か行の path の拡張子で終わる・同じ
  (path, name, change) の重なり・considered の path の誤り・消す側の訳 why の欠け——も。修正案の受け付けが拒む。拒否の理由は書いた役に戻り、その役が直せる）。exists は
  受け入れのテストが既に在るかを引く口（既定は作業ツリー。同じ run の中の案の直しは修正の起点の版の木）
- find_test(repo, test_id): テストの id の定義の行（rewrite_tests は在るテストだけ・tests は無いテストだけを名指す）
- line_in(src, test_id): 渡したファイルの中身でのテストの id の定義の行（凍結の検査が輪の後の木で引き直す）
- id_at(src, path, line)・map_range(old, new, first, last)・map_line(old, new, line): line_in の逆（行を含む関数の id）と、行の番号を
  別の版の木へ移す口
  （範囲の相談の合意の行は修正前の版の行で、凍結の検査が読む木へはこの 2 つで移す）
- split(reply, repo, base_tests=)・save(board, rnd, fields)・read(b)・rewrites(b)・removes_permits(b): 欄を外す口・盤面の控え・書き換えてよい既存のテストの並び・
  files の change=remove の symbol（消す名）をコードの識別子（と点の付いたパス・属性の名の文字列）として使う既存のテストの並び（base_tests は
  修正前の版のテストの中身。split が欄 removes_tests に置く許しの行）
- FILES_SCHEMA・FILE_OPS・SYMBOL_CHANGES: 修正案の項目の欄 files（ファイル構成の行。足す物・消す物を 1 ファイルごとの {path, op, from?,
  responsibility, symbols:[{name, change, why?, replaced_by?}], home:{concept, why}, considered:[{path, why_not}], why?, replaced_by?} にした物）の型の住処（yaml の plan_reply の
  files はその写し）。読みの口は file_rows(item)・symbol_rows(row)・file_symbols(item, change)・file_paths(item, ops)・removed_paths(item)。読み手（planscope・ripple・design・
  planbrief）は欄の字を自分で読まず、この口を引く
- IDENT・search_word(name)・declared_name(d)・word_re(name)・test_functions(src, path)・test_names(src, path)・test_defs(tree, path)・code_idents(node)・DOTTED_NAME: files の
  symbols の name を差分や本体で探す語の決まり（1 行の読み方）・テストの関数の源の引き（blk-fix の planscope・tddloop・blk-plan の ripple が
  同じ物を呼ぶ）・テストの関数がコードで使う名の引き（split が removes_tests を引く）・コードの識別子の名の集めと、名と読む点の付いた文字列の形（tddloop も
  使う）
- 項目の間の依存（DEPENDS_KEY=depends_on。後の項目が前の項目の単位と受ける物を書く works の欄）: depends_gaps(items) は案の全体を受ける
  依存の照らしの 1 つの口（take_plan と案の直しの _plan_errors が案の全体を渡して呼ぶ）、home_gaps(items) は同じ案の全体を受ける考えの住処の
  照らし（files の行の home.concept が案の 2 行に出たら拒む。純な関数）、depends_pairs(items, among=None) は組を作る
  (前の単位, 後の単位) の対（among の外の単位を通る依存は中の端どうしに縮める）、renumber(item, name_of) は UNIT_REFS の欄の単位の no を名に戻す
  （planfile.named が呼ぶ）
- unit_contract(fields, key): 1 つの単位の約束（その単位を名指す項目の道・受け入れのテスト・書き換えの id・整えの申告を合わせた物。TDD の輪が読む）
- append_trace(folder, op, **row): 開いた盤面の書き口の無い時に trace.jsonl（TRACE_FILE）へ足す行 {t, op, …}（save と planfile が書く）
- 凍結（SAVED_OP・frozen(b)・FieldsBroken）: save は控えを置いた後、盤面の trace に印 {round, sha256（控えのバイトの sha256）} を
  1 行書く。テストの変更の許しの元（rewrites）と brief の切り出しは frozen で読み、今の周の印と控えが食い違えば（受け付けの後に
  書き換えた・消した）FieldsBroken。読む側が盤面を止める（黙って許しを広げない・黙って捨てない）。印の無い控えは無い物（None）
- 構造の欄 structure（計画 2026-10-09-clean-whole の Task 2.4・計画 world-solution の W8）: structure_gaps(plan, tables) が、答えの
  要る行の表（Need）ごとに、項目に要る行の「従う（follows）か外れの訳（deviation）」の欠けと誤りの行と、どの項目も答えていない行を
  返す（修正案の受け付けと同じ run の中の案の直しが拒む）。表は構造の目が汚れると見た単位（design_need。行の鍵 row）と世界の解の
  答えの要る行（worldmark.need。行の鍵 world）で、答えの仕組みは 1 つ。判定の処方への答え（prescription）も同じ欄に並べてよい
  （要るのは表の行だけ）。deviations(fields) は控えの欄から外れの訳の並びを引く（事前審査の頭・報告・最後の関所が読む）。
  prescriptions(b) は判定の返答（盤面の節 JUDGE_NODE の最新の出力）の単位ごとの処方（写しの盤面の記録は単位の処方を写さない
  ので、修正案の頭と修正役の brief はここから引く。利用者の声 D2）
- MACHINE_KEY・machine_face_gaps(faces): 欄の行のうち機械が足し修正案の役が直せない欄（removes_tests）。where でそれを名指す block の
  穴は事前審査の受け付けが拒む（役が直せない穴で案の往復を回さない）
- 範囲の欄の glob の読み（誤り glob_problem・当たり glob_match・交わり globs_meet）と根の外への上り climbs は lib/globs.py。gaps は
  誤った glob と、out_of_scope の glob が tests・rewrite_tests の id のファイルに当たる案を拒む
- approved_items(b): 今の周の承認済みの修正案の項目と凍結した欄を同じ番号で合わせた並び（修正の受け付けが差分と照らす）
- joined(it, f): 案の項目の行に同じ番号の欄の行の KEYS を重ねた行（approved_items と事前審査の往復の控えの行が使う）
- handed(ruling, items): 裁かれた項目の番号の字（fix の replan_items）を案の項目の番号に読み、番号でない行と案の外の番号は訳を返す
  （案の直しの周を開く planfile と、案の直しの事前審査を開く boardview が同じ物を呼ぶ）
- 約束の欄と手段の欄（依頼 226）: CONTRACT_KEYS・CONTRACT_TEST_KEYS（tests[] の行の約束の欄）は変えると関所に戻す物、
  MEANS_KEYS は修正案の役が同じ run の中で直してよい物。contract_diff(old, new) が違う約束の欄の名を返す
  widened(old, new) は違いが範囲を広げる欄（WIDEN_KEYS: allowed_paths に足す・out_of_scope から外す）だけの時に足した・外した glob を返す
- 承認済みの項目の差し替え（依頼 226）の控え: 核の欄（CORE_KEYS）を控えの AMENDED_KEY に置き、trace に AMEND_OP を書いた物を
  amended(b)・plan_items(b) が読む
- scoped(items): 範囲の欄の在る項目の並びか（217 番の形の控えは範囲の無い run と同じに扱う 1 つの決まり。
  修正の受け付けの範囲の照らしと差分の審査の準拠の受け付けが使う）

写しの engine の型の検査と時刻（engine.schema・engine.util。L0 の写し）と JSON の読み書き jsonfile・glob の読み globs だけを使い、entry・conflict を import しない（conflict がこのモジュールを読むので、
輪を作らない）。
"""
from __future__ import annotations

import ast
import copy
import difflib
import graphlib
import hashlib
import json
import pathlib
import posixpath
import re
import sys
from typing import Callable, NamedTuple

_GL = pathlib.Path(__file__).resolve().parent / "graphloops"
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

from engine.schema import validate_schema  # noqa: E402
from engine.util import now  # noqa: E402
import globs  # noqa: E402
import jsonfile  # noqa: E402

STEPS = ("plan", jsonfile.EACH)   # 返答の中の欄を持つ行（修正案の項目）の道
NODE = "p2.fix_plan"   # 盤面の記録で修正案の返答を引く節（plan_items。前の marks の種 plan の節）
FIELDS_FILE = "plan-fields.json"   # 盤面の根の控え {"round": 周, "fields": [項目ごとの欄], "amended"?: {番号: 核の欄}}
SAVED_OP = "plan_fields_saved"     # save が盤面の trace に書く凍結の印 {round, sha256}
TRACE_FILE = "trace.jsonl"
DEPENDS_KEY = "depends_on"       # 項目の間の依存の欄の名（1 か所。ITEMS_RULE・REJECT・planbrief が貼る）
KEYS = ("route", "route_why", "tests", "rewrite_tests", "refactor", "allowed_paths", "out_of_scope", "structure", DEPENDS_KEY)
# 写しの graph の修正案の項目の欄（核）。差し替えた項目のこの欄を控えの AMENDED_KEY に置く（approved_items が足す鍵 item は外す）
CORE_KEYS = ("unit_keys", "approach", "files", "shrink_first", "narrows")
# 約束の欄（変えると関所に戻す物）と手段の欄（同じ run の中で修正案の役が直してよい物）。tests[] の行は CONTRACT_TEST_KEYS の
# 欄だけが約束で、ほかの欄（id・path・red_kind・red_why）は手段。files は消す側（op が delete・rename の行と change=remove の
# symbol。_contract_value）だけが約束で、足す側は手段
CONTRACT_KEYS = ("unit_keys", "narrows", "files", "allowed_paths", "out_of_scope", "rewrite_tests")
CONTRACT_TEST_KEYS = ("behavior",)
MEANS_KEYS = ("approach", "files", "shrink_first", "route", "route_why", "tests", "refactor", "structure", DEPENDS_KEY)
# 範囲を広げる欄（widened が見る）: allowed_paths に足す・out_of_scope から外すだけの直しは、範囲を広げるだけの直し
WIDEN_KEYS = ("allowed_paths", "out_of_scope")
AMENDED_KEY = "amended"            # 控えの鍵 {"<項目の番号>": {CORE_KEYS の欄}}（差し替えた項目の核の欄）
AMEND_OP = "plan_amended"          # 差し替えの trace の行（planfile が書く） {round, items: [番号…]}（SAVED_OP の行の直後）
# route_why は route が tdd でない時だけ要る（gaps が見る）
REQUIRED = ("route", "tests", "rewrite_tests", "refactor", "allowed_paths", "out_of_scope")
# 範囲の相談の合意で入る新しいテストだけが使う赤の種類: 守りのテスト（base で緑でよい。人の条件「X を壊さないことを確かめよ」の型）。
# 修正案の役の tests は今どおり赤を求めるので RED_KINDS には入れない
GUARD_KIND = "guard"
AGREED_RED = "red"   # 合意の新しいテストの赤の種類のもう 1 つ: base で赤（failure）を求める（落ち方は機械が照らさない。red_check の事実だけ）
AGREED_KINDS = (AGREED_RED, GUARD_KIND)   # 範囲の相談の答えの new_tests の red_kind（赤か守りか）
MIN_DEVIATION = 20   # 構造の目の避け方・処方から外れる訳の字の下限
# 項目の works の欄の行の型の住処は lib/plan-item-fields.schema.json の 1 か所（盤面の控え plan-fields.json の fields の行の形。
# port の宣言 shared:plan-fields.schema.json もそれを名指す）。返答の欄の型 FIELD_SCHEMA と、ファイル構成の行 files（足す物・消す物を、
# 1 ファイルごとの path・操作・受け持ちと、そのファイルの symbols の行にした物）の型 FILES_SCHEMA はそこから引き、写しを持たない
# （workflows/plan/works-factory-plan.yaml の plan_reply の同じ欄は、グラフの output_format が形を字でしか持てないための写しで、一致を試験が縛る）
ROW_SCHEMA_FILE = "plan-item-fields.schema.json"
_ROW = json.loads((pathlib.Path(__file__).resolve().parent / ROW_SCHEMA_FILE).read_text(encoding="utf-8"))["properties"]
FILES_SCHEMA = _ROW["files"]
MIN_WHY = FILES_SCHEMA["items"]["properties"]["why"]["minLength"]   # 訳の欄（消す訳 why・route_why など）の字の下限
FILE_OPS = tuple(FILES_SCHEMA["items"]["properties"]["op"]["enum"])          # 行の操作。rename は元のパス from を持つ
SYMBOL_CHANGES = tuple(FILES_SCHEMA["items"]["properties"]["symbols"]["items"]["properties"]["change"]["enum"])   # symbols の行の変え方
# 直し方の語。tdd・direct のほか、項目がどんな直しかの見分けの 3 語（持ち主の答え。docs/plans/2026-10-24-fix-weapons.md の 9.1 の 10）:
# static は試験で示す振る舞いの無い直し・tidy は利用者から届かない使われていない物を消す直し・pin はコードが正しく試験だけが欠けた直し。
# 修正の段は語を表で型に引くだけで、語を推し量らない（workflows/fix/src/route.py）
ROUTES = tuple(_ROW["route"]["enum"])
RED_KINDS = tuple(_ROW["tests"]["items"]["properties"]["red_kind"]["enum"])
# 項目の欄のうち単位の no（か単位の字）を持つ欄の表 (欄の名, 行の中の鍵)。鍵が None の欄は単位の並びそのもの、鍵が在る欄は
# その鍵に単位を持つ object の並び。renumber が回す
UNIT_REFS = (("unit_keys", None), (DEPENDS_KEY, "unit"))
# 返答の欄の型（KEYS の欄）。控えの行の rewrite_tests の limit は split が足す欄で、修正案の役は書かない
FIELD_SCHEMA = {k: copy.deepcopy(_ROW[k]) for k in KEYS}
del FIELD_SCHEMA["rewrite_tests"]["items"]["properties"]["limit"]

STRUCTURE_REJECT = ("修正案の項目の works の欄 structure に欠けか誤りが在る（構造の目が汚れると見た単位を持つ項目は、その行ごとに"
                    "避け方に従うか外れの訳を書く。世界の解の答えの要る行は、行ごとにどれかの項目が定石に従うか外れの訳を"
                    "書く）。拒んだ行:")
ANSWER_KEYS = ("row", "prescription", "world")   # 欄 structure の行が答える先の鍵（ちょうど 1 つ）
REJECT = ("修正案の項目の works の欄（route・tests・rewrite_tests・refactor・allowed_paths・out_of_scope・depends_on）か、files の行"
          "（symbols の name・消す行の why・replaced_by・home・considered）に欠けか誤りが在る。拒んだ行:")
DEPENDS_REJECT = (f"修正案の項目の依存 {DEPENDS_KEY} に誤りが在る（unit は案の項目の unit_keys の字・自分の項目の単位でない・受ける物は"
                  "その項目の files の <パス>::<名前> か <パス>・依存は循環しない）。拒んだ行:")
MACHINE_KEY = "removes_tests"   # 欄の行のうち split が足し、修正案の役が書かない・直せない欄。rewrite_tests の limit も split が
# 足すが、役の書く id から決まり、その行への block は役が id を直して答えられるので、わざと入れない


# ---------------------------------------------------------------- 役の型


# ---------------------------------------------------------------- テストの定義の行
def _parse_id(test_id):
    """id → (根からの相対パス, [名前…]（1 つか 2 つ）)。形が違えば None"""
    if not isinstance(test_id, str):
        return None
    path, *names = test_id.split("::")
    if not path or not 1 <= len(names) <= 2 or not all(names):
        return None
    return path, names


def _resolve(repo: pathlib.Path, path: str):
    """根の中のファイルなら (作業ツリーの根からの相対の綴り, 実体)。根の外（絶対パス・`..` の段・根の外へのリンク）・無いなら
    None。根の外へのリンクは解いた実体の is_relative_to で見る"""
    norm = posixpath.normpath(path)
    if globs.climbs(norm):
        return None
    root = pathlib.Path(repo).resolve()
    real = (root / norm).resolve()
    if not real.is_relative_to(root) or not real.is_file():
        return None
    return norm, real


def _py_line(src: str, names: list):
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    body = tree.body
    *outer, name = names
    for cls in outer:
        got = [n for n in body if isinstance(n, ast.ClassDef) and n.name == cls]
        if not got:
            return None
        body = got[0].body
    fn = [n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    return fn[0].lineno if fn else None


IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")   # files の symbols の name が識別子の形か


def search_word(name) -> str | None:
    """files の symbols の name で差分や本体を探す語（:: と . で割った最後の段）。識別子の形でない名と、/ を含む名（欄の指し
    /plan/files のような字。パスは行の path に書くので、name の / は欄の指しだけ）は None（語では確かめない）"""
    if not isinstance(name, str) or not IDENT.match(name) or "/" in name:
        return None
    last = re.split(r"::|\.", name)[-1]
    return last or None


def declared_name(d) -> str:
    """名 d 1 つが宣言する名前（'(' より前を見る）: <パス>::<名前> は :: の後の最後の . の後・.py のパスはモジュールの名
    （__init__.py はディレクトリの名。拡張子 py と比べない。receivers.py は receivers）・ほかは最後の . の後"""
    s = str(d).split("(", 1)[0].strip()
    if "::" in s:
        return s.rsplit("::", 1)[-1].rsplit(".", 1)[-1]
    if s.endswith(".py"):
        p = posixpath.normpath(s[:-3])
        return posixpath.basename(posixpath.dirname(p)) if posixpath.basename(p) == "__init__" else posixpath.basename(p)
    return s.rsplit(".", 1)[-1]


def word_re(name: str):
    """探す語 name を語の境で探す型（前後が語の字でない）"""
    return re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])")


def test_defs(tree, path: str):
    """木 tree の、名前が test で始まる関数（モジュールの直下と、クラスの直下のメソッド。入れ子のクラスも辿る）の
    (id, 定義の節) を並びの順に出す（id は test_functions の形）"""
    def walk(body, head):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                yield f"{head}::{node.name}", node
            if isinstance(node, ast.ClassDef):
                yield from walk(node.body, f"{head}::{node.name}")

    return walk(tree.body, path)


def _parse_py(src: str, path: str):
    if not path.endswith(".py"):
        return None
    try:
        return ast.parse(src)
    except (SyntaxError, ValueError):
        return None


def test_functions(src: str, path: str) -> dict[str, str]:
    """.py の中身 src から、名前が test で始まる関数（モジュールの直下と、クラスの直下のメソッド。入れ子のクラスも辿る）の
    id（実行器の node id の形 `<path>::<クラス>[::<内のクラス>…]::<名前>` か `<path>::<名前>`）→ その関数の源
    （ast.get_source_segment。デコレータの行から）。構文が読めない・path が .py でなければ {}。純粋"""
    tree = _parse_py(src, path)
    out = {}
    for tid, node in test_defs(tree, path) if tree else ():
        top = min([node.lineno] + [d.lineno for d in node.decorator_list])
        span = ast.Constant(value=None, lineno=top, col_offset=node.col_offset, end_lineno=node.end_lineno,
                            end_col_offset=node.end_col_offset)   # デコレータの行から本体の終わりまで
        out[tid] = ast.get_source_segment(src, span) or ""
    return out


def code_idents(node) -> set[str]:
    """節 node の下でコードの識別子として使う名（名前・属性・引数・キーワード・import の各段と別名・定義の名。注釈の中の名も）。
    文字列の中の語（文字列で書いた注釈 "Book" も）は入れない（文字列のどれを名と読むかは呼び手が足す。planmarks._code_names・
    tddloop._old_names）。`from X import Y` の X は名前空間に名を作らないので入れない"""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, (ast.arg, ast.keyword)):
            out.add(n.arg or "")
        elif isinstance(n, ast.alias):
            out.update(n.name.split("."))
            out.add(n.asname or "")
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
    out.discard("")
    return out


DOTTED_NAME = re.compile(r"[A-Za-z_][\w.]*")   # 識別子か点の付いた名の形の文字列（fullmatch で使う）
_ATTR_CALLS = frozenset({"setattr", "getattr", "hasattr", "delattr"})


def _attr_name_arg(call):
    """呼び call が属性の名を文字列で渡す形（setattr・getattr・hasattr・delattr（monkeypatch.setattr も）と *.patch.object の
    2 つ目の引数）なら、その文字列の節。ほかは None"""
    f = call.func
    name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
    patch_object = name == "object" and isinstance(f, ast.Attribute) and (
        getattr(f.value, "id", None) == "patch" or getattr(f.value, "attr", None) == "patch")
    if (name in _ATTR_CALLS or patch_object) and len(call.args) >= 2:
        return call.args[1]
    return None


def _code_names(node) -> set[str]:
    """節 node（デコレータも含む）の下でコードの識別子として使う名（code_idents）と、`from X import Y` の X の各段と、点の付いた
    パスの形の文字列の各段（mock.patch("pkg.mod.Name") の pkg・mod・Name）と、属性の名として渡す識別子の文字列
    （setattr(mod, "Name", …) の Name）。ほかの文字列（文字列で書いた注釈も）の中の語は入れない"""
    out = code_idents(node)
    for n in ast.walk(node):
        if isinstance(n, ast.ImportFrom):
            out.update((n.module or "").split("."))
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and "." in n.value and DOTTED_NAME.fullmatch(n.value):
            out.update(n.value.split("."))
        elif isinstance(n, ast.Call):
            arg = _attr_name_arg(n)
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.isidentifier():
                out.add(arg.value)
    out.discard("")
    return out


def test_names(src: str, path: str) -> dict[str, set[str]]:
    """test_functions と同じ id → その関数（デコレータから本体の終わりまで）がコードで使う名（_code_names）。構文が読めない・
    path が .py でなければ {}。純粋"""
    tree = _parse_py(src, path)
    return {tid: _code_names(node) for tid, node in test_defs(tree, path)} if tree else {}


# ---------------------------------------------------------------- files の読みの口（行の型 FILES_SCHEMA の読み手は全部ここを引く）
def file_rows(item) -> list[dict]:
    """項目 item の files の行（object の物だけ。files が並びでなければ空）"""
    rows = item.get("files") if isinstance(item, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def symbol_rows(row: dict) -> list[dict]:
    """行 row の symbols の行（object の物だけ）"""
    rows = row.get("symbols")
    return [s for s in rows if isinstance(s, dict)] if isinstance(rows, list) else []


def file_symbols(item, change: str | None = None) -> list[tuple[str, str]]:
    """項目 item の files の (path, name) の並び（現れた順・重なりは 1 つ）。change（SYMBOL_CHANGES）を渡せばその変え方の symbol だけ。
    path か name が字でない行は並べない"""
    out = []
    for row in file_rows(item):
        path = row.get("path")
        for sym in symbol_rows(row):
            name = sym.get("name")
            if isinstance(path, str) and isinstance(name, str) and (change is None or sym.get("change") == change):
                out.append((path, name))
    return list(dict.fromkeys(out))


def file_paths(item, ops) -> list[str]:
    """項目 item の files のうち op が ops の行の path の並び（現れた順・重なりは 1 つ）"""
    return list(dict.fromkeys(r["path"] for r in file_rows(item) if r.get("op") in ops and isinstance(r.get("path"), str)))


def removed_paths(item) -> list[str]:
    """項目 item の files で、この直しの後に無くなるパス: op=delete の行の path と、op=rename の行の元のパス from（現れた順・重なりは 1 つ）"""
    out = []
    for row in file_rows(item):
        old = row.get("path") if row.get("op") == "delete" else row.get("from") if row.get("op") == "rename" else None
        if isinstance(old, str) and old:
            out.append(old)
    return list(dict.fromkeys(out))


def _naming_removes(item: dict, base_tests: dict) -> list[dict]:
    """項目 item の files の change=remove の symbol の名（消す名）の探す語（search_word）を、base_tests（パス → 修正前の版のテストの
    ファイルの中身）のテストの関数がコードの識別子（と点の付いたパス・属性の名の文字列）として使う所（test_names）から探し、当たった
    関数の行 {id, limit: "<パス>:<定義の行>"} を並びの順で返す。この直しの後に無くなる .py（removed_paths: op=delete の path と
    op=rename の元のパス from）のモジュールの名も消す名の語に数える（消える・移るモジュールの旧名を使う修正前のテストにも許しを
    並べる）。ほかの文字列（文字列で書いた注釈も）の中の同じ語は当たりにしない
    （ありふれた語で関わらないテストへ許しを広げない）。定義の行が引けない関数（入れ子のクラスの中など）は並べない（許しを広げない）"""
    words = {w for w in map(search_word, (name for _, name in file_symbols(item, "remove"))) if w}
    words |= {declared_name(p) for p in removed_paths(item) if p.endswith(".py")} - {""}
    out = []
    for path, text in (base_tests if words else {}).items():
        for tid, names in test_names(text, path).items():
            line = line_in(text, tid) if words & names else None
            if line:
                out.append({"id": tid, "limit": f"{posixpath.normpath(path)}:{line}"})
    return out


def line_in(src: str, test_id: str) -> int | None:
    """テストの id のファイルの中身 src での定義の行（1 始まり。引き方は find_test と同じ）。id の形が違う・名前が無いなら None。
    .py かは _resolve と同じく整えたパス（posixpath.normpath。`t.py/` は t.py）で決める"""
    got = _parse_id(test_id)
    if got is None or not isinstance(src, str):
        return None
    path, names = got
    if posixpath.normpath(path).endswith(".py"):
        return _py_line(src, names)
    return next((i for i, line in enumerate(src.splitlines(), 1) if names[-1] in line), None)


def id_at(src: str, path: str, line: int) -> str | None:
    """.py の中身 src の line 行目を含む最も外側の関数（メソッドも）のテストの id（`<path>::<クラス>…::<名前>`。line_in の逆）。
    関数の外の行・.py でない・構文が読めないなら None"""
    if not path.endswith(".py"):
        return None
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    best = []

    def walk(body, chain):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top = min([node.lineno] + [d.lineno for d in node.decorator_list])
                if top <= line <= node.end_lineno and not best:
                    best[:] = [*chain, node.name]
            elif isinstance(node, ast.ClassDef):
                walk(node.body, [*chain, node.name])
    walk(tree.body, [])
    return "::".join([path, *best]) if best else None


def map_range(old: str, new: str, first: int, last: int) -> tuple[int, int] | None:
    """old の first〜last 行目（1 始まり）が、new にそのまま（途中に足した行も書き換えた行も無く）在れば、その行の幅。
    行の番号を別の版の木へ移す口（範囲の指しを別の木で読む）。移せなければ None"""
    got = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False).get_opcodes()
    for tag, i1, i2, j1, _ in got:
        if tag == "equal" and i1 < first <= last <= i2:
            return j1 + first - i1, j1 + last - i1
    return None


def map_line(old: str, new: str, line: int) -> int | None:
    """old の line 行目と同じ行が new に在れば、その行の番号（map_range の 1 行）"""
    got = map_range(old, new, line, line)
    return got[0] if got else None


def find_test(repo: pathlib.Path, test_id: str) -> int | None:
    """<パス>::<クラス>::<名前> か <パス>::<名前> のテストの定義の行（1 始まり）。.py は ast でクラスと関数を引き（行は def の行）、
    ほかの拡張子は名前を含む最初の行。根の外・ファイルが無い・構文が壊れている・名前が無いなら None"""
    got = _parse_id(test_id)
    found = _resolve(repo, got[0]) if got else None
    if found is None:
        return None
    try:
        src = found[1].read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return line_in(src, test_id)


def _path_problem(repo: pathlib.Path, test_id: str) -> str | None:
    """テストの id のパスの誤りの文（\\ の区切り・作業ツリーの根からの相対でない）。無ければ None。ファイルの有無は見ない
    （tests はまだ無いテストを名指す）"""
    if "\\" in test_id:
        return "パスに \\ が在る（区切りは / で書け。パスは作業ツリーの根からの相対）"
    got = _parse_id(test_id)
    if got is None:
        return None
    norm = posixpath.normpath(got[0])
    root = pathlib.Path(repo).resolve()
    if globs.climbs(norm) or not (root / norm).resolve().is_relative_to(root):
        return "パスが作業ツリーの根からの相対でない（絶対パス・根の外を指す。/ で書いた根からの相対にせよ）"
    return None


def _limit(repo: pathlib.Path, test_id: str):
    """書き換えてよい範囲 "<パス>:<定義の行>"（パスは根からの相対の綴り）。引けなければ None"""
    line = find_test(repo, test_id)
    return f"{posixpath.normpath(_parse_id(test_id)[0])}:{line}" if line else None


# ---------------------------------------------------------------- 約束の欄の比べ
def _canon(v) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def _removal_side(it: dict) -> list:
    """項目 it の files の消す側だけ: op が delete・rename の行（path と元のパス from）と、change=remove の symbol（path と name）を
    並べ替えた並び。足す側（op が create・modify の行・change=add の symbol）と訳（why・replaced_by）・受け持ち・home・considered は入れない"""
    gone = [{"op": r.get("op"), "path": r.get("path"), "from": r.get("from")} for r in file_rows(it)
            if r.get("op") in ("delete", "rename")]
    gone += [{"symbol": name, "path": path} for path, name in file_symbols(it, "remove")]
    return sorted(gone, key=_canon)


def _contract_value(it: dict, key: str) -> str:
    """約束の欄 key の比べる字（欄が無い・None は空の並びと同じ。unit_keys は並べ替える。rewrite_tests の行は型の欄
    （FIELD_SCHEMA）だけで比べる——凍結の控えの行は split が足した範囲 limit を持ち、返答の行は型で持てないので。files は
    消す側 _removal_side だけに写して比べる——足す側は手段の欄で、同じ run の中で関所に戻さずに直せる）"""
    if key == "files":
        return _canon(_removal_side(it))
    v = it.get(key) if isinstance(it, dict) else None
    v = [] if v is None else v
    if key == "unit_keys" and isinstance(v, list):
        v = sorted(v, key=_canon)
    if key == "rewrite_tests" and isinstance(v, list):
        props = FIELD_SCHEMA["rewrite_tests"]["items"]["properties"]
        v = [{k: row[k] for k in props if k in row} if isinstance(row, dict) else row for row in v]
    return _canon(v)


def _test_contract(it: dict) -> str:
    """tests[] の行の約束の欄（CONTRACT_TEST_KEYS）の並べ替えた並びの字"""
    rows = [{k: row.get(k) for k in CONTRACT_TEST_KEYS} for row in _rows(it, "tests") if isinstance(row, dict)] \
        if isinstance(it, dict) else []
    return _canon(sorted(rows, key=_canon))


def contract_diff(old: dict, new: dict) -> list[str]:
    """2 つの項目の約束の欄のうち違う物の名（CONTRACT_KEYS の順。最後に tests[] の behavior の並びが違えば "tests.behavior"）。
    手段の欄（MEANS_KEYS・tests[] の id・path・red_kind・red_why）だけの違いは空。比べは json.dumps（sort_keys）の字で、
    unit_keys と tests の行は並べ替えて比べ、欄が無いのと空の並びは同じと読む。narrows は関所の決め手の欄を外した形で渡す。純粋"""
    out = [k for k in CONTRACT_KEYS if _contract_value(old, k) != _contract_value(new, k)]
    if _test_contract(old) != _test_contract(new):
        out.append("tests.behavior")
    return out


def _item_value(it: dict, key: str) -> str:
    """項目の欄 key の比べる字（約束の欄は _contract_value、tests は行の全部の欄を並べ替えた並び、ほかは字のまま。無いのは None）。
    files は足す側も違いに数える（widened が、足す側を変えて範囲も広げた直しを『範囲を広げただけ』と読まないように。消す側だけに
    写すのは contract_diff の約束の比べ）"""
    if key in CONTRACT_KEYS and key != "files":
        return _contract_value(it, key)
    v = it.get(key) if isinstance(it, dict) else None
    if key == "tests" and isinstance(v, list):
        v = sorted(v, key=_canon)
    return _canon(v)


def _scope_rows(it: dict, key: str) -> list:
    return _rows(it, key) if isinstance(it, dict) else []


def widened(old: dict, new: dict) -> dict | None:
    """直した項目 new が承認済みの項目 old の範囲を広げただけか。違いが allowed_paths に足した行と out_of_scope から外した行
    （WIDEN_KEYS）だけで、どちらかが 1 行以上在れば {"allowed_paths": [足した glob…], "out_of_scope": [外した行の glob…]}（new・old
    の並びの順）。ほかの欄（約束の欄も手段の欄も。tests は行の全部の欄）が 1 つでも違う・allowed_paths から外した・out_of_scope に
    足したか行を書き換えた・何も広げていない・足した glob が誤り（glob_problem。**/?* のような丸ごとの許しも）
    なら None。比べは contract_diff と同じ読み（unit_keys と tests の並べ替え・rewrite_tests の範囲 limit は数えない）。narrows は関所の決め手の欄を外した形で渡す。純粋"""
    if not isinstance(old, dict):
        return None
    keys = (set(old) | set(new)) - set(WIDEN_KEYS)
    if any(_item_value(old, k) != _item_value(new, k) for k in keys):
        return None
    old_paths = {_canon(p) for p in _scope_rows(old, "allowed_paths")}
    new_paths = {_canon(p) for p in _scope_rows(new, "allowed_paths")}
    old_oos = {_canon(r) for r in _scope_rows(old, "out_of_scope")}
    new_oos = {_canon(r) for r in _scope_rows(new, "out_of_scope")}
    if not old_paths <= new_paths or not new_oos <= old_oos:
        return None
    added = list(dict.fromkeys(p for p in _scope_rows(new, "allowed_paths") if _canon(p) not in old_paths))
    if any(not isinstance(p, str) or globs.glob_problem(p) for p in added):   # 誤った・丸ごとの glob は広げるだけと数えない（聞く）
        return None
    removed = [r.get("glob") if isinstance(r, dict) else r for r in _scope_rows(old, "out_of_scope") if _canon(r) not in new_oos]
    if not added and not removed:
        return None
    return {"allowed_paths": added, "out_of_scope": removed}


# ---------------------------------------------------------------- 受け付け
def _rows(it: dict, key: str) -> list:
    rows = it.get(key)
    return rows if isinstance(rows, list) else []


def _id_of(row):
    tid = row.get("id") if isinstance(row, dict) else None
    return tid if isinstance(tid, str) else None


def test_paths(it: dict) -> list[str]:
    """項目の tests・rewrite_tests の id のファイル（整えた根からの相対の綴り・現れた順・重なりは 1 つ）。書いてよい範囲に入る"""
    out = []
    for key in ("tests", "rewrite_tests"):
        for row in _rows(it, key):
            got = _parse_id(_id_of(row))
            if got:
                norm = posixpath.normpath(got[0])
                if norm not in out:
                    out.append(norm)
    return out


def _scope_overlaps(plan: list) -> list[str]:
    """out_of_scope の glob が、案のどれかの項目の tests・rewrite_tests の id のファイルに当たる行（書けと言うファイルを触るなとも
    言う食い違い。修正の段へ渡さずに案を直させる）"""
    out = []
    named = [(n, p) for n, it in enumerate(plan, 1) if isinstance(it, dict) for p in test_paths(it)]
    for i, it in enumerate(plan):
        for j, row in enumerate(_rows(it, "out_of_scope") if isinstance(it, dict) else []):
            g = row.get("glob") if isinstance(row, dict) else None
            if not isinstance(g, str) or not g or globs.glob_problem(g):
                continue
            for n, p in named:
                if globs.glob_match(p, g):
                    out.append(f"plan[{i}].out_of_scope[{j}].glob（{g}）: 項目 {n} の tests・rewrite_tests の id のファイル {p} に"
                               "当たる（書けと言うファイルを触るなとも言っている。glob を狭めるか、テストの置き場を変えよ）")
    return out


def _symbol_problem(path: str, name: str) -> str | None:
    """行の path の symbol の name の誤りの文（無ければ None）: / で始まらずに / を含む（パスの形。/ で始まる字は /plan/files のような
    欄の指しなので通す）か、行の path の拡張子で終わる（ファイルの名。Response.json は app/x.ts の行では通る）。拡張子の表は持たず、
    行の path の拡張子と照らす"""
    if "/" in name and not name.startswith("/"):
        return "パスの形（/ を含む）。パスは行の path に書き、name は識別子で書け"
    ext = posixpath.splitext(path)[1]
    if ext and name.endswith(ext):
        return f"行の path（{path}）の拡張子 {ext} で終わる（ファイルの名でなく識別子で書け。置くファイルは行の path に書く）"
    return None


def _path_problem_of(path) -> str | None:
    """files の行の path・from の誤りの文（\\ の区切り・根の外・整えた形でない。ファイルの有無は見ない）"""
    if not isinstance(path, str) or not path:
        return None
    if "\\" in path:
        return "\\ が在る（区切りは / で書け）"
    norm = posixpath.normpath(path)
    if globs.climbs(norm):
        return "作業ツリーの根からの相対でない（絶対パス・根の外・根そのものを指す）"
    return None if norm == path else f"整えた形でない（./・..・// を含む）。整えた形 {norm} で書け"


def _gone_why(at: str, node: dict, what: str) -> list[str]:
    """消す側の node（at の指し）の why が MIN_WHY 字以上か。what は誤りの文の頭"""
    why = node.get("why")
    if isinstance(why, str) and len(why.strip()) >= MIN_WHY:
        return []
    return [f"{at}.why: {what}は消す訳（why）を {MIN_WHY} 字以上で書く（置き換え先が在れば replaced_by に <パス>::<名前> か <パス> も）"]


def _removal_gaps(i: int, it: dict) -> list[str]:
    """項目 it（plan[i]）の files の消す訳の欠けと、足す側の訳の書き間違い。消す側（op が delete・rename の行と change=remove の
    symbol）は why（MIN_WHY 字以上）が必須で、replaced_by は任意。足す側（op が create・modify の行と change=add の symbol）に
    why・replaced_by を書くのは拒む。型の if-then は output_format に書かず、ここ 1 か所で照らす"""
    out = []
    for j, row in enumerate(it.get("files") if isinstance(it.get("files"), list) else []):
        if not isinstance(row, dict):
            continue
        at = f"plan[{i}].files[{j}]"
        if row.get("op") in ("delete", "rename"):
            out += _gone_why(at, row, f"op={row.get('op')} の行")
        else:
            out += [f"{at}.{k}: 足す側の行（op={row.get('op')}）に {k} は書かない（消す側の行と symbol の物）"
                    for k in ("why", "replaced_by") if k in row]
        for k, sym in enumerate(row.get("symbols") if isinstance(row.get("symbols"), list) else []):
            if not isinstance(sym, dict):
                continue
            sat = f"{at}.symbols[{k}]"
            if sym.get("change") == "remove":
                out += _gone_why(sat, sym, "change=remove の symbol ")
            else:
                out += [f"{sat}.{key}: 足す側の symbol（change={sym.get('change')}）に {key} は書かない（change=remove の symbol の物）"
                        for key in ("why", "replaced_by") if key in sym]
    return out


def _roots(repo: pathlib.Path) -> set[str]:
    """repo の根の直下の名の集合（.git を除く）。根が dir でなければ空（その時は根の名を照らさない）"""
    try:
        return {p.name for p in pathlib.Path(repo).iterdir() if p.name != ".git"}
    except OSError:
        return set()


def _considered_gaps(at: str, row: dict, roots: set[str]) -> list[str]:
    """行 row（at は "plan[i].files[j]"）の considered の path の誤りの行。拒むのは、行の path と同じ path（自分を退けた先に数えない）・
    同じ行で同じ path を 2 度書く・_path_problem_of の形の誤り・2 段以上の path の最初の段が roots（対象の根の名）に無い。1 段の path
    （根に置く新しいファイルの候補）は根の名を照らさない。roots が空なら根の名を照らさない。欄が無い・形が違う行は飛ばす（型が見る）。
    純な関数（作業ツリーの中の在りかは引かない）"""
    out, seen = [], set()
    for k, c in enumerate(row.get("considered") if isinstance(row.get("considered"), list) else []):
        path = c.get("path") if isinstance(c, dict) else None
        if not (isinstance(path, str) and path):
            continue
        here = f"{at}.considered[{k}].path（{path}）"
        bad = _path_problem_of(path)
        if bad:
            out.append(f"{here}: {bad}")
        elif path == row.get("path"):
            out.append(f"{here}: 行の path と同じ（自分を退けた先に数えない。この行が住処にしない別の置き場を書け）")
        elif path in seen:
            out.append(f"{here}: 同じ行の considered に同じ path を 2 度書いた（1 つにまとめ、訳を why_not に続けよ）")
        elif roots and "/" in path and path.split("/", 1)[0] not in roots:
            out.append(f"{here}: 最初の段 {path.split('/', 1)[0]} が対象の根に無い（在る置き場のパスを書け。根に置く新しいファイルの"
                       "候補は 1 段の path で書く）")
        seen.add(path)
    return out


def _files_gaps(i: int, it: dict, roots: set[str]) -> list[str]:
    """項目 it（plan[i]）の files の行の誤り: path・from の形・rename の from・symbols の name（_symbol_problem）・同じ
    (path, name, change) の行の重なり・considered の path の誤り（_considered_gaps）・消す訳の欠け（_removal_gaps）"""
    out, seen = [], {}
    for j, row in enumerate(it.get("files") if isinstance(it.get("files"), list) else []):
        if not isinstance(row, dict):
            continue
        at, path = f"plan[{i}].files[{j}]", row.get("path")
        for key in ("path", "from"):
            bad = _path_problem_of(row.get(key))
            if bad:
                out.append(f"{at}.{key}（{row.get(key)}）: {bad}")
        if row.get("op") == "rename" and not (isinstance(row.get("from"), str) and row["from"]):
            out.append(f"{at}.from: op=rename の行は元のパス from を書く")
        elif row.get("op") != "rename" and "from" in row:
            out.append(f"{at}.from: from は op=rename の行だけが書く（元のパス）")
        for k, sym in enumerate(row.get("symbols") if isinstance(row.get("symbols"), list) else []):
            name = sym.get("name") if isinstance(sym, dict) else None
            if not (isinstance(name, str) and isinstance(path, str)):
                continue
            bad = _symbol_problem(path, name)
            if bad:
                out.append(f"{at}.symbols[{k}].name（{name}）: {bad}")
            key = (path, name, sym.get("change"))
            if key in seen:
                out.append(f"{at}.symbols[{k}]（{path}::{name}・change={key[2]}）: 同じ (path, name, change) の行を {seen[key]} にも書いた"
                           "（1 行にまとめよ）")
            seen.setdefault(key, f"{at}.symbols[{k}]")
        out += _considered_gaps(at, row, roots)
    return out + _removal_gaps(i, it)


def _added_test_gaps(plan: list) -> list[str]:
    """files の symbols に足すテスト（案のどれかの項目の tests・rewrite_tests が名指すファイルの change=add の symbol で、名前が test で
    始まる）が、案のどれかの項目の tests（まだ無いテストの宣言）の id の最後の名に無い行。改名（旧名を消し新名を足す）で新名を tests に
    書かない案は、修正役が範囲の相談で新名を頼むことになる（足してよい新しいテストは tests と範囲の相談の合意だけ）ので、案の受け付けで
    出し直させる。純な関数"""
    items = [it for it in plan if isinstance(it, dict)]
    files = {p for it in items for p in test_paths(it)}
    declared = {(posixpath.normpath(got[0]), got[1][-1]) for it in items for row in _rows(it, "tests")
                if (got := _parse_id(_id_of(row)))}
    out = []
    for i, it in enumerate(plan):
        for j, row in enumerate(file_rows(it) if isinstance(it, dict) else []):
            path = row.get("path")
            if not (isinstance(path, str) and posixpath.normpath(path) in files):
                continue
            for k, sym in enumerate(symbol_rows(row)):
                name = sym.get("name")
                if (sym.get("change") == "add" and isinstance(name, str) and name.startswith("test")
                        and (posixpath.normpath(path), name) not in declared):
                    out.append(f"plan[{i}].files[{j}].symbols[{k}]（{path}::{name}）: 足すテストなのに、案のどの項目の tests にも無い"
                               "（改名なら新しい名も tests に書け。tests に無いテストは修正役が足せず、範囲の相談になる）")
    return out


def gaps(reply: dict, repo: pathlib.Path, *, exists=None) -> list[str]:
    """修正案の返答の works の欄の欠けと誤りの行と、files の行の誤り（symbols の name がパスの形か行の path の拡張子で終わる・
    同じ (path, name, change) の重なり・considered の path の誤り（_considered_gaps。対象の根の名は repo の根を 1 度だけ引く）・
    消す側の訳 why の欠けと足す側の訳の書き間違い。_files_gaps）・files の symbols に足すテストが案のどの項目の tests にも無い行（_added_test_gaps）（"plan[<i>].<欄>…: <理由>"）。案の全体を見る home.concept の重なりは
    home_gaps に在り、ここには入れない。
    空なら通る。項目の間の依存 depends_on の照らしは案の全体を見る depends_gaps に在り、ここでは型（FIELD_SCHEMA）だけを見る
    （案の直しの返答は直した項目だけなので、直さない項目を指す行をここでは照らせない）。返答や plan が形を成さなければ空
    （写しの規則が型で拒む）。例外で拒まない。exists(test_id) -> 定義の行 | None は、受け入れのテスト（tests）が既に在るかを
    引く口（None なら find_test で作業ツリーを引く。同じ run の中の案の直しは修正の起点の版の木で引く）"""
    plan = reply.get("plan") if isinstance(reply, dict) else None
    if not isinstance(plan, list):
        return []
    if exists is None:
        def exists(tid):
            return find_test(repo, tid)
    out, new_ids, kinds, roots = [], {}, {}, _roots(repo)
    for i, it in enumerate(plan):
        if not isinstance(it, dict):
            out.append(f"plan[{i}]: 項目が object でない")
            continue
        for k in REQUIRED:
            if k not in it:
                out.append(f"plan[{i}].{k}: 無い（works の欄。修正案の頭の『修正案の項目の works の欄』を見よ）")
        for k in KEYS:
            if k in it:
                out += validate_schema(it[k], FIELD_SCHEMA[k], f"plan[{i}].{k}")
        route, tests = it.get("route"), it.get("tests")
        if route == "tdd" and isinstance(tests, list) and not tests:
            out.append(f"plan[{i}].tests: route が tdd の項目は受け入れのテストを 1 本以上書く"
                       "（先に書けないなら route を direct にし、route_why に理由を書く）")
        why = it.get("route_why")
        if route == "direct" and not (isinstance(why, str) and len(why.strip()) >= MIN_WHY):
            out.append(f"plan[{i}].route_why: route が direct の項目は、テストを先に書かない理由を {MIN_WHY} 字以上で書く")
        elif route in ROUTES and route not in ("tdd", "direct") and not (isinstance(why, str) and len(why.strip()) >= MIN_WHY):
            out.append(f"plan[{i}].route_why: route が {route} の項目は、その語を選んだ訳を {MIN_WHY} 字以上で書く")
        for j, row in enumerate(_rows(it, "tests")):
            tid = _id_of(row)
            bad = _path_problem(repo, tid) if tid else None
            if bad:
                out.append(f"plan[{i}].tests[{j}].id（{tid}）: {bad}")
                continue
            line = exists(tid) if tid else None
            if tid:
                new_ids.setdefault(tid, f"plan[{i}].tests[{j}]")
                first, kind = kinds.setdefault(tid, (f"plan[{i}].tests[{j}]", row.get("red_kind")))
                if kind != row.get("red_kind"):
                    out.append(f"plan[{i}].tests[{j}].id（{tid}）: 同じ id を {first} にも別の red_kind（{kind}）で書いた"
                               "（同じテストの赤の種類は 1 つにそろえよ）")
            if line is not None:
                out.append(f"plan[{i}].tests[{j}].id（{tid}）: 既に在るテスト（{posixpath.normpath(_parse_id(tid)[0])}:{line}）。"
                           "tests はまだ無いテストを名指す。"
                           "既に在るテストの期待を変えるなら rewrite_tests に書け")
        for j, g in enumerate(_rows(it, "allowed_paths")):
            bad = globs.glob_problem(g) if isinstance(g, str) and g else None
            if bad:
                out.append(f"plan[{i}].allowed_paths[{j}]（{g}）: {bad}")
        for j, row in enumerate(_rows(it, "out_of_scope")):
            g = row.get("glob") if isinstance(row, dict) else None
            bad = globs.glob_problem(g) if isinstance(g, str) and g else None
            if bad:
                out.append(f"plan[{i}].out_of_scope[{j}].glob（{g}）: {bad}")
        out += _files_gaps(i, it, roots)
        rf = it.get("refactor")
        if isinstance(rf, dict) and rf.get("declared") is True:
            rwhy = rf.get("why")
            if not (isinstance(rwhy, str) and len(rwhy.strip()) >= MIN_WHY):
                out.append(f"plan[{i}].refactor.why: declared が true なら、整えの理由を {MIN_WHY} 字以上で書く")
    out += _scope_overlaps(plan)
    out += _added_test_gaps(plan)
    for i, it in enumerate(plan):
        for j, row in enumerate(_rows(it, "rewrite_tests") if isinstance(it, dict) else []):
            tid = _id_of(row)
            if tid is None:
                continue
            if "\\" in tid:
                out.append(f"plan[{i}].rewrite_tests[{j}].id（{tid}）: {_path_problem(repo, tid)}")
                continue
            if find_test(repo, tid) is None:
                out.append(f"plan[{i}].rewrite_tests[{j}].id（{tid}）: 作業ツリーの根の中に在るテストの定義として引けない"
                           "（<パス>::<クラス>::<名前> か <パス>::<名前>。パスは根からの相対）")
            if tid in new_ids:
                out.append(f"plan[{i}].rewrite_tests[{j}].id（{tid}）: 同じ id を {new_ids[tid]} にも書いた"
                           "（新しく足すテストか書き換える既存のテストのどちらか 1 つにせよ）")
    return out


# ---------------------------------------------------------------- 項目の間の依存（depends_on）
def renumber(item: dict, name_of: Callable) -> dict:
    """項目 item（その場で書き換える）の単位を持つ欄（UNIT_REFS: unit_keys と depends_on[].unit）の単位の no を name_of(no) の単位の名に
    戻し、item を返す。字は name_of にそのまま通す（planblk.unit_name は字をそのまま返す。案の直しの返答は unit_keys を字で写すので、
    depends_on[].unit も字で書く）。形の崩れた欄（並びでない・object でない行）は触らない"""
    for field, sub in UNIT_REFS:
        rows = item.get(field)
        if not isinstance(rows, list):
            continue
        for n, row in enumerate(rows):
            if sub is None:
                rows[n] = name_of(row)
            elif isinstance(row, dict) and sub in row:
                row[sub] = name_of(row[sub])
    return item


def _unit_owner(items: list) -> dict:
    """{単位の字: それを unit_keys に持つ最初の項目の位置}（字でない key は入れない）"""
    owner = {}
    for n, it in enumerate(items):
        for k in it.get("unit_keys") if isinstance(it, dict) and isinstance(it.get("unit_keys"), list) else []:
            if isinstance(k, str):
                owner.setdefault(k, n)
    return owner


def _provided(item: dict) -> set[str]:
    """項目 item の files から後の項目が受けてよい物の字: 行の path と、symbol の <パス>::<名前>"""
    return {r["path"] for r in file_rows(item) if isinstance(r.get("path"), str)} | {f"{p}::{n}" for p, n in file_symbols(item)}


def depends_gaps(items) -> list[str]:
    """案の全体 items（unit_keys を単位の字に戻した項目の並び）の depends_on の誤りの行（"plan[<i>].depends_on[<j>]…: <理由>"）。
    拒むのは、自分の項目の単位を指す行・案のどの項目の unit_keys にも無い単位を指す行・受ける物が指した項目の files（行の path か
    symbol の <パス>::<名前>）に無い行・依存の循環（graphlib.TopologicalSorter の CycleError）。案の全体を受ける 1 つの口で、gaps には
    入れない（案の直しの gaps は直した項目だけを受け、直さない項目を指す行を誤って拒むので）。呼ぶのは take_plan（splice した
    案の全体）と案の直しの _plan_errors（直した項目を差し替えた案の全体）。形の崩れた項目・行は飛ばす（型は gaps が見る）"""
    if not isinstance(items, list):
        return []
    owner = _unit_owner(items)
    out, graph = [], {}
    for i, it in enumerate(items):
        for j, row in enumerate(_rows(it, DEPENDS_KEY) if isinstance(it, dict) else []):
            if not isinstance(row, dict):
                continue
            at, unit = f"plan[{i}].{DEPENDS_KEY}[{j}]", row.get("unit")
            src = owner.get(unit) if isinstance(unit, str) else None
            if src is None:
                out.append(f"{at}.unit（{unit}）: 案のどの項目の unit_keys にも無い単位（前の項目の unit_keys の字を書け）")
                continue
            if src == i:
                out.append(f"{at}.unit（{unit}）: 自分の項目の単位（前の項目の単位を書け。同じ項目の中は依存でなく同じ直し）")
                continue
            have = _provided(items[src])
            receives = row.get("receives") if isinstance(row.get("receives"), list) else []
            out += [f"{at}.receives[{k}]（{r}）: 項目 {src + 1}（plan[{src}]）の files に無い（行の path か <パス>::<名前> で書け。"
                    f"在るのは {sorted(have)[:5]}）" for k, r in enumerate(receives) if isinstance(r, str) and r not in have]
            graph.setdefault(i, set()).add(src)
    try:
        graphlib.TopologicalSorter(graph).prepare()
    except graphlib.CycleError as e:
        ring = e.args[1] if len(e.args) > 1 else []
        out.append(f"plan.{DEPENDS_KEY}: 依存が循環している（{' → '.join(f'plan[{n}]' for n in ring)}）。循環する項目は前後を決められない"
                   "（まとめるか、依存の向きを 1 つにせよ）")
    return out


def home_gaps(items) -> list[str]:
    """案の全体 items の files の行の home.concept（前後の空白を落として casefold）が、案の全部の行で 2 度出たら、2 度目の行の
    home.concept を名指し、1 度目の行も文に載せて拒む（同じ考えの住処を 2 行に置かない）。2 度目の行の path が 1 度目の行の considered に
    在るか、1 度目の行の path が 2 度目の行の considered に在れば、退けた所に同じ考えを住まわせる矛盾の行も足す。行は
    "plan[<i>].files[<j>].home.concept…: <理由>"。案の全体を受ける 1 つの口で、gaps には入れない（案の直しの gaps は直した項目だけを
    受け、直さない項目の行と重なる考えを見逃すので）。呼ぶのは take_plan と案の直しの _plan_errors（depends_gaps と同じ案の全体を渡す）。
    op=delete の行は数えない（消えるファイルは変更の後に考えの住処になれず、移す前の考えの名を書くのが自然なので）。
    純な関数（案の JSON だけを読む）。形の崩れた項目・行は飛ばす（型は gaps が見る）"""
    out, first = [], {}
    for i, it in enumerate(items if isinstance(items, list) else []):
        for j, row in enumerate(_rows(it, "files") if isinstance(it, dict) else []):
            if not isinstance(row, dict) or row.get("op") == "delete":
                continue
            home = row.get("home")
            concept = home.get("concept") if isinstance(home, dict) else None
            if not (isinstance(concept, str) and concept.strip()):
                continue
            at, key = f"plan[{i}].files[{j}]", concept.strip().casefold()
            if key not in first:
                first[key] = (at, row)
                continue
            was_at, was = first[key]
            here = f"{at}.home.concept（{concept.strip()}）"
            out.append(f"{here}: {was_at} の home.concept にも同じ考えの住処を置いた（考えの住処は 1 か所。同じ考えを 2 行に置かず、"
                       "1 行にまとめるか、考えの名を分けよ）")
            if row.get("path") in _considered_paths(was) or was.get("path") in _considered_paths(row):
                out.append(f"{here}: 矛盾（退けた所に同じ考えを住まわせる）。{was_at} と {at} の一方の considered に、もう一方の行の path が"
                           "在る（退けた置き場を住処にしない。住処を 1 つに決め、退けた方の行から考えを外せ）")
    return out


def _considered_paths(row: dict) -> set[str]:
    """行 row の considered の path の集合（字の物だけ）"""
    return {c["path"] for c in row.get("considered") if isinstance(c, dict) and isinstance(c.get("path"), str)} \
        if isinstance(row.get("considered"), list) else set()


def depends_pairs(items, among=None) -> list[tuple[str, str]]:
    """承認済みの項目の並び items（planmarks.approved_items の形。unit_keys は単位の字）の依存を、単位の対 (前の単位, 後の単位) の並びで
    引く（後の項目の depends_on が指す前の項目の単位の全部 × 後の項目の単位の全部。現れた順・重なりは 1 つ）。among（組に渡す
    単位の並び）を渡せば、among の外の単位を通る依存を among の中の端どうしの対に縮める（A→B→C で B が外なら (A, C)）。
    指す単位が案に無い行・自分の項目への行は数えない（depends_gaps が受け付けで拒む）"""
    items = [it for it in items or [] if isinstance(it, dict)]
    owner = _unit_owner(items)
    units = [[k for k in it.get("unit_keys") or [] if isinstance(k, str)] for it in items]
    edges: dict = {}
    for i, it in enumerate(items):
        for row in _rows(it, DEPENDS_KEY):
            src = owner.get(row.get("unit")) if isinstance(row, dict) and isinstance(row.get("unit"), str) else None
            if src is None or src == i:
                continue
            for a in units[src]:
                for b in units[i]:
                    if b not in units[src]:   # 両方の項目が持つ単位は前の項目の側で直る（向きの逆の対で循環させない）
                        edges.setdefault(a, {})[b] = None
    if among is None:
        return [(a, b) for a, nexts in edges.items() for b in nexts]
    inside, pairs = set(among), {}
    for a in [k for k in edges if k in inside]:
        seen, queue = {a}, list(edges[a])
        while queue:
            x = queue.pop(0)
            if x in seen:
                continue
            seen.add(x)
            if x in inside:
                pairs[(a, x)] = None   # 外の単位を通ってきた依存は、中の端どうしの対に縮める（中の単位から先は、その単位の対が引く）
            else:
                queue += list(edges.get(x, ()))
    return list(pairs)


def _declared(files) -> list[str]:
    """項目の files の宣言した名前の並び: 行の順に、op=create の .py の行の path（新しいモジュールの import の失敗を TDD の輪が宣言の赤に
    数える。依頼 194c の nodeio.py）と、その行の change=add の symbol の名（重なりは 1 つ）。home・considered の字は読まない"""
    out = []
    for row in file_rows({"files": files}):
        path = row.get("path")
        if row.get("op") == "create" and isinstance(path, str) and path.endswith(".py"):
            out.append(path)
        out += [s["name"] for s in symbol_rows(row) if s.get("change") == "add" and isinstance(s.get("name"), str)]
    return list(dict.fromkeys(out))


def split(reply: dict, repo: pathlib.Path, *, base_tests: dict | None = None) -> tuple[dict, list[dict]]:
    """（works の欄を外した返答の写し, 項目と同じ並びの欄）。欄の行は外した欄に、項目の unit_keys の写しと、項目の files の写し
    （宣言した名前 _declared と消す名は、読み手が files から引く。unit_contract・ripple）と、rewrite_tests の各行の書き換えてよい範囲
    limit（"<パス>:<定義の行>"。引けない行には付けない）を足した物。gaps を通った返答に使う。
    base_tests（パス → 修正前の版のテストのファイルの中身）を渡せば、項目の files の change=remove の symbol（消す名）をコードの
    識別子として使うテストの行 removes_tests [{id, limit}] も足す（書き換え・消しを許すだけの行で、義務でない。作業ツリーでは消えた
    テストも修正前の版で探す）。repo は rewrite_tests の範囲 limit を引く作業ツリー"""
    out, rows = jsonfile.split(reply, STEPS, KEYS)
    items = out.get("plan") if isinstance(out, dict) else None
    for it, got in zip(items if isinstance(items, list) else [], rows):
        if not isinstance(it, dict):   # 形の崩れた項目の欄は空のまま
            continue
        got["unit_keys"] = copy.deepcopy(it.get("unit_keys") or [])
        got["files"] = copy.deepcopy(it.get("files") or [])
        for row in got.get("rewrite_tests") or []:
            lim = _limit(repo, _id_of(row)) if _id_of(row) else None
            if lim:
                row["limit"] = lim
        if base_tests is not None:
            got[MACHINE_KEY] = _naming_removes(it, base_tests)
    return out, rows


class Need(NamedTuple):
    """答えの要る行の表 1 つ（structure_gaps が受ける）。key＝欄 structure の行で答える先の id を持つ鍵（ANSWER_KEYS の 1 つ）・
    word＝誤りの文で行を呼ぶ名・hints＝{名指せる id: 誤りの文に添える推しの 1 文}・hint_word＝その 1 文の名・
    unknown＝名指せない id を名指した時の文・of(項目)＝その項目が答える要る id の並び・missing(案)＝どの項目も答えていない id の並び"""
    key: str
    word: str
    hints: dict
    hint_word: str
    unknown: str
    of: Callable
    missing: Callable


def design_need(dirty: dict) -> Need:
    """構造の目が汚れると見た単位（dirty: 単位の id → 設計の行）の表。項目の unit_keys に汚れる単位が在れば、その行の 1 件（row）が要る"""
    def of(it):
        keys = it.get("unit_keys") if isinstance(it.get("unit_keys"), list) else []
        return [k for k in keys if isinstance(k, str) and k in dirty]
    return Need("row", "設計の行", {k: (r or {}).get("chosen") or "無し" for k, r in dirty.items()}, "避け方",
                "構造の目が汚れると見た行の単位でない", of, lambda plan: [])


def _structure_row_problem(row) -> str | None:
    """structure の 1 行の誤りの文（無ければ None）: ANSWER_KEYS のちょうど 1 つ・follows: true と deviation のちょうど 1 つ"""
    if not isinstance(row, dict):
        return "行が object でない"
    if sum(k in row for k in ANSWER_KEYS) != 1:
        return "row（構造の目の行）か prescription（判定の処方）か world（世界の解の類）のどれか 1 つを書く"
    has_follow, has_dev = "follows" in row, "deviation" in row
    if has_follow == has_dev:
        return "follows: true（従う）か deviation（外れの訳）のどちらか 1 つを書く"
    if has_follow and row["follows"] is not True:
        return "follows は true だけ（従わないなら deviation に訳を書く）"
    dev = row.get("deviation")
    if has_dev and not (isinstance(dev, str) and len(dev.strip()) >= MIN_DEVIATION):
        return f"deviation（外れの訳）は {MIN_DEVIATION} 字以上"
    return None


def structure_gaps(plan, tables) -> list[str]:
    """構造の欄の欠けと誤りの行（"plan[<i>].structure…: <理由>"）。tables は答えの要る行の表（Need）の並び。表ごとに、項目に要る
    id（Need.of）の 1 件が要り、表の鍵の行は表の id だけを名指し、どの項目も答えていない id（Need.missing）が在れば拒む。
    plan は名前に戻した unit_keys の案（返答の no の整数は呼び手が戻す）。形を成さない plan は空（写しの規則が型で拒む）"""
    if not isinstance(plan, list):
        return []
    tables = list(tables or [])
    out, owed = [], set()   # owed: 項目ごとに欠けを名指した (鍵, id)。案の全体の欠けで重ねて名指さない
    for i, it in enumerate(plan):
        if not isinstance(it, dict):
            continue
        rows = it.get("structure") if isinstance(it.get("structure"), list) else []
        named = {t.key: set() for t in tables}
        for j, row in enumerate(rows):
            bad = _structure_row_problem(row)
            if bad:
                out.append(f"plan[{i}].structure[{j}]: {bad}")
                continue
            for t in tables:
                if t.key in row:
                    if row[t.key] not in t.hints:
                        out.append(f"plan[{i}].structure[{j}].{t.key}（{row[t.key]}）: {t.unknown}（在るのは {sorted(t.hints)}）")
                    named[t.key].add(row[t.key])
        for t in tables:
            for k in t.of(it):
                if k not in named[t.key]:
                    owed.add((t.key, k))
                    out.append(f"plan[{i}].structure: {t.word} {k} に従うか、外れの訳を structure に書け（{t.hint_word}: {t.hints[k]}）")
    good = [it for it in plan if isinstance(it, dict)]
    for t in tables:
        for k in t.missing(good):
            if (t.key, k) in owed:
                continue
            out.append(f"plan.structure: {t.word} {k} にどの項目も答えていない（答えの要る行ごとに、どれかの項目が {{{t.key}: {k}, "
                       f"follows: true}} か {{{t.key}, deviation}} を書け。{t.hint_word}: {t.hints.get(k, '無し')}）")
    return out


JUDGE_NODE = "p2.diagnose"   # 判定の節（単位の処方を持つ返答。写しの graph の writes は units に処方を写さない）


def prescriptions(b) -> dict:
    """{単位の key: [処方の文]}（判定の返答の最新の出力から。空の処方の単位は入れない。出力が無い・形が違えば {}）"""
    out = b.latest_output(JUDGE_NODE)
    units = out.get("units") if isinstance(out, dict) else None
    got = {}
    for u in units if isinstance(units, list) else []:
        if isinstance(u, dict) and isinstance(u.get("key"), str):
            rx = [x for x in u.get("prescriptions") or [] if isinstance(x, str) and x.strip()]
            if rx:
                got[u["key"]] = rx
    return got


def answer_line(r: dict) -> str:
    """欄 structure の 1 行（か deviations の 1 行）の文: 「（項目 n・）設計の行 <id> に従う」か「…から外れる——<訳>」。
    事前審査の頭・報告・最後の関所・修正役の brief が同じ文を引く"""
    if not isinstance(r, dict):
        return str(r)
    head = f"項目 {r['item']}・" if "item" in r else ""
    what = (f"設計の行 {r['row']}" if r.get("row") else f"世界の解の行 {r['world']}" if r.get("world")
            else f"処方 {r.get('prescription')}")
    if r.get("follows") is True:
        return f"{head}{what}に従う（避け方・処方どおりに直す）"
    return f"{head}{what}から外れる——{r.get('deviation')}"


def deviations(fields: list | None) -> list[dict]:
    """控えの欄（split の形）の外れの訳の並び [{item（1 始まり）, row か prescription か world, deviation}]。無ければ空"""
    out = []
    for n, f in enumerate(fields if isinstance(fields, list) else [], 1):
        for row in (f.get("structure") if isinstance(f, dict) and isinstance(f.get("structure"), list) else []):
            if isinstance(row, dict) and isinstance(row.get("deviation"), str):
                key = next((k for k in ANSWER_KEYS if k in row), "prescription")
                out.append({"item": n, key: row.get(key), "deviation": row["deviation"]})
    return out


# ---------------------------------------------------------------- 盤面の控え
class FieldsBroken(ValueError):
    """盤面の控え plan-fields.json が今の周の凍結の印（SAVED_OP）と合わない（受け付けの後に書き換えた・消した・読めない）"""


def save(board, rnd: int, fields: list, amended: dict | None = None, *, trace=None) -> None:
    """盤面の plan-fields.json を今の周の欄で置き換え（一時のファイルから os.replace。リンクの先へ書かない）、盤面の trace に
    凍結の印 SAVED_OP {round, sha256（置いたバイトの sha256）} を 1 行足す。trace は開いた盤面の書き口（DiskBoard.trace。行に
    部品の scope が載る）で、渡さなければ同じ行の形 {t, op, …} で trace.jsonl に直に足す（append_trace）。
    amended（{番号: 核の欄}）が在れば鍵 AMENDED_KEY に番号を字にして置く（無ければ鍵を書かない）"""
    d = pathlib.Path(board)
    doc = {"round": rnd, "fields": fields}
    if amended is not None:
        doc[AMENDED_KEY] = {str(n): core for n, core in amended.items()}
    raw = jsonfile.dump(_path(d), doc)
    row = {"round": rnd, "sha256": hashlib.sha256(raw).hexdigest()}
    if trace is not None:
        trace(SAVED_OP, **row)
        return
    append_trace(d, SAVED_OP, **row)


def append_trace(folder, op: str, **row) -> None:
    """folder の trace.jsonl（TRACE_FILE）に行 {t, op, …} を 1 行足す（開いた盤面の書き口が無い時の trace の行の形の持ち主）"""
    with open(pathlib.Path(folder) / TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now(), "op": op, **row}, ensure_ascii=False) + "\n")


def _path(b) -> pathlib.Path:
    """盤面の根の控えのパス（b は盤面か、その置き場のパス）"""
    return pathlib.Path(getattr(b, "dir", b)) / FIELDS_FILE


def _doc(b) -> dict | None:
    """今の周（b.round）の控えの全体。控えが無い・周が違う・読めない・fields が並びでないなら None"""
    doc = jsonfile.read_or(_path(b))
    if not isinstance(doc, dict) or doc.get("round") != b.round or not isinstance(doc.get("fields"), list):
        return None
    return doc


def read(b) -> list | None:
    """今の周（b.round）の欄の並び。控えが無い・周が違う・読めないなら None（b.dir・b.round だけを読む）"""
    doc = _doc(b)
    return doc["fields"] if doc else None


def _saved_mark(b) -> dict | None:
    """今の周（b.round）の凍結の印（trace の SAVED_OP の行の最後の物）。無ければ None"""
    try:
        lines = (pathlib.Path(b.dir) / TRACE_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    mark = None
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("op") == SAVED_OP and row.get("round") == b.round:
            mark = row
    return mark


def handed(ruling, items: int) -> tuple:
    """(案の直しで渡す項目の番号の並び, 渡せない訳)。ruling は項目の番号の字の並び（fix の replan_items）"""
    out = []
    for r in ruling if isinstance(ruling, list) else []:
        n = int(r) if isinstance(r, str) and re.fullmatch(r"[0-9]+", r.strip()) else r if isinstance(r, int) and not isinstance(r, bool) else None
        if n is None or not 1 <= n <= items:
            return [], f"ruling の項目 {r!r} が承認済みの修正案（{items} 項目）の番号でない"
        if n not in out:
            out.append(n)
    return out, "" if out else "ruling に直す項目が無い"


def approved_items(b) -> list[dict] | None:
    """今の周の承認済みの修正案の項目（plan_items。差し替えた項目は直した核の欄）と凍結した欄（frozen）を同じ番号で合わせた並び
    {"item": <1 始まり>, **案の項目, **欄の KEYS の物}（unit_keys は案の物）。どちらか無ければ None。数が違えば FieldsBroken
    （frozen の食い違いもそのまま FieldsBroken。b は dir・round・output_of_round を読む）"""
    fields = frozen(b)
    plan = plan_items(b)
    if fields is None or plan is None:
        return None
    return [{"item": n, **copy.deepcopy(joined(it, f))} for n, (it, f) in enumerate(paired(plan, fields, f"共有ボードの控え {FIELDS_FILE}"), 1)]


def paired(plan: list, fields: list, where: str) -> list[tuple[dict, dict]]:
    """案の項目の行の並び plan と欄の行の並び fields（where に在る物）を同じ番号で組んだ (項目, 欄) の並び（dict でない行は空の dict）。
    数が違えば FieldsBroken（同じ周の受け付けが同じ並びで書くので、組めば番号がずれる）。承認済みの項目（approved_items）・
    事前審査の往復の控えの行（boardview.open_pass）・項目ごとの brief（planbrief）が同じ物を呼ぶ"""
    if len(fields) != len(plan):
        raise FieldsBroken(f"修正案の項目の数 {len(plan)} と {where} の欄の数 {len(fields)} が違う（同じ周の受け付けが同じ並びで書く物）")
    return [(it if isinstance(it, dict) else {}, f if isinstance(f, dict) else {}) for it, f in zip(plan, fields)]


def joined(it: dict, f: dict) -> dict:
    """案の項目の行 it に同じ番号の欄の行 f（plan-fields.json の行）の KEYS の物を重ねた行（unit_keys は案の物）。
    承認済みの項目（approved_items）と事前審査の往復の控えの行（boardview.open_pass）が同じ物を呼ぶ"""
    return {**it, **{k: f[k] for k in KEYS if k in f}}


def scoped(items: list | None) -> bool:
    """承認済みの項目の並び items が範囲の欄を持つか（並びが在り、どの項目にも allowed_paths が在る）。偽なら範囲の無い run
    （修正案の無い run・217 番の形の控え）として扱う"""
    return items is not None and all(isinstance(it, dict) and "allowed_paths" in it for it in items)


def frozen(b) -> list | None:
    """今の周の凍結した欄の並び（read と同じ物）。今の周の印が無ければ None（印の無い控えは無い物: 変更前の盤面・save の外で
    置いた控え）。印が在るのに控えが読めない・控えのバイトの sha256 が印と違えば FieldsBroken"""
    doc = _frozen_doc(b)
    return doc["fields"] if doc else None


def _frozen_doc(b) -> dict | None:
    """今の周の凍結した控えの全体（frozen の決まりで読む: 印が無ければ None・食い違えば FieldsBroken）"""
    mark = _saved_mark(b)
    if mark is None:
        return None
    p = _path(b)
    try:
        raw = p.read_bytes()
    except OSError as e:
        raise FieldsBroken(f"共有ボードの控え {p}（{FIELDS_FILE}）が読めない。周 {b.round} の {SAVED_OP} の印が在る: {e}") from None
    if hashlib.sha256(raw).hexdigest() != mark.get("sha256"):
        raise FieldsBroken(f"共有ボードの控え {p}（{FIELDS_FILE}）のバイトの sha256 が周 {b.round} の {SAVED_OP} の印と違う"
                           "（受け付けの後に書き換えた）")
    return _doc(b)


def amended(b) -> dict[int, dict]:
    """今の周の凍結した控えの差し替えた項目の核の欄 {番号（int）: {CORE_KEYS の欄}}。控えか鍵 AMENDED_KEY が無ければ {}。
    印と食い違えば・形が違えば FieldsBroken"""
    doc = _frozen_doc(b)
    got = doc.get(AMENDED_KEY) if doc else None
    if got is None:
        return {}
    try:
        out = {int(n): core for n, core in got.items()}
    except (AttributeError, TypeError, ValueError):
        out = None
    if out is None or not all(isinstance(c, dict) for c in out.values()):
        raise FieldsBroken(f"共有ボードの控え {FIELDS_FILE} の {AMENDED_KEY} の形が違う（{{番号: 核の欄}} でない）")
    return out


def plan_items(b) -> list | None:
    """今の周の修正案の項目の並び: p2.fix_plan の出力の plan に、amended(b) の核の欄を番号ごとに重ねた物（差し替えの後の案）。
    出力の plan が無ければ None。控えの番号が案の外なら FieldsBroken（b は dir・round・output_of_round を読む）"""
    doc = b.output_of_round(NODE, b.round)
    plan = doc.get("plan") if isinstance(doc, dict) else None
    if not isinstance(plan, list):
        return None
    out = copy.deepcopy(plan)
    for n, core in amended(b).items():
        if not 1 <= n <= len(out):
            raise FieldsBroken(f"共有ボードの控え {FIELDS_FILE} の {AMENDED_KEY} の項目 {n} が修正案の項目（{len(out)} 個）の外")
        base = out[n - 1] if isinstance(out[n - 1], dict) else {}
        out[n - 1] = {**base, **copy.deepcopy(core)}
    return out


def rewrites(b) -> list[dict]:
    """今の周の承認済みの修正案が名指した、書き換えてよい既存のテストの並び
    {item: 項目の番号（1 始まり）, unit_keys, id, new, limit}。範囲 limit の無い行は並べない（許しを広げない）。
    控えは frozen で読む（印と食い違えば FieldsBroken）"""
    out = []
    for n, f in enumerate(frozen(b) or [], 1):
        if not isinstance(f, dict):
            continue
        for row in f.get("rewrite_tests") or []:
            if isinstance(row, dict) and isinstance(row.get("limit"), str) and row["limit"]:
                out.append({"item": n, "unit_keys": list(f.get("unit_keys") or []), "id": row.get("id"),
                            "new": row.get("new"), "limit": row["limit"]})
    return out


def removes_permits(b) -> list[dict]:
    """今の周の承認済みの修正案の項目の files の change=remove の symbol（消す名）をコードで使う既存のテストの並び {item, id, limit}（split が凍結した欄の
    removes_tests。書き換え・消しを許すだけの行で、義務ではない）。rewrites と同じく frozen で読み（印と食い違えば FieldsBroken）、
    範囲 limit の無い行は並べない（許しを広げない）"""
    out = []
    for n, f in enumerate(frozen(b) or [], 1):
        if not isinstance(f, dict):
            continue
        for row in f.get(MACHINE_KEY) or []:
            if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("limit"), str) and row["limit"]:
                out.append({"item": n, "id": row["id"], "limit": row["limit"]})
    return out


def unit_contract(fields: list | None, key: str) -> dict | None:
    """単位 key の約束 {items: 項目の番号（1 始まり）, route, tests: [{id, red_kind}], rewrites: [id], refactor: [{item, why}], names: [宣言した名前（欄の files から _declared）]}。
    key を unit_keys に含む項目の欄を合わせる: route はどれかの項目が tdd なら tdd（ほかは direct）・tests は項目の順で id の重複を
    除く（同じ id に別の red_kind は gaps が拒む）・rewrites は範囲 limit の在る行の id だけ（rewrites と同じ選び方）・refactor は
    refactor.declared が真の項目の番号と理由（申告が無ければ空）・names は項目の欄の files の宣言した名前（_declared: change=add の symbol の名と op=create の .py の path）を項目の順で重複を除いた列。
    fields が None か、当たる項目が無ければ None。純粋（盤面もファイルも読まない）"""
    if not isinstance(fields, list):
        return None
    items, tests, rws, names = [], {}, {}, {}
    route, refactor = "direct", []
    for n, f in enumerate(fields, 1):
        keys = f.get("unit_keys") if isinstance(f, dict) else None
        if not isinstance(keys, list) or key not in keys:
            continue
        items.append(n)
        route = "tdd" if f.get("route") == "tdd" else route
        for row in _rows(f, "tests"):
            if _id_of(row):
                tests.setdefault(row["id"], row.get("red_kind"))
        for row in _rows(f, "rewrite_tests"):
            if _id_of(row) and isinstance(row.get("limit"), str) and row["limit"]:
                rws.setdefault(row["id"])
        for nm in _declared(f.get("files")):
            names.setdefault(nm)
        rf = f.get("refactor")
        if isinstance(rf, dict) and rf.get("declared") is True:
            refactor.append({"item": n, "why": rf.get("why").strip() if isinstance(rf.get("why"), str) else ""})
    if not items:
        return None
    return {"items": items, "route": route, "tests": [{"id": i, "red_kind": k} for i, k in tests.items()],
            "rewrites": list(rws), "refactor": refactor, "names": list(names)}


# 境は ASCII の識別子の字だけで見る（\w は仮名・漢字も語の字に数え、「項目1のremoves_testsが」を見逃す）
_MACHINE_KEY_IN = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(MACHINE_KEY)}(?![A-Za-z0-9_])")


def machine_face_gaps(faces: list) -> list[str]:
    """事前審査の穴 faces のうち、where が機械の足した欄（MACHINE_KEY）を名指す block の誤りの行（受け付けが拒む。修正案の役が
    直せない穴で案の往復を回さない）。suggest は往復を回さないので拒まない"""
    return [f"faces[{j}]（{str(f.get('key'))[:40]}）: where が機械の足した欄 {MACHINE_KEY} を名指す block（修正案の役は直せない。"
            f"許しが広すぎるなら files の change=remove の symbol を名指せ。そうでなければ suggest にせよ）"
            for j, f in enumerate(faces)
            if f.get("severity") == "block" and _MACHINE_KEY_IN.search(str(f.get("where") or ""))]

