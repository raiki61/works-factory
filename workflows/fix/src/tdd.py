"""修正のブロックの単位ごとの TDD の輪（MVP。設計 2 節 3・案 (i)。graph は変えず、ブロックの中で回す）。

節と関数:
- tdd-start → start: 入力 tdd_suite（JUnit XML の書き先を第 1 引数に受け、リポジトリの根で走る実行ファイル。本線と同じ約束）が
  空なら何もせず go: false（static でない単位の在る組は組の頭が no-suite で止める。docs/plans/2026-10-24-fix-weapons.md の 3.9）。在れば一式を 1 回走らせて元の結末を取り、置き場の tdd-<k>/ に状態を置く。
  承認済みの修正案の単位ごとの約束（plan_contract → planmarks.unit_contract。道・受け入れのテストと、案が狙う落ち方 red_kind。後者は役に見せるだけで機械は照らさない）もここで 1 回だけ
  組んで状態の contract に置く（欄の控えの無い置き場・平の run は空で、輪は約束の無い今の動きのまま）。
  run のテストのコマンド（線の入力 test_cmd）の関門（test_cmd_gate）もここで 1 回だけ決める: 空なら off、実行器のファイルが
  そのコマンドの文字列をそのまま含むなら same_as_suite（一式と同じなので 2 度走らせない）、ほかは 1 回走らせて緑なら on、
  赤・走らないなら off にして理由を test_cmd_note に残す（元から赤の test_cmd で毎単位を拒まない）。test_cmd は baseline_red.run_suite と
  同じ起こし方（tree_run.reuse_run・優先度は baseline_red.lowered）で走らせ、既存のファイルを書き換えた回はいつも赤（書き換えた物は戻す。_cmd_run）。関門が on なら
  直し・整えの段の指示書にそのコマンドを書く。
- tdd-loop の中: tdd-prep → prep（今の段の指示書を fixrules で組んで書く。頭に brief の節: 振り分けの段は
  直す義務の単位の全部、ほかの段は今の単位の brief。brief の控えの無い置き場・平の run は無し。単位が替わった周かを new_unit で返す）→
  役 tdd（修正役。同じ単位の段は前の周の会話を継ぎ、単位が替わる周だけ新しい会話で起きる。前の単位と今の単位のこれまで（段・
  前の段の結果）は引き継ぎの節（handoff_lines）も状態から書く。振り分け・テスト・直し・整えを返す）→
  tdd-step → step（返答を機械が確かめて段を進める）。段は route → 単位ごとに test → fix →（申告の在る単位だけ）refactor → 次の単位。
  step 1 回ごとに状態の calls に 1 行（n・確かめた段（申し出は conflict、実行器・test_cmd が走らずに抜けた回は runner）・単位・
  合否・その回に起こした一式と test_cmd の数・秒）を積む（秒は書くだけで止める条件に使わない）
  - route: 直す義務の単位（_owed: 開いた単位から、答え待ち・ask_human で外れた単位と食い違いで止めた単位を除く）を全部 1 度だけ
    tdd か direct（理由 10 字以上）に振る。約束で tdd の単位は direct に振れない（出口は phase conflict の申し出）
  - test: 申告したテストのファイルの外のテストのファイル（impact.is_test_file）に触れていない・赤の判定 red_check（名指しは failure で
    落ち、error・一式に居ない・もう通る・飛ばされたは拒み、元で通っていた物は緑。言語に依らない事実だけ）。テストでないファイル
    （これから足す名前の仮の実装）への書き込みは拒まず、単位の stub_files に残す。error・一式に居ないで拒む時は NOT_RAN の
    1 行を足す（走る前の失敗は赤に数えず、直して走らせ直させる）。
    約束の在る単位は、受け入れのテストの id を全部名指し（走らせる前に見る）、名指しごとの失敗の文の引用と理由（QUOTES_FIELD）を
    結末の failure の文と照らす（red_check。照らす先の無い名指しは引用を求めず、単位の quote_unchecked に残す）。約束の無い単位は
    引用を求めず、書かれていれば照らす。direct_why でも direct に渡せない。
    修正案が書き換えを名指した既存のテスト（約束の rewrites）も名指しに入れ、同じ赤を通す。
    約束の在る単位は、名指しの外の既存のテストの本体（.py の test* 関数。_unnamed_edits）を書き換えたら拒む（走らせる前）。
    単位の頭で通っていたテストが飛ばされた・結末から消えたら拒む（_vanished_problems。単位の頭から変わったテストの
    ファイルのモジュールだけ。居ないは同じ選びの回に居た時だけ数える）。前の単位で赤→緑を確かめた id は名指しを
    強いず、書き換えさせない（_verified）
    赤が通ったら、役の引用と理由を単位の red_quotes に、赤の時の木（snapshot）を red_tree に残す（red_tree は出口に出さない。
    事後の関門が、仮の実装を含む赤をその木で確かめ直す）
  - 同じ修正案の項目の単位（together）: 受け入れのテストは項目の物で、項目の単位の全部の約束に載る。前の単位の段はそれを全部名指して
    緑にするので、項目を共にする後の単位（載る項目が全部前の単位の項目にも在る物）の直しも要る。支度はその単位を「今は直すな」・
    「この後の単位（今は手を付けるな）」に並べず、「今の単位と一緒に直す単位」の節に並べ、brief の行の単位にも入れる。前の単位が
    緑に届けば、後の単位は段を回さずに機械が閉じる（_close_covered: 受け入れのテストが全部確かめ済みの時だけ。赤・緑とも ok、
    covered_by に一緒に直した単位）。別の項目の単位・前の単位に無い項目にも載る単位は今どおり単位ごとに赤→緑を回す
  - fix: その単位のテストのファイルが赤の時から変わっていない・写しの green_problems。約束の在る単位は、ほかのテストのファイル
    （impact.is_test_file: 宣言か名の慣習）の既存の test* 関数の本体（.py でないファイルは行を消した・置き換えた差分）も変えていない（_other_test_edits）・テストを飛ばした・消していない
    （_vanished_problems）。関門が on なら、そのうえで run の test_cmd も緑（_test_cmd_problems。赤は拒み、走らない時は実行器が
    走らない時と同じに輪を抜ける）。refactor の緑の確かめも同じ。
    緑の後、返答の任意の欄 refactor（{declared, why}）で役が理由（10 字以上）つきで申告した単位か、約束の refactor が真（修正案の
    項目の refactor.declared）の単位だけ refactor の段へ進み、理由を単位の refactor_why に残す。declared が true で理由が短ければ
    拒む（一式を走らせる前）。申告が無ければ単位の refactor を skipped にして次の単位へ（緑の木が次の単位の頭）
  - refactor: 緑の時から何も変えていなければ none。変えたなら fix と同じ確かめをもう 1 回
  - test・fix・refactor とも、名指しを絶対パスの node id で実行器の後ろに足し、合図 TDD_SUITE_ONLY=1（ONLY_ENV）を付けて走らせる
    （一式を回さない。解かない実行器は今どおり一式に足して走らせる）。赤の回は名指しだけ。緑の回（fix・変えた refactor）は名指しに、
    単位の頭からの変更に直に関わる試験（impact.select_tests の direct_only: 変えた試験・変えた file を直に読む・言及する試験）の
    うち元の結末に載ったモジュールの pytest のファイルを絶対パスで足す
    （_reached。元で通っていたテストの緑と消えたテストの照らしは、この回でファイルごと走ったモジュールで見る）。地図が引けない・
    分からない物が近くに在る（run_all）時は合図なしの一式。届かない試験・元の結末の外の試験は受け付け（selected_problems）と
    線の最後のテストの段（一式）が確かめる
  拒めば同じ段のまま、理由は次の指示書（と reason_file）に載る。段ごとに RETRY_MAX 回目の拒否で諦める: test・fix は作業ツリーを
  単位の頭に戻して食い違いの申し出（機械が書いた 1 件。裁定の輪が裁く）で止めて次の単位へ、refactor は緑の時の木に戻す。
  実行器が走らない・回数の上限に届いた時は、残りを全部 direct にして抜ける
  （輪は done の印で抜け、max_iterations に届いて落ちない。R50）。段 test で役が direct_why を返した単位は、修正案の約束が無い run
  （約束が在れば direct_why は拒まれる）に限り、申し出の道を通らずに direct へ渡る
- fix-accept → frozen_problems: 輪で緑になった単位のテストのファイルを、輪の後の修正役が変えていないか（裁定 fix_test_scope の
  範囲の中の変更は、輪が済んだ時の木（frozen_tree）との差分の塊の旧い側の行で見て通す。.py に新しい関数・クラス・メソッドを
  足しただけで、既存の文も既存のテストが読む名・枠の掛け金も変えない物は数えない）
- fix-accept → selected_problems: 版からの変更に直に関わる試験（impact.select_tests の direct_only: 変えた・足した試験・変えた file を
  直に読む・言及する試験（深さ 1）と、修正案の受け入れ・書き換えのテストと輪で名指したテストのファイル。分からない物が近くに
  在れば全部）を同じ実行器で
  走らせ（選んだ .py のうち変えた・足したファイルだけを一式を回す時も絶対パスで後ろに足し、一式でない時は -k で絞る。届いただけの
  段の外の試験は手元で走らせない。ADR 0071 の 3 の 1）、元で赤でなかった試験の赤をテストのファイルごとの行で返す（行はそのパスを
  名指す。ファイルの分からない赤は 1 行にまとめてパスを名指さない）。走らせなかった試験は『手元で回さなかった』として
  知らせと状態（ci_left。受け付けが盤面の trace に載せ、最後の関所が並べる）に名前で残す。届くだけで直に関わらない試験は
  受け付けで回さず、『最後のテストの段に任せた』として知らせと状態（final_left。同じ trace の行・最後の関所）に名前で残す
  （一式は線の最後のテストの段で 1 回。そこでの赤は最後の関所と報告・次の依頼の下書きに載る）。分からない物が直に関わる所
  （起点か深さ 1）に在る時だけ一式を回し、深さ 2 以上の分からない物は final_far に残して最後のテストの段に任せる（輪の緑も同じ）。元の結末に無い試験の赤は、版を
  一時の置き場に写して同じ試験を回し、版でも赤なら外す（作業ツリーは動かさない）。1 件も走らなければ「新しい赤なし」にせず
  知らせる（一式の緑は線の最後のテストの段が確かめる。役は一式を回さない）
- collect → exit_fields: 出口の欄 tdd（単位ごとの道・赤・緑・整えとその申告の理由・direct の理由・test_cmd の緑。輪の test_cmd の
  関門と理由・段ごとの呼び出しの記録 calls）
赤の判定は red_check 1 つ（中で lib/baseline_red の red_problems を呼ぶ。rules() がそのモジュールを返す）で、輪と
事後の関門が同じ事実を見る。緑の判定は baseline_red の green_problems を呼ぶ。実行器を走らせる口 run_suite と failure の文の
読み _failure_attrs は baseline_red の物を読む（ここに定義を持たない）。版は一時の index（GIT_INDEX_FILE）で木に固める
（本物の index・HEAD・枝は動かさない。.gitignore に当たる物は載らない）。期限は持たない。
"""
import ast
import json
import pathlib
import posixpath
import sys
import time

sys.dont_write_bytecode = True

from baseline_red import _failure_attrs, exe_path, run_suite  # noqa: E402,F401  （定義はここに持たない。fixgates・fixboard が tddloop の名で読む）
import conflict  # noqa: E402  （lib。食い違いの申し出の確かめ・直す義務から外れた単位）
from src import board as fixboard  # noqa: E402  （lib。直す義務 fix_duty。元 conflict.fix_duty の値で受ける形）
from src import files as fixnames  # noqa: E402
from src import rules as fixrules  # noqa: E402  （同じブロックの lib。指示書の組み立て）
import impact  # noqa: E402  （.shared/core。変更に当たる試験の選び）
import planbrief  # noqa: E402  （同じブロックの lib。承認済みの修正案の項目ごとの brief の凍結）
import planmarks  # noqa: E402  （.shared/core。修正案の項目の works の欄。単位の約束）
from planmarks import test_functions  # noqa: E402,F401  （.shared/core。テストの関数の id（pytest の node id の形）→ 源の引き。fixgates・fixboard が tddloop.test_functions の名で読む）
import rolekit  # noqa: E402  （lib。諦めの回数 GIVE_UP_AFTER）
import writelog  # noqa: E402
import writes  # noqa: E402  （.shared/core。書き込みの出どころの突き合わせ）
import oneline  # noqa: E402
from leftovers import git, git_names  # noqa: E402
# 型を問わない部品（src/common.py。輪の中の名は変えない）
from src import common  # noqa: E402
from src.common import (  # noqa: E402
    Broken, GATE_OFF, GATE_ON, MIN_WHY, QUOTES_FIELD, UNSENT, _abs_ids, _abs_paths, _blank, _cmd_run, _contract, _id_base,
    _key, _load, _mark_parked, _norm_id, _owed, _plan_tdd, _reached, _save, _unit, _unnamed_edits, _verified, hashes, id_path,
    red_check, restore, rules, snapshot, touched)

PHASES = ("test", "fix", "refactor")   # 振り分けの段は輪の外の route-loop（src/route.py）
MAX_ITERATIONS = 40   # YAML の tdd-loop の max_iterations と同じ値（試験が縛る）。この周に届いたら残りを direct にして抜ける
ROUTES = fixnames.ROUTES   # 入力 routes の語（src/files.py の 1 か所）
PLAN_NO_TDD = "承認済みの修正案に route が tdd の単位が無い（入力 routes: plan）——TDD の輪を回さず、ほかの型の注文で直す"
PLAN_DIRECT = "承認済みの修正案の route が direct（入力 routes: plan。行の route_why が無い）"
PLAN_NO_ROW = "承認済みの修正案にこの単位を持つ行が無い（入力 routes: plan は案の route に従い、行の無い単位は direct）"
SESSION_KEY = "session_key"   # 状態の欄: 前の周の支度が組んだ単位の鍵（prep の new_unit の元。元 write_key の鍵）
GAVE_UP_WHY = "機械が書いた申し出（TDD の確認が回数の上限まで通らなかった）: "   # 3 回拒まれた単位の申し出の why の頭
STATE, PROMPT, SUMMARY, RECORD = "state.json", "next.md", "summary.md", fixnames.RECORD_FILE   # STATE は輪の状態のファイルの名。名を持つのはこの部品だけ（輪の外は記録 RECORD を読む）
# 実行器への合図（env）: 1 なら後ろに足した試験（ファイル・node id）だけを走らせてよい（既定の一式を集めない）。輪の赤・緑の回だけが
# 付ける（元の結末・受け付け・版の写しは付けない）。解かない実行器は無視してよい（一式に足して走らせても確かめは同じ）
ONLY_ENV = "TDD_SUITE_ONLY"
# 単位ごとの深さ（入力 unit_depths の値）のうち、緑の後の test_cmd を走らせない語。出口の単位の test_cmd はその時 CMD_LIGHT
LIGHT = "軽量"
CMD_LIGHT = "light"
SUITE_MADE_NOTE = "一式を走らせて出来たファイル"
ROUTE_REFUSED = "振り分けの段（単位の名の無い拒否）"


class _RunnerDown(Exception):
    """実行器が走らない・JUnit が読めない（テストや直しの誤りではない。やり直しの回数を使わずに輪を抜け、組を no-suite で止める）"""
    head = "テストの実行器が走らない"


class _CmdDown(_RunnerDown):
    """run の test_cmd が走らない（実行器が走らない時と同じ道で輪を抜ける。理由の頭の語だけ違う）"""
    head = "テストのコマンドが走らない"


def retry_max() -> int:
    """段ごとの諦めの回数（rolekit.GIVE_UP_AFTER。元の写しの rules の RETRY_MAX と同じ 3）"""
    return rolekit.GIVE_UP_AFTER


# ---------------------------------------------------------------- 一式を走らせる（run_suite・_failure_attrs は baseline_red の物）
# 走る前の失敗（読み込み・組み立ての失敗で名指しが一式の結末に居ない・error）の拒否に _test だけが足す 1 行。red_check と写しの
# red_problems の文は事実だけで、事後の関門（fixgates）の行にもこの言い足しは入らない
NOT_RAN = ("赤に数えない。テストの中の検査で落ちる形に書き直せるならそうし、これから足す名前の欠けで書き直せないなら最小の仮の実装を"
           "足し、テスト自身の誤りならテストを直して、走らせ直せ")


def _open_units(raw: str) -> list:
    try:
        keys = json.loads(raw)
    except ValueError as e:
        raise Broken(f"open_units が JSON として読めない（{e}）")
    if not isinstance(keys, list) or not all(isinstance(k, str) and k for k in keys):
        raise Broken(f"open_units が単位の key の配列でない（{raw[:200]!r}）")
    return keys


def _duty(board_dir: pathlib.Path, owed=None, withheld_by=None, returned=()):
    """(直す義務 owed か None, 直す義務から外れた単位 {key: 理由})（fixboard.fix_duty。受け付けと同じ 1 つの集合）。owed は写しの
    規則の直す義務の単位、withheld_by・returned は問いの台帳の値（どれも呼び手が渡す。元は盤面 board_dir を開いて読んだ）。
    owed が None（渡されない run）は (None, {})。読めなければ Broken（開いた単位のまま黙って続けない）"""
    if owed is None:
        return None, {}
    try:
        got, excused = fixboard.fix_duty(board_dir, owed, withheld_by=withheld_by, returned=returned)
        return set(got), dict(excused)
    except Exception as e:
        raise Broken(f"置き場 {board_dir} の直す義務が読めない: {e}") from None


def plan_contract(board_dir: pathlib.Path, keys: list[str], round_: int = 1) -> dict[str, dict]:
    """単位 → 承認済みの修正案の約束（planmarks.unit_contract。約束の無い単位は載せない）。置き場 board_dir に凍結した欄の控え
    （plan-fields.json と trace.jsonl の凍結の印）が無い run は {}。欄の控えが凍結の印と食い違う（conflict.frozen_fields の
    ValueError）なら、理由の文のまま Broken（約束を黙って空にしない）。元は盤面を開いて読んだ"""
    try:
        fields = conflict.frozen_fields(pathlib.Path(board_dir), round_)
    except ValueError as e:
        raise Broken(str(e)) from None
    return {k: c for k in keys if (c := planmarks.unit_contract(fields, k)) is not None}


def _light_units(raw: str) -> list:
    """入力 unit_depths（{"<単位の key>": "軽量" | "標準"} の JSON の文字列。空は {}）のうち LIGHT の単位の key。形が違えば Broken"""
    if not (raw or "").strip():
        return []
    try:
        doc = json.loads(raw)
    except ValueError as e:
        raise Broken(f"unit_depths が JSON として読めない（{e}）")
    if not isinstance(doc, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in doc.items()):
        raise Broken(f"unit_depths が単位の key から深さの語への object でない（{raw[:200]!r}）")
    return sorted(k for k, v in doc.items() if v == LIGHT)


BASE_FIELDS = ("exe", "suite", "baseline", "baseline_exit", "baseline_cases", "suite_made", "test_cmd", "test_cmd_gate",
               "test_cmd_note", "reused", "related")   # 元の結末の控え base.json から輪の状態へ写す欄（同じ名と形）


ROUTE_CARRY = ("open_units", "excused", "contract", "order", "units", "parked", "parked_why", "note", "handoff", "unsent")
# 振り分けの状態（place の route.json。src/route.py）から輪の状態へ移す欄（orders が輪の状態を作る時。同じ名と形。contract は振り分けが
# 見た約束のまま使う）。数え（iterations・calls）と渡した証拠の種類（kinds）は注文の型ごとの欄 orders.tdd（route.counted）で渡る。
# tries・reason は assign が空に戻し、runs・suite_made・light・元の結末の欄は new_state が組み直す（振り分けは実行器を走らせない）


def new_state(board_dir, repo, base_file, open_units: list, work, *, owed=None, withheld_by=None, returned=(), round_: int = 1,
              light=()) -> dict:
    """輪の状態の辞書を組む（ファイルを置かず、work の置き場も作らない。work は状態の欄にそのまま書く）。元の結末は組の頭が取った
    base_file（src/basecase.take）の欄を同じ名で写す（輪の頭で試験を走らせ直さない）。段は route。owed・withheld_by・returned は
    直す義務の値（_duty）、round_ は凍結した欄の周（plan_contract）、light は緑の後の test_cmd を走らせない軽量の単位"""
    from src import basecase
    base = basecase.read_file(base_file)
    if not base or not base.get("taken"):
        raise Broken(f"元の結末の控え {base_file} が無いか、元の結末を取っていない")
    keys = list(open_units)
    board_dir = pathlib.Path(board_dir)
    owed, excused = _duty(board_dir, owed, withheld_by, returned)
    if owed is not None:   # 振り分ける義務は受け付けと同じ fix_duty の owed（渡された is_open の並びに、関所で答えて戻った単位を足す）
        keys = [k for k in keys if k in owed or k in excused] + sorted(owed - set(keys))   # is_open の並び順を保つ
    excused = {k: why for k, why in excused.items() if k in keys}
    contract = plan_contract(board_dir, keys, round_)   # 輪の頭で 1 回だけ（欄の控えの食い違いは conflict の 1 か所で止める）
    return {**{f: base[f] for f in BASE_FIELDS}, "work": str(work), "base_file": str(base_file), "open_units": keys,
            "excused": excused, "handoff": snapshot(repo), "phase": "route", "tries": 0, "reason": "", "iterations": 0,
            "runs": 1, "order": [], "units": {}, "queue": [], "cur": 0, "unit_head": "", "green_tree": "",
            "done": False, "note": "", "frozen": {}, "parked": [], "parked_why": {}, "contract": contract,
            "light": sorted(set(light) & set(keys)), "calls": [], "kinds": []}


def open_state(board_dir, repo, base_file, open_units: list, *, owed=None, withheld_by=None, returned=(), round_: int = 1,
               light=(), routed: dict | None = None, counted: dict | None = None) -> str:
    """輪の状態を置き、状態のファイルのパスを返す（組の子の node orders が、振り分けの後か振り分けを起こさない組で呼ぶ。輪の置き場
    tdd-<k>/ もここで初めて作る）。routed は振り分けの状態 route.json（src/route.py）の辞書で、あれば ROUTE_CARRY の欄を移し、段を
    振り分けが済んだ印のままにする。counted は注文の型ごとの欄 orders.tdd {iterations, calls, kinds}（route.counted）で、輪はそこから
    数え始める（回数の上限 MAX_ITERATIONS・呼びの控え calls・渡した証拠の種類の控え kinds）。段が route のまま置くのは tdd.start
    （routes が plan の手早い口）で、assign が tdd の単位の並びを置く"""
    board_dir = pathlib.Path(board_dir)
    k = 1
    while (board_dir / f"tdd-{k}").exists():
        k += 1
    work = board_dir / f"tdd-{k}"
    st = new_state(board_dir, repo, base_file, open_units, work, owed=owed, withheld_by=withheld_by, returned=returned,
                   round_=round_, light=light)
    if routed:
        st.update({f: routed[f] for f in ROUTE_CARRY if f in routed}, phase=routed["phase"])
    if counted:
        st.update(iterations=int(counted["iterations"]), calls=list(counted["calls"]), kinds=list(counted["kinds"]))
    work.mkdir(parents=True)
    state_file = work / STATE
    _save(state_file, st)
    return str(state_file)


def assign(state_file, repo, routes: dict, whys: dict | None = None) -> None:
    """注文の node（orders）が、型の表で tdd に引いた単位の並びを輪の状態に置き、段を test にする。routes は単位 → 輪の行の route
    （tdd か direct。振り分けを済ませた状態では振り分けの行をそのまま使い、無い単位は direct の行を足す）、whys は direct の行の訳。
    tdd の単位が無ければ輪を済ませ、輪の後の修正役へ渡す要約を書く（_finish）"""
    st = _load(state_file)
    whys = whys or {}
    order = list(st.get("order") or [])
    order += [k for k in routes if k not in order]
    units = dict(st.get("units") or {})
    for k in order:
        if k not in units:
            units[k] = _unit(k, routes[k] if routes.get(k) == "tdd" else "direct", "" if routes.get(k) == "tdd" else whys.get(k, ""))
        elif routes.get(k) == "tdd" and units[k].get("route") != "tdd":
            units[k] = _unit(k, "tdd")
        elif routes.get(k) != "tdd" and units[k].get("route") == "tdd":   # 型の表が tdd でない型を引いた単位（計画の語・消す名）
            units[k] = _unit(k, "direct", whys.get(k, ""))
    st.update(order=order, units=units, queue=[k for k in order if units[k]["route"] == "tdd"], cur=0, done=False,
              tries=0, reason="")
    _next_unit(st, repo)
    if st["done"]:
        _finish(st, repo)
        _write_record(st)
    _save(state_file, st)


def start(board_dir, repo, suite: str, open_units: str, test_cmd: str = "", unit_depths: str = "", *,
          owed=None, withheld_by=None, returned=(), round_: int = 1, reuse: dict | None = None, narrow: bool = False,
          routes: str = "auto", suite_made: bool = False) -> dict:
    """組の頭（src/basecase.take）と輪の状態（open_state）を 1 回で組む口（単独の呼びと試験の手早い口。組の子は group-start・
    route-go・orders の 3 つの node でこれと同じ順に呼ぶ）。{go, reason, suite, state_file, summary_file, base_file}。
    routes が plan なら振り分けの段の AI を起こさず、承認済みの案の route（約束の route が tdd の単位を tdd）で単位を振って test の
    段から始める（tdd の単位が無ければ go: false。PLAN_NO_TDD）。auto なら振り分けの状態 route.json を置き、state_file はそのパス
    （src/route.step が回す。輪の状態は振り分けの後に注文の node orders が置く）。
    narrow・reuse・suite_made・test_cmd は元の結末の取り方（basecase.take）へ。narrow は related.applies の代わりに渡す"""
    from src import basecase
    from src import route as router
    if routes not in ROUTES:
        raise Broken(f"入力 routes は {'・'.join(ROUTES)} のどれか（{routes!r}）")
    keys = _open_units(open_units)
    board_dir = pathlib.Path(board_dir)
    values = {"tdd_suite": suite, "test_cmd": test_cmd, "suite_made": suite_made}
    head = basecase.take(board_dir, repo, values, keys, reuse, words={}, rev="HEAD", round_=round_, narrow=narrow)
    if not head.get("base_file") or head.get("suite_broken"):
        return {**head, "go": False}
    if not basecase.read_file(head["base_file"]).get("taken"):
        return {**head, "go": False}
    if routes == "plan":
        _, excused = _duty(board_dir, owed, withheld_by, returned)
        contract = plan_contract(board_dir, keys, round_)
        if not any((contract.get(k) or {}).get("route") == "tdd" for k in keys if k not in excused):
            return {**head, "go": False, "reason": PLAN_NO_TDD}
    light = _light_units(unit_depths)
    if routes != "plan":   # 振り分けの状態 route.json を置く（輪の状態は注文の node orders が振り分けの後に作る。試験の助けは steps.loop_step）
        state_file = router.open_route(board_dir, repo, head["base_file"], keys, owed=owed, withheld_by=withheld_by,
                                       returned=returned, round_=round_, light=light)
        return {**head, "go": True, "state_file": state_file, "summary_file": ""}
    state_file = open_state(board_dir, repo, head["base_file"], keys, owed=owed, withheld_by=withheld_by, returned=returned,
                            round_=round_, light=light)
    st = _load(state_file)
    whys = router.plan_whys(board_dir, keys, round_)
    routed = {k: "tdd" if (_contract(st, k) or {}).get("route") == "tdd" else "direct" for k in _owed(st)}
    assign(state_file, repo, routed, {k: whys.get(k) or (PLAN_DIRECT if _contract(st, k) else PLAN_NO_ROW) for k in routed})
    return {**head, "go": True, "state_file": state_file, "summary_file": str(pathlib.Path(state_file).parent / SUMMARY)}


def _test_cmd_problems(st, repo) -> list[str]:
    """関門が on の時だけ run の test_cmd を 1 回走らせ（ログ work/test-cmd-<runs>.log。runs を 1 進め、出来たファイルを
    suite_made に積む。書き換えた既存のファイルは _cmd_run が戻して積まない）、赤ならログのパスを含む拒否の文。緑なら今の単位の
    test_cmd を ok にする（_green は今の単位にしか呼ばれない）。走らなければ _CmdDown（実行器が走らない時と同じ道）。
    既存のファイルを書き換えた回は赤（_cmd_run）。今の単位が軽量（状態の light）なら走らせず、単位の test_cmd を CMD_LIGHT にする
    （同じコマンドを run の最後のテストが木の全部で走らせるので、確かめは消えない）"""
    if st.get("test_cmd_gate") != GATE_ON:
        return []
    if _cur(st)["unit_key"] in st.get("light", []):
        _cur(st)["test_cmd"] = CMD_LIGHT
        return []
    log = pathlib.Path(st["work"]) / f"test-cmd-{st['runs']}.log"
    mat, made = _cmd_run(repo, st["test_cmd"], log)
    st["runs"] += 1
    st["suite_made"] = sorted(set(st["suite_made"]) | set(made))
    if mat["status"] == "not_run":
        raise _CmdDown(f"run の test_cmd（{st['test_cmd']}）: {mat.get('reason', '')}")
    if mat["status"] == "clean":
        _cur(st)["test_cmd"] = "ok"
        return []
    tail = oneline.one_line(mat.get("detail", ""))[-400:]
    return [f"名指しのテストと一式は緑だが、run の test_cmd（{st['test_cmd']}）が赤（ループの頭では緑。ログ {log}）——"
            f"これも緑にせよ（赤の元が凍ったテストのファイルなら phase conflict で申し出よ）。{mat.get('rewrote') or '末尾: ' + tail}"]


# ---------------------------------------------------------------- 指示書（節 tdd-prep）
def _briefs(board_dir: pathlib.Path, **sources) -> list:
    """置き場の brief（planbrief.cut_at。sources は cut の材料。控えが在ればそれを返す。置き場が無い・材料の無い run は []）。
    控えが壊れていれば理由の Broken（fixrules.brief_halt の文。brief の無い指示書として続けない。止めるのは呼び手）"""
    try:
        return planbrief.cut_at(board_dir, **sources)
    except planbrief.LedgerBroken as e:
        raise Broken(fixrules.brief_halt(e)) from None


# 引き継ぎ（依頼 243 の 2）。輪の役は周ごとに新しい会話で起きる（同じ単位の段の間も会話を継がない）ので、前の単位が何を変えたかと、
# 今の周の段・今の単位・この単位の前の段の結果を、会話の履歴でなく機械が状態から書いて渡す（prep の今の単位の節の後。振り分けの
# 段は義務の単位の後）
HANDOFF_HEAD = "## 前の単位の引き継ぎ（機械が状態から書いた物）"


def current_lines(st) -> list:
    """今の周の段・今の単位・この単位の前の段の結果の行（handoff_lines が必ず載せる。元は同じ単位の段を同じ会話で続けたので、
    指示書に書かなかった物: 段と拒まれた回・test の段の仮の実装のファイル・fix の段の直しと整えの申告の理由）"""
    phase = st["phase"]
    tries = st.get("tries") or 0
    again = [f"- この段の返答は {tries} 回拒まれた（理由は上の「前の回の返答を機械が拒んだ理由」）"] if tries else []
    if phase == "route":
        return ["- 今の段: route（直す義務の単位の振り分け）。このループの最初の段で、前の段の結果は無い", *again]
    if phase not in ("test", "fix", "refactor") or not st.get("queue") or st["cur"] >= len(st["queue"]):
        return [f"- 今の段: {phase}", *again]
    u = _cur(st)
    rows = [f"- 今の段: {phase}・今の単位: {u['unit_key']}（振り分けは tdd）"]
    if phase == "test":
        rows.append("- 前の段: 振り分け（この単位は tdd）。この単位の段はここから")
    if phase in ("fix", "refactor"):
        rows.append(f"- test の段の結果（機械が赤を確かめた）: 名指しのテスト {', '.join(u.get('tests') or []) or 'なし'}・"
                    f"テストのファイル（凍っている） {', '.join(u.get('test_files') or []) or 'なし'}")
        if u.get("stub_files"):
            rows.append(f"- test の段で足したテストでないファイル（仮の実装）: {', '.join(u['stub_files'])}")
    if phase == "refactor":
        rows.append(f"- fix の段の結果（機械が緑を確かめた）: 直したファイル {', '.join(u.get('files') or []) or 'なし'}・"
                    f"直し: {(u.get('what') or '')[:300]}")
        rows.append(f"- 整えの申告の理由: {(u.get('refactor_why') or '')[:300]}")
    return rows + again


def handoff_lines(st) -> list:
    """今の単位より前に済んだ単位の 1 行ずつ（単位の key・直したファイル・緑にしたテスト・整え・止めた理由・direct に回した理由）と、
    今の周の段・今の単位・この単位の前の段の結果（current_lines）。周ごとに新しい会話で起きるので、節はいつも載せる"""
    rows = []
    for k in st["queue"][:st["cur"]]:
        u = st["units"].get(k)
        if not u:
            continue
        if u.get("route") == "parked":
            rows.append(f"- {k}: 食い違いの申し出で止めた（木は単位の頭に戻した）: {u.get('why', '')[:200]}")
            continue
        if u.get("gave_up"):
            rows.append(f"- {k}: 諦めて direct に回した（木は単位の頭に戻した。修正役が直す）: {u.get('why', '')[:200]}")
            continue
        if u.get("covered_by"):
            rows.append(f"- {k}: 同じ修正案の項目の単位 {'、'.join(u['covered_by'])} の段で一緒に直した（受け入れのテスト "
                        f"{', '.join(u.get('tests') or [])} はループが赤→緑を確かめ済み）")
            continue
        bits = [f"直したファイル {', '.join(u.get('files') or []) or 'なし'}",
                f"緑にしたテスト {', '.join(u.get('tests') or []) or 'なし'}"]
        if u.get("refactor"):
            bits.append(f"整え {u['refactor']}")
        rows.append(f"- {k}: " + "・".join(bits))
    head = ["前の単位の直しは作業ツリーに在る（緑の木）。戻したり作り直したりするな。", ""] if rows else []
    return [HANDOFF_HEAD, "", *head] + rows + ([""] if rows else []) + current_lines(st) + [""]


# 今の単位と一緒に直す単位（同じ修正案の項目の後の単位。together）の節の見出し（prep）
TOGETHER_HEAD = "## 今の単位と一緒に直す単位（同じ修正案の項目。1 つの brief と 1 つのやり方を共にする）"


def _items(st, k) -> set:
    """単位 k の約束の修正案の項目の番号（約束が無ければ空）"""
    return set((_contract(st, k) or {}).get("items") or [])


def together(st, k) -> list:
    """単位 k の段で一緒に直す単位: 順（queue）で k より後の tdd の単位のうち、約束の受け入れのテストを持ち、載る修正案の項目が
    全部 k の項目にも在る物（順の並び）。k の段は項目の受け入れのテストを全部名指して緑にする（_test の want）ので、その単位の
    直しも要る。k の段が緑に届けば、その単位は機械が閉じる（_close_covered。同じ条件）。k に無い項目にも載る単位・約束の無い
    単位・別の項目の単位は入らない（今どおり「この後の単位（今は手を付けるな）」。その単位は自分の段で赤を書く）"""
    mine = _items(st, k)
    if not mine or k not in st.get("queue", []):
        return []
    later = st["queue"][st["queue"].index(k) + 1:]
    return [q for q in later if (st["units"].get(q) or {}).get("route") == "tdd" and _plan_tests(st, q)
            and _items(st, q) <= mine]


def _together_lines(st, k) -> list:
    """指示書の「今の単位と一緒に直す単位」の節（together が空なら []）"""
    keys = together(st, k)
    if not keys:
        return []
    return [TOGETHER_HEAD, "",
            "次の単位は今の単位と同じ修正案の項目に載る。この単位の段（test・fix・refactor）で今の単位と一緒に扱え: test の段は"
            "項目の受け入れのテストを全部名指して赤にし、fix の段はこれらの単位の直しも含めて名指しを緑にする。緑に届けば機械が"
            "これらの単位を閉じる（別の段は来ない）。", ""] + [f"- {q}" for q in keys] + [""]


def prep(state_file, sources=None) -> dict:
    """node tdd-prep の材料（指示の文は prompts/parts/tdd.md。値と段落の真偽は src/prompts.py の tdd_values が組む）。
    返り {go, new_unit, state, path, briefs}: state は輪の状態、path は輪の置き場の印（今の next.md の場所。単位の鍵の名に使う）、
    briefs は置き場の brief（_briefs。sources は brief を切る材料。置き場に控えが在れば読まない。控えが壊れていれば Broken）。
    輪が済んでいる（状態の done）なら {"go": False, "new_unit": False}:
    確かめの node が状態にそれを保存した後、実行基盤が輪の済みを記録する前に止まった run を、実行基盤の resume は輪の 1 周目から
    回し直す（役の node は when: で飛び、確かめ step は返答 None で何も動かさずに輪を抜ける）。
    new_unit は単位の鍵（輪の置き場の名と、振り分けの段は route・ほかの段は今の単位）が前の周の支度の鍵（状態の SESSION_KEY）と
    違う周だけ真: YAML がそれで役を振り分け、同じ単位の段は前の周の会話を継ぎ、単位が替わる周だけ新しい会話で起こす（元は
    包みが同じ鍵で会話を切った: works/blk-fix/lib/tddloop.py:880 write_key）。新しい会話でも前の単位の物は引き継ぎの行（handoff_rows）で渡る"""
    st = _load(state_file)
    if _over(st):   # resume で 1 周目から回し直された済んだ輪: 役を起こさない（YAML の役の when: が go を読む）
        return {"go": False, "new_unit": False}
    path = pathlib.Path(st["work"]) / PROMPT
    briefs = _briefs(path.parent.parent, **(sources or {}))   # 状態の置き場は fix の置き場の tdd-<k>
    key = f"{path.parent.name}:{st['queue'][st['cur']]}"
    new_unit = st.get(SESSION_KEY) != key
    if new_unit:
        st[SESSION_KEY] = key
        _save(state_file, st)
    return {"go": True, "new_unit": new_unit, "state": st, "path": path, "briefs": briefs}


def handoff_rows(st) -> tuple[bool, list]:
    """(前の単位の行が在るか, 引き継ぎの行)。handoff_lines の見出しと決まった文を除いた行（見出しと文は md）"""
    lines = handoff_lines(st)
    head = ["前の単位の直しは作業ツリーに在る（緑の木）。戻したり作り直したりするな。", ""]
    rows = lines[2:]   # 見出しと空行
    had = rows[:2] == head
    rows = rows[2:] if had else rows
    return had, [r for r in rows if r]


def together_rows(st, k) -> list:
    """「今の単位と一緒に直す単位」の行（_together_lines の見出しと決まった文を除いた物）"""
    return [f"- {q}" for q in together(st, k)]


def _over(st: dict) -> bool:
    """輪を抜けた状態か（済んだ done）。確かめ step の出口の done と同じ"""
    return bool(st["done"])


def _paths(v, name) -> tuple:
    """空でない文字列の配列 → (要素の決まり fixboard.test_file で整えたパスの一覧, 問題)"""
    out = [fixboard.test_file(x) for x in v] if isinstance(v, list) else []
    if not out or None in out:
        return [], [f"{name} は空でない文字列の配列"]
    bad = [x for x in out if x.startswith("/") or x == ".." or x.startswith("../")]
    return out, ([f"{name} はリポジトリの根からの相対パス（{bad}）"] if bad else [])


def _run(st, repo, named=(), files=(), full=False):
    """実行器を 1 回走らせ、走らせて出来たファイルを suite_made に積む（テストを書く段が触ったファイルの数えから外す）。
    名指しは絶対パスの node id、files（根からの相対の試験のファイル）は絶対パスで実行器の後ろに足す（段の外に書いたテストも
    同じ 1 回で集める。段の中の名指しとの重なりは run_suite が 1 件にまとめる。後ろの引数を解かない実行器なら段の外の名指しは
    居ないままで、赤・緑の確認が今どおり拒む）。full でなければ合図 ONLY_ENV を付ける（後ろの試験だけ）。
    last_run（消えたテストの照らしの元）: outcome・args（名指しと files）・whole（ファイルごと足したモジュール）・full・log（この回の
    ログのパス。赤の引用を役が引いた時の照らし先）"""
    pre = snapshot(repo)
    work, n = pathlib.Path(st["work"]), st["runs"]
    cases, code, why = run_suite(st["exe"], repo, work, n, _abs_ids(repo, named) + _abs_paths(repo, files), only=not full)
    st["runs"] += 1
    st["suite_made"] = sorted(set(st["suite_made"]) | set(touched(repo, pre, snapshot(repo))))
    if cases is None:
        raise _RunnerDown("; ".join(why))
    st["last_run"] = {"outcome": {_key(c): c["outcome"] for c in cases}, "args": [*named, *files],
                      "whole": sorted({impact._mod(f) for f in files}), "full": bool(full), "log": str(work / f"suite-{n}.log")}
    return cases, code


def _next_head(prev: dict, run: dict) -> dict:
    """次の単位の頭の回（純粋）: 一式の回（full）はそのまま。絞った回は、前の頭の結末に、その回の結末を重ねた物（ファイルごと
    走ったモジュール（whole）の前の行は捨てる。走っていないモジュールは前の頭の結末のまま）。重ねた回は同じ選びの回に数えない
    （args は None）"""
    if not run or run.get("full", True):
        return run
    whole = set(run.get("whole") or [])
    kept = {k: o for k, o in prev.get("outcome", {}).items()
            if impact._junit_module({"classname": k.partition("::")[0]}) not in whole}
    return {"outcome": {**kept, **run["outcome"]}, "args": None, "whole": [], "full": False}


def _cur(st) -> dict:
    return st["units"][st["queue"][st["cur"]]]


def _covered_by(st, k) -> list:
    """単位 k を一緒に直した、緑に届いた tdd の単位（順の並び）。k の約束の受け入れのテスト（と書き換えの名指し）が在って全部
    輪が赤→緑を確かめ済み（_verified）で、k の修正案の項目を全部持つ緑の単位が在る時だけ（その単位の段が k を together に並べた
    条件と同じ）。ほかは []"""
    ids = {_norm_id(t["id"]) for t in _plan_tests(st, k)} | {_norm_id(i) for i in _plan_rewrites(st, k)}
    mine = _items(st, k)
    if not ids or not mine or not ids <= _verified(st):
        return []
    return [g for g, u in st["units"].items() if g != k and u.get("route") == "tdd" and u.get("green") == "ok"
            and not u.get("covered_by") and mine <= _items(st, g)]


def _close_covered(st) -> None:
    """順の今の単位が、同じ修正案の項目の前の単位の段で一緒に直されていれば（_covered_by）、段を回さずに閉じて次へ進む（続く限り）。
    閉じた単位は赤・緑とも ok で、名指しは約束の受け入れのテスト、テストのファイル・直したファイル・整え・test_cmd は一緒に直した
    単位の物を写し（軽量で走らせなかった印 CMD_LIGHT は、閉じた単位も軽量の時だけ）、赤の引用（red_quotes）と照らせなかった名指し
    （quote_unchecked）は名指しを確かめた緑の単位の全部から引き、covered_by にその単位を、why に一緒に直したことを書く"""
    while st["cur"] < len(st["queue"]):
        k = st["queue"][st["cur"]]
        by = _covered_by(st, k)
        if not by:
            return
        src = st["units"][by[0]]
        tests = [t["id"] for t in _plan_tests(st, k)] + [i for i in _plan_rewrites(st, k)]
        want = {_norm_id(x) for x in tests}
        proven = [v for v in st["units"].values() if v.get("route") == "tdd" and v.get("green") == "ok"]   # 確かめた単位の全部から
        quotes = {t: q for v in proven for t, q in (v.get(QUOTES_FIELD) or {}).items() if _norm_id(t) in want}
        unchecked = sorted({t for v in proven for t in v.get("quote_unchecked") or [] if _norm_id(t) in want})
        st["units"][k].update(red="ok", green="ok", tests=tests, test_files=list(src.get("test_files") or []),
                              test_hashes=dict(src.get("test_hashes") or {}), quote_unchecked=unchecked,
                              stub_files=list(src.get("stub_files") or []), files=list(src.get("files") or []),
                              refactor=src.get("refactor", ""), **{QUOTES_FIELD: quotes},
                              refactor_why=src.get("refactor_why", ""), covered_by=by,
                              test_cmd="" if src.get("test_cmd") == CMD_LIGHT and k not in st.get("light", []) else src.get("test_cmd", ""),
                              what=f"同じ修正案の項目の単位 {'、'.join(by)} の段で一緒に直した",
                              why=f"同じ修正案の項目の単位 {'、'.join(by)} の段で一緒に直した（受け入れのテストはループが赤→緑を確かめ済み）")
        st["cur"] += 1


def _next_unit(st, repo) -> None:
    """次の単位の頭を固める。機械が戻した木（諦め・申し出・direct_why）もここを通るので、前の段の印（handoff）もここで進める。
    同じ修正案の項目の前の単位の段で一緒に直された単位は、段を回さずに閉じる（_close_covered）"""
    _close_covered(st)
    if st["cur"] < len(st["queue"]):
        head = snapshot(repo)
        st.update(phase="test", tries=0, reason="", unit_head=head, handoff=head, green_tree="")
    else:
        st["done"] = True


def _to_direct(u, stage, why, probs=()) -> None:
    u.update(route="direct", gave_up=stage, why=why, problems=list(probs)[:10])


def _plan_tests(st, k) -> list:
    """単位 k の約束の受け入れのテスト [{id, red_kind}]（約束が無ければ空）"""
    return (_contract(st, k) or {}).get("tests") or []


def _plan_rewrites(st, k) -> list:
    """単位 k の約束の書き換えの名指し（修正案の rewrite_tests の id。planmarks.rewrites と同じ行から作った物。約束が無ければ空）"""
    return (_contract(st, k) or {}).get("rewrites") or []


def declared_test_files(st) -> set[str]:
    """宣言されたテストのファイル: 単位ごとの役の申告（test_files）と、承認済みの修正案の約束の受け入れのテスト（tests）・書き換えの
    名指し（rewrites）のパス。テストのファイルの見分け（impact.is_test_file）の宣言の正本。純粋"""
    out = set()
    for u in (st.get("units") or {}).values():
        out |= set(fixboard.unit_test_files(u))
    for c in (st.get("contract") or {}).values():
        ids = [t.get("id") for t in (c or {}).get("tests") or [] if isinstance(t, dict)] + list((c or {}).get("rewrites") or [])
        out |= {id_path(i) for i in ids if isinstance(i, str) and i.strip()}
    return out


def _moved_test_files(st, repo, exclude=()) -> list[str]:
    """単位の頭から変わったテストのファイル（impact.is_test_file。走らせて出来たファイルと exclude を除く）"""
    moved = set(touched(repo, st["unit_head"], snapshot(repo))) - set(st["suite_made"]) - set(exclude)
    declared = declared_test_files(st)
    return sorted(f for f in moved if impact.is_test_file(f, declared))


def _cut_lines(repo, tree: str, files: list[str]) -> list[str]:
    """files のうち木 tree に在った .py でないファイルで、tree から今の作業ツリーまでに行を消した・置き換えた物（足すだけは
    数えない。バイナリ・消したファイルは数える）。テストの関数の幅は言語に依らず引けないので、ファイルの単位で見る（.py は
    _unnamed_edits が関数の単位で見る）"""
    other = [f for f in files if not f.endswith(".py")]
    there = sorted(set(git_names(repo, "ls-tree", "-r", "--name-only", tree, "--", *other))) if other else []
    if not there:
        return []
    out = []
    for row in git(repo, "diff-tree", "-r", "-z", "--numstat", "--no-renames", tree, snapshot(repo), "--", *there).split("\0"):
        if row.count("\t") >= 2:
            _added, deleted, path = row.split("\t", 2)
            if deleted != "0":
                out.append(path)
    return sorted(out)


def _syntax_problems(repo, files) -> list[str]:
    """files のうち作業ツリーに在る .py で、構文として読めない物の文（_unnamed_edits が関数を全部『書き換えた』と並べる前に、
    構文の誤りとして名指す）"""
    out = []
    for f in files:
        p = pathlib.Path(repo) / f
        if not f.endswith(".py") or not p.is_file():
            continue
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError) as e:
            where = f"{getattr(e, 'lineno', None)} 行" if getattr(e, "lineno", None) else "行は不明"
            out.append(f"{f}: 構文が読めない（{getattr(e, 'msg', e)}・{where}）——テストのファイルを構文として読める形に直して出し直せ")
    return out


def _other_test_edits(st, u, repo) -> list[str]:
    """約束の在る単位の直し・整えの段: 単位の頭から変わったテストのファイル（_moved_test_files。単位のテストのファイルを除く）
    の構文の誤り（_syntax_problems）と、既存の test* 関数の本体の書き換え（_unnamed_edits。許しは無し）の文"""
    if _contract(st, u["unit_key"]) is None:
        return []
    files = _moved_test_files(st, repo, u["test_files"])
    bad = _syntax_problems(repo, files)
    if bad:
        return bad
    edits = _unnamed_edits(repo, st["unit_head"], files, set())
    cut = _cut_lines(repo, st["unit_head"], files)
    return [f"既存のテスト {edits[:10]} の本体を書き換えた——直し・整えの段ではテストを変えない"
            "（テストの誤りは what に書け。変えるしかないなら phase conflict で申し出よ）"] * bool(edits) + \
        [f"既存のテストのファイル {cut[:10]} の行を消した・置き換えた——直し・整えの段ではテストを変えない"
         "（.py でないテストのファイルは行を足すだけを通す。テストの誤りは what に書け。変えるしかないなら phase conflict で申し出よ）"] * bool(cut)


def _vanish_scope(files, declared=frozenset()) -> set | None:
    """消えたテストを照らすモジュール（impact._mod の名）。files のうちテストのファイル（impact.is_test_file）だけを見る。conftest.py か
    .py でないテストのファイルに触れていれば None（一式の全部。.py でないファイルは JUnit の行とモジュールを言語に依らず結べない
    ので、分からない＝全部を照らす）。純粋"""
    files = [f for f in files if impact.is_test_file(f, declared)]
    if any(posixpath.basename(f) == "conftest.py" or not f.endswith(".py") for f in files):
        return None
    return {impact._mod(f) for f in files}


def _vanished(head: dict, refs: list, now: dict, args: list, scope, skip, whole=()) -> list[tuple[str, str]]:
    """単位の頭の回（head: {outcome: 鍵 → 結末, args: 実行器の後ろの引数}）で通っていたテストのうち、今の結末（now）で
    飛ばされた物と、今の回と同じ選び（args）の回（refs のどれか）に居たのに今は居ない物の [(鍵, skipped か missing)]。
    scope（_vanish_scope）の外のモジュールと、skip の id（_id_base で parametrize の `[…]` を落として比べる。修正案の書き換え・
    輪が確かめた id）に当たる鍵は見ない。選びの違う回の居ないは数えない（後ろの node id だけを走らせる実行器）。ただし今の回で
    ファイルごと走ったモジュール（whole。impact._mod の名）の居ないは、選びに依らず数える。args が None の回（重ねた頭）は
    どの回とも同じ選びでない。純粋"""
    same = [r for r in refs if r.get("args") is not None and sorted(r["args"]) == sorted(args)]
    whole = set(whole)
    out = []
    for k, o in head.get("outcome", {}).items():
        cls, _, name = k.partition("::")
        if o != "passed" or (scope is not None and impact._junit_module({"classname": cls}) not in scope):
            continue
        case = {"classname": cls, "name": name.split("[", 1)[0]}
        if any(rules().match_case(_id_base(i), [case]) for i in skip):
            continue
        got = now.get(k)
        if got == "skipped" or (got is None and (any(k in r.get("outcome", {}) for r in same)
                                                  or impact._junit_module({"classname": cls}) in whole)):
            out.append((k, got or "missing"))
    return out


def _head_run(st) -> dict:
    """単位の頭の回（前の単位の緑の回。最初の単位は元の結末。前の版の状態に無ければ元の結末）"""
    return st.get("head_run") or {"outcome": st["baseline"], "args": []}


def _vanished_problems(st, u, cases, args, repo) -> list[str]:
    """約束の在る単位で、単位の頭で通っていたテストが飛ばされた・結末から消えた物の文（クラスの setUp の skipTest・モジュールの
    末尾で消すなど、名指しの外の本体を変えずに外す抜け道。写しの red_problems・green_problems は落ちた物しか見ない）。
    照らすのは単位の頭から変わったテストのファイルのモジュールだけ（conftest.py に触れたら全部）。居ないを数えるのは、同じ
    選びの回（単位の頭の回か、この単位の赤の回）に居た時と、今の回（last_run）でファイルごと走ったモジュールの時"""
    if _contract(st, u["unit_key"]) is None:
        return []
    refs = [_head_run(st)] + ([u["red_run"]] if u.get("red_run") else [])
    skip = [*_plan_rewrites(st, u["unit_key"]), *_verified(st)]
    gone = _vanished(_head_run(st), refs, {_key(c): c["outcome"] for c in cases}, list(args),
                     _vanish_scope(_moved_test_files(st, repo), declared_test_files(st)), skip, st["last_run"].get("whole") or ())
    return [f"単位 '{u['unit_key']}' の段で、単位の頭で通っていたテスト {k} が {o}（飛ばされた・一式の結末から消えた）——"
            "名指しの外の既存のテストを外すな（外すなら phase conflict で申し出よ）" for k, o in gone[:20]]


def _quotes_of(reply, tests, required: bool):
    """test の段の返答の欄 QUOTES_FIELD → (red_check に渡す引用か None, 記録する {名指しの id: {quote, why}}, 問題)。
    欄が無いのは、約束の在る単位（required）なら {}（名指しごとの引用が要る。照らす先が無い名指しだけ red_check が除く）、
    約束の無い単位なら None（引用を求めない）。在って {id: {quote, why}} の形でなければ問題"""
    got = reply.get(QUOTES_FIELD)
    if got is None:
        return ({} if required else None), {}, []
    if not isinstance(got, dict) or not all(isinstance(v, dict) for v in got.values()):
        return None, {}, [f"{QUOTES_FIELD} は {{<名指しの id>: {{quote（失敗の文）, why（理由）}}}} の object"]
    named = {_norm_id(t) for t in tests if isinstance(t, str)}
    kept = {k: {"quote": str(v.get("quote", "")).strip(), "why": str(v.get("why", "")).strip()}
            for k, v in got.items() if isinstance(k, str) and _norm_id(k) in named}
    return got, kept, []


def _test(st, reply, repo) -> list:
    u = _cur(st)
    if "direct_why" in reply:
        if _blank(reply["direct_why"]):
            return [f"direct_why は {MIN_WHY} 字以上"]
        bound = _plan_tdd(st, u["unit_key"], "direct_why で direct に渡せない")
        if bound:
            return [bound]
        restore(repo, st["unit_head"])
        _to_direct(u, "writer", reply["direct_why"].strip())
        st["cur"] += 1
        _next_unit(st, repo)
        return []
    tests = reply.get("tests")
    ok_tests = isinstance(tests, list) and tests and all(isinstance(t, str) and t.strip() for t in tests)
    errs = [] if ok_tests else ["tests は名指しのテスト（<パス>::<クラス>::<名前>）の空でない配列"]
    files, bad = _paths(reply.get("test_files"), "test_files")
    errs += bad
    # 約束の名指し（形が崩れていても、名指せた分で照らして同じ返答に並べる）
    done = _verified(st)   # 前の単位で赤→緑を確かめた id は名指しを強いず、凍っている（同じ項目が 2 つの単位にまたがる時）
    want = [t for t in _plan_tests(st, u["unit_key"]) if _norm_id(t["id"]) not in done]
    rws = [i for i in _plan_rewrites(st, u["unit_key"]) if _norm_id(i) not in done]
    named = {_norm_id(t) for t in tests if isinstance(t, str) and t.strip()} if isinstance(tests, list) else set()
    miss = [t["id"] for t in want if _norm_id(t["id"]) not in named]
    if miss:
        errs.append(f"承認済みの修正案の受け入れのテストを名指していない: {miss}——brief の tests の id の名前でテストを書き、tests に入れよ。"
                    "案の前提が誤りなら phase conflict で申し出よ")
    errs += [f"{i}: 承認済みの修正案が書き換えを名指した既存のテスト——書き換えて名指しに入れよ" for i in rws if _norm_id(i) not in named]
    quotes, kept, bad = _quotes_of(reply, tests if ok_tests else [], _contract(st, u["unit_key"]) is not None)
    errs += bad
    if errs:
        return errs
    extra = sorted(set(touched(repo, st["unit_head"], snapshot(repo))) - set(files) - set(st["suite_made"]))
    declared = declared_test_files(st) | set(files)
    outside = [f for f in extra if impact.is_test_file(f, declared)]
    if outside:
        return [f"申告したテストのファイルの外のテストのファイルに触れた: {outside[:5]}——test_files に申告するか、触れるな"]
    stubs = [f for f in extra if f not in outside]   # テストでないファイル（これから足す名前の仮の実装）は拒まず、記録に残す
    if _contract(st, u["unit_key"]) is not None:
        bad = _syntax_problems(repo, files)
        if bad:
            return bad
        frozen = _unnamed_edits(repo, st["unit_head"], files, set(rws))
        if frozen:
            return [f"名指しの外の既存のテスト {frozen[:10]} の本体を書き換えた——書き換えてよいのは修正案の rewrite_tests の名指しだけ"
                    "（それ以外を変えるなら phase conflict で申し出よ）"]
    cases, code = _run(st, repo, tests)
    probs, unchecked = red_check(tests, cases, code, st["baseline"], quotes, st["last_run"]["log"])
    if probs and any((c := rules().match_case(t, cases)) is None or c["outcome"] == "error" for t in tests):
        probs.append(NOT_RAN)
    probs = probs or _vanished_problems(st, u, cases, tests, repo)
    if probs:
        return probs
    u.update(tests=tests, test_files=files, red="ok", test_hashes=hashes(repo, files), red_run=st["last_run"], red_tree=snapshot(repo),
             quote_unchecked=unchecked, stub_files=stubs, **{QUOTES_FIELD: kept})
    st.update(phase="fix", tries=0, reason="")
    return []


def _frozen_moved(u, repo) -> list:
    now = hashes(repo, u["test_files"])
    return [f for f in u["test_files"] if now[f] != u["test_hashes"][f]]


def _green(st, u, repo) -> list:
    moved = _frozen_moved(u, repo)
    if moved:
        return [f"テストのファイルを赤の時から書き換えた: {moved}——テストは凍っている（テストの誤りは what に書け）"]
    other = _other_test_edits(st, u, repo)
    if other:
        return other
    files, full = _reached(st, repo)
    cases, code = _run(st, repo, u["tests"], files, full)
    rel = st.get("related") or {}
    narrow = bool(full and rel.get("applied") and not rel.get("whole"))   # 元の結末が関わる試験だけで、今の回は全部の試験
    return rules().green_problems(u["tests"], cases, code, st["baseline"], st["baseline_exit"], narrow=narrow,
                                  also=sorted(_verified(st))) \
        or _vanished_problems(st, u, cases, st["last_run"]["args"], repo) or _test_cmd_problems(st, repo)


def _plan_refactor_why(st, k) -> str:
    """約束の refactor（申告した項目の [{item, why}]）を「修正案の項目 n: <理由>」でつないだ物。申告が無ければ空の文字列"""
    return "；".join(f"修正案の項目 {r['item']}: {r['why']}" for r in (_contract(st, k) or {}).get("refactor") or [])


def _declared(reply) -> tuple[str, list]:
    """fix の返答の任意の欄 refactor（{declared, why}）→ (申告の理由（申告が無ければ空の文字列）, 問題)"""
    r = reply.get("refactor")
    if r is None:
        return "", []
    if not isinstance(r, dict) or not isinstance(r.get("declared"), bool) or not isinstance(r.get("why"), str):
        return "", ["refactor は {declared（true か false）, why（文字列）}"]
    if not r["declared"]:
        return "", []
    if _blank(r["why"]):
        return "", [f"refactor.declared が true なら why（整える理由）を {MIN_WHY} 字以上で書け（整えないなら declared を false に）"]
    return r["why"].strip(), []


def _fix(st, reply, repo) -> list:
    """緑を確かめ、整えの申告（役の refactor.declared か、約束の refactor）の在る単位だけ refactor の段へ。無ければ skipped で
    次の単位へ（緑の木が次の単位の頭）"""
    u = _cur(st)
    files = reply.get("files")
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files) or not isinstance(reply.get("what"), str) \
            or not reply["what"].strip():
        return ["files（直したファイルの配列）と what（何をどう直したか）が要る"]
    why, probs = _declared(reply)
    if probs:
        return probs   # 一式を走らせる前に拒む
    probs = _green(st, u, repo)
    if probs:
        return probs
    why = "；".join(filter(None, [why, _plan_refactor_why(st, u["unit_key"])]))   # 空でない申告の理由を全部
    u.update(green="ok", files=files, what=reply["what"].strip(), refactor_why=why)
    st.update(tries=0, reason="", green_tree=snapshot(repo), green_run=st["last_run"])
    if why:
        st["phase"] = "refactor"
        return []
    u["refactor"] = "skipped"
    st["head_run"] = _next_head(_head_run(st), st["green_run"])   # 次の単位の頭の回（緑の木の回）
    st["cur"] += 1
    _next_unit(st, repo)
    return []


def _refactor(st, reply, repo) -> list:
    u = _cur(st)
    if not isinstance(reply.get("what"), str) or not reply["what"].strip():
        return ["what（何を整えたか。整える物が無ければそう書く）が要る"]
    moved = set(touched(repo, st["green_tree"], snapshot(repo))) - set(st["suite_made"])
    if moved:
        probs = _green(st, u, repo)
        if probs:
            return probs
        st["green_run"] = st["last_run"]
    u["refactor"] = "ok" if moved else "none"
    st["head_run"] = _next_head(_head_run(st), st.get("green_run"))   # 次の単位の頭の回（緑の木の回）
    st["cur"] += 1
    _next_unit(st, repo)
    return []


def _give_up(st, repo, probs):
    """段の RETRY_MAX 回目の拒否。test・fix の段は単位を止めて機械の申し出 1 件を返す（それ以外は None）"""
    head = f"{retry_max()} 回とも通らなかった: {probs[0][:200]}"
    u = _cur(st)
    if st["phase"] == "refactor":
        restore(repo, st["green_tree"])
        u.update(refactor="reverted", problems=probs[:10])
        st["head_run"] = _next_head(_head_run(st), st.get("green_run"))   # 緑の木に戻したので、次の単位の頭の回は緑の回
        st["cur"] += 1
        _next_unit(st, repo)
        return None
    stage = "red" if st["phase"] == "test" else "green"
    key = st["queue"][st["cur"]]
    why = f"{GAVE_UP_WHY}TDD の{'赤' if stage == 'red' else '緑'}の確認が " + head
    briefs = planbrief.by_unit_at(pathlib.Path(st["work"]).parent).get(key, [])   # 状態と作業ツリーを動かす前に読む（読めずに落ちても半端に残さない）
    item = {"unit_key": key, "between": [f"{b['file']}:1" for b in briefs], "why_both_cannot_hold": why,
            "which_is_right": conflict.UNKNOWN, "kind": conflict.NEEDS_CONTEXT}
    u.update(gave_up=stage, problems=probs[:10])
    _park_cur(st, repo, key, why)
    return item


def _abort(st, repo, why, stage) -> None:
    """残りの tdd の単位を全部 direct にして輪を抜ける（実行器が走らない・回数の上限。振り分けを諦めた時は src/route._abort）。
    実行器が走らない（stage runner）時は状態に no_suite の印を置き、修正役の輪を起こさずに組を止める（board.no_suite_stop・
    exit_fields。下書き 3.9 の止め方の 2）"""
    st["note"] = why
    if stage == "runner":
        st["no_suite"] = True
    u = _cur(st)
    if st["phase"] == "refactor":
        restore(repo, st["green_tree"])
        u["refactor"] = "reverted"
    else:
        restore(repo, st["unit_head"])
        _to_direct(u, stage, why)
    for k in st["queue"][st["cur"] + 1:]:
        _to_direct(st["units"][k], stage, why)
    st["done"] = True


def _conflict(st, reply, repo, try_query=None) -> tuple:
    """phase conflict（test・fix・refactor の段）: 名指しが現物に在れば拒否に数えず、作業ツリーを単位の頭に戻して次の単位へ（確かめは
    common.conflict_item。振り分けの段の申し出は route._conflict）。返り (問題, 申し出の 1 件)。盤面の控えに積むのは節 tdd-step"""
    probs, item = common.conflict_item(st, reply, repo, {st["queue"][st["cur"]]}, try_query)
    if probs:
        return probs, None
    _park_cur(st, repo, item["unit_key"], item["why_both_cannot_hold"])
    return [], item


def _park_cur(st, repo, key, why) -> None:
    """今の単位を食い違いの申し出で止める: 輪の状態に止めた単位と理由を積み、作業ツリーを単位の頭に戻して次の単位へ"""
    _mark_parked(st, key, why)
    restore(repo, st["unit_head"])
    _cur(st).update(route="parked", why=why)
    st["cur"] += 1
    _next_unit(st, repo)


def step(state_file, reply, repo, try_query=None, log=None) -> dict:
    """節 tdd-step。{ok（この返答を受けた）, done（輪を抜ける）, reason, phase（次の段）, writes（書き込みの出どころの突き合わせの
    結果。節が盤面の trace に積む）}。
    申し出でない返答は、前の段の後から変わったファイルを書き込みの記録と欄 bash_writes に突き合わせてから段を確かめる。
    輪を抜けた状態（済んだ）に返答 None（支度が go: false を返して役が飛ばされた周。resume）なら、何も動かさずに
    {ok: True, done: True, reason: "", phase}。返答が在れば今どおり Broken。
    log は書き込みの記録（既定は状態の置き場の writelog.LOG。記録を取る包みの無い run は無いので writes.NO_RECORD の知らせ）。
    止めた申し出は、保存と同じ 1 回の書き込みで状態の未送の並び UNSENT（行 {source, item}）に積む（止めた申し出の
    出口はこの 1 つ。盤面へ積むのは節 tdd-step が flush_unsent で。保存と積みの間で落ちても、次の呼びが積み直す）。
    前の段の印（handoff）は突き合わせを通った時と、機械が木を単位の頭に戻して次の単位へ移った時（申し出・諦め）だけ進める（拒まれた
    返答の出し直しや、振り分けの段の申し出で、記録の無い書き込みを流さない）"""
    st = _load(state_file)
    if reply is None and _over(st):   # 支度が go: false を返して役が飛ばされた周（resume）: 何も動かさずに輪を抜ける
        return {"ok": True, "done": True, "reason": "", "phase": "done"}
    if st["done"]:
        raise Broken("TDD のループは済んでいる（tdd-step を呼ぶ番でない）")
    phase = st["phase"]
    t0, runs0 = time.monotonic(), st["runs"]   # 段ごとの呼び出しの記録（calls）の元。秒は書くだけで止める条件に使わない
    call = {"n": st["iterations"] + 1,
            "phase": "conflict" if isinstance(reply, dict) and reply.get("phase") == "conflict" else phase,
            "unit_key": st["queue"][st["cur"]]}
    item = None
    source = conflict.TDD_SOURCE
    got = None
    if isinstance(reply, dict) and reply.get("phase") != "conflict":
        moved = sorted(set(touched(repo, st["handoff"], snapshot(repo))) - set(st["suite_made"]))
        got = writes.check(reply, repo, moved, pathlib.Path(st["work"]) / writelog.LOG if log is None else pathlib.Path(log))
        reply = got.pop("reply")
    if not isinstance(reply, dict):
        probs = ["返答が JSON のオブジェクトでない"]
    elif got and got["problems"]:
        probs = got["problems"]
    elif reply.get("phase") == "conflict":
        probs, item = _conflict(st, reply, repo, try_query)
    elif reply.get("phase") != phase:
        probs = [f"今の段は {phase}（返答の phase は {reply.get('phase')!r}）"]
    elif reply.get("unit_key") != st["queue"][st["cur"]]:
        probs = [f"今の単位は '{st['queue'][st['cur']]}'（返答の unit_key は {reply.get('unit_key')!r}）"]
    else:
        try:
            probs = {"test": _test, "fix": _fix, "refactor": _refactor}[phase](st, reply, repo)
        except _RunnerDown as e:
            _abort(st, repo, f"{e.head}: {e}", "runner")
            probs = [st["note"]]
            call["phase"] = "runner"   # 機械の止まり（役の拒否と分ける）
    if probs and not st["done"]:
        st["tries"] += 1
        st["reason"] = "\n".join(f"- {p}" for p in probs)
        if st["tries"] >= retry_max():
            item = _give_up(st, repo, probs)
            source = conflict.GAVE_UP_SOURCE
    st["iterations"] += 1
    if not st["done"] and st["iterations"] >= MAX_ITERATIONS:
        _abort(st, repo, f"TDD のループの回数の上限（{MAX_ITERATIONS} 回）に届いた", "budget")
    if st["done"]:
        _finish(st, repo)
    if got and not got["problems"]:   # 突き合わせを通った木だけ（機械が単位の頭に戻した木は _next_unit が進める）
        st["handoff"] = snapshot(repo)
    st.setdefault("calls", []).append({**call, "ok": not probs, "runs": st["runs"] - runs0,
                                       "secs": round(time.monotonic() - t0, 1)})
    if item is not None:
        st.setdefault(UNSENT, []).append({"source": source, "item": item})
    if st["done"]:
        _write_record(st)
    _save(state_file, st)
    return {"ok": not probs, "done": st["done"], "reason": "\n".join(probs), "phase": "done" if st["done"] else st["phase"],
            "writes": got}


RESULT_TITLE = "# TDD のループの結果（機械が書いた）"
FIXED_HEAD = ("## ループで直した単位（直さず、changes に 1 行を書け。テストのファイルは変えるな——受け付けが拒む。"
              "食い違いの裁定 fix_test_scope が範囲に並べた所だけは例外。修正案の rewrite_tests の名指しはループで書き換えて凍結した）")
CONFLICT_HEAD = "## 食い違いで止めた単位（直すな。ループの後に裁定役が裁き、裁定が理由のファイルで届く）"
OUT_HEAD = "## 直す義務から外れた単位（直すな。not_done に理由を書け）"
DIRECT_HEAD = "## direct の単位（ここで直せ）"

def _finish(st, repo) -> None:
    """輪の後の修正役へ渡す summary.md と、凍ったテストのファイルの控え（frozen）"""
    passed = [st["units"][k] for k in st["order"] if st["units"][k]["route"] == "tdd"]
    st["frozen"] = hashes(repo, sorted({f for u in passed for f in u["test_files"]}))
    st["frozen_tree"] = snapshot(repo)
    lines = [RESULT_TITLE, ""]
    if st["note"]:
        lines += [f"ループを途中で抜けた: {st['note']}", ""]
    lines += [FIXED_HEAD, ""]
    for u in passed:
        lines += [f"- {u['unit_key']}", f"  - 名指しのテスト（機械が赤→緑を確かめた）: {', '.join(u['tests'])}",
                  f"  - テストのファイル: {', '.join(u['test_files'])}", f"  - 直したファイル: {', '.join(u['files'])}",
                  f"  - 直し: {u['what']}",
                  f"  - 整え: {u['refactor']}" + (f"（{u['refactor_why']}）" if u.get("refactor_why") else "")]
    parked = st.get("parked", [])
    if parked:
        lines += ["", CONFLICT_HEAD, ""]
        lines += [f"- {k}: {st.get('parked_why', {}).get(k, '')}" for k in parked]
    if st.get("excused"):
        lines += ["", OUT_HEAD, ""]
        lines += [f"- {k}: {why}" for k, why in st["excused"].items()]
    lines += ["", DIRECT_HEAD, ""]
    lines += [f"- {st['units'][k]['unit_key']}: {st['units'][k]['why']}" for k in st["order"] if st["units"][k]["route"] == "direct"]
    (pathlib.Path(st["work"]) / SUMMARY).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_record(st) -> None:
    """輪が抜ける時に輪の記録 record.json を書く。輪を抜ける道（全部の単位が済んだ・回数の上限・実行器が走らない・振り分けを諦めた・
    tdd の単位が無い）は _finish を通り、step の終わり（最後の呼びの行と handoff を状態に積んだ後）と assign が呼ぶ"""
    _save(pathlib.Path(st["work"]) / RECORD, record(st))


RECORD_UNIT = {"route": "", "why": "", "tests": [], "test_files": [], "red": "", "green": "", "gave_up": "", "files": [],
               "red_tree": "", "test_hashes": {}}   # 記録の単位の行の欄と、その単位の状態に無い時の値（test_hashes は赤が通った単位にしか付かない）


def record(st) -> dict:
    """輪の記録 record.json の中身（形は schemas/tdd-record.schema.json）。輪が抜ける時の状態から、輪の外が読む欄だけを同じ名と形で写す:
    輪の全体の frozen・frozen_tree・handoff・suite_made・no_suite・note・done・calls と summary.md の在りか、組の結果の tdd の欄
    （exit_fields の order・parked・parked_why・suite・test_cmd_gate・test_cmd_note・reused・related）、単位ごと（order の単位）の
    RECORD_UNIT の欄。どの抜け方でも同じ形で書く（諦めた・direct の単位には test_hashes が無いので {} に揃える）"""
    units = {k: {f: json.loads(json.dumps(st["units"][k].get(f, default))) for f, default in RECORD_UNIT.items()} for k in st["order"]}
    return {"frozen": st["frozen"], "frozen_tree": st["frozen_tree"], "handoff": st["handoff"], "suite_made": list(st["suite_made"]),
            "no_suite": st.get("no_suite") is True, "note": st["note"], "done": True, "calls": list(st.get("calls") or []),
            "summary": str(pathlib.Path(st["work"]) / SUMMARY), "order": list(st["order"]), "parked": list(st.get("parked") or []),
            "parked_why": dict(st.get("parked_why") or {}), "suite": st["suite"], "test_cmd_gate": st.get("test_cmd_gate", GATE_OFF),
            "test_cmd_note": st.get("test_cmd_note", ""), "reused": dict(st.get("reused") or {}), "related": dict(st.get("related") or {}),
            "units": units}


def green_units(summary_file) -> set:
    """輪の要約 summary_file の隣の記録 record.json で、輪が緑にした単位（route が tdd・green が ok・諦めていない）の key。要約が空・記録が
    無い・読めない時は空（修正役の下請けを起こす単位を絞る節約の口なので、読めなくても止めず、全部の単位に下請けを起こす。
    依頼 243 の 2）"""
    if not summary_file:
        return set()
    try:
        st = _load(pathlib.Path(summary_file).parent / RECORD)
    except Broken:
        return set()
    units = st.get("units") if isinstance(st, dict) else None
    return {k for k, u in (units or {}).items()
            if isinstance(u, dict) and u.get("route") == "tdd" and u.get("green") == "ok" and not u.get("gave_up")}


FIELDS = ("unit_key", "route", "why", "tests", "test_files", "red", "green", "refactor", "gave_up", "problems", QUOTES_FIELD,
          "quote_unchecked", "stub_files", "test_cmd", "refactor_why")


def exit_fields(start_out: dict) -> dict:
    """出口の欄 tdd: {ran, suite, reason, units: [{unit_key, route, why, tests, test_files, red, green, refactor, gave_up, problems,
    red_quotes（名指しの id → {quote: 赤の時の失敗の文の引用, why: 理由}。引用は結末の failure の文に在ることを red_check が
    照らし済み）, quote_unchecked（failure の文もログも空で引用を照らせなかった名指し）, stub_files（test の段がテストでない
    ファイルに書いた仮の実装）, test_cmd（"ok"＝緑の後に run の test_cmd も走らせて通った・CMD_LIGHT＝軽量の単位
    なので走らせなかった・""）,
    refactor_why（整えの申告の理由）}]}。refactor は ""・skipped（申告が無く整えの段を飛ばした）・none・ok・reverted。
    ran: true の出口には test_cmd: {gate（GATE_ON・GATE_SAME・GATE_OFF）, note（off の理由）} と calls（step 1 回ごとの
    {n, phase, unit_key, ok, runs, secs}。役の費用は実行基盤の出来事に在り、この行の順（tdd の節の起動の順）で後から結べる）も載る。
    状態の reused（輪の頭で元の結末を控えから使い回した出どころの句 {suite}）が空でなければ載せる。組の頭・輪・受け付けが no-suite で
    止めた組は no_suite: true と、reason にその訳を載せる（下書き 3.9）"""
    if not isinstance(start_out, dict) or not start_out.get("go"):
        so = start_out if isinstance(start_out, dict) else {}
        out = {"ran": False, "suite": so.get("suite", ""), "reason": so.get("reason", ""), "units": []}
        if so.get("suite_broken") is True:   # 起動スクリプトが書き直しても壊れたまま（docs/design/fix.md の 19 節）。組の結末が止めを名乗る
            out.update(suite_broken=True, runner_log=so.get("runner_log", ""), cmd_log=so.get("cmd_log", ""))
        if so.get("no_suite") is True:   # 実行器が無い・走らない組（下書き 3.9）。組の結末が no-suite を名乗る
            out["no_suite"] = True
        return out
    st = _load(start_out["state_file"])
    if not st["done"]:
        raise Broken("TDD のループが済んでいない（done の印が無い）")
    rows = [{f: st["units"][k][f] for f in FIELDS} for k in st["order"]]
    rows += [{**{f: _unit(k, "parked")[f] for f in FIELDS}, "why": st.get("parked_why", {}).get(k, "")}
             for k in st.get("parked", []) if k not in st["order"]]   # 振り分けの段で止めた単位
    out = {"ran": True, "suite": st["suite"], "reason": st["note"], "units": rows,
           "test_cmd": {"gate": st.get("test_cmd_gate", GATE_OFF), "note": st.get("test_cmd_note", "")},
           "calls": st.get("calls", [])}
    if st.get("reused"):
        out["reused"] = st["reused"]
    if st.get("related", {}).get("applied"):
        out["related"] = st["related"]
    if st.get("no_suite") is True or start_out.get("no_suite") is True:   # 輪か受け付けが実行器の止まりで組を止めた（下書き 3.9）
        out.update(no_suite=True, reason=str(start_out.get("reason") or "") if start_out.get("no_suite") is True else st["note"])
    return out


def refused_units(calls) -> list:
    """出口の欄 calls（step 1 回ごとの {n, phase, unit_key, ok, …}）のうち、ok が偽で phase が runner（機械の止まり。役の拒否と
    分ける）でない物の unit_key（現れた順・重なりは 1 つ）。単位の名の無い拒否（振り分けの段。unit_key が空）は ROUTE_REFUSED で
    数える。calls が並びでなければ空。修正の後に深さを標準へ上げる信号（depth.late_signals の refused）の元"""
    out = []
    for c in calls if isinstance(calls, list) else []:
        if isinstance(c, dict) and c.get("ok") is False and c.get("phase") != "runner":
            name = c.get("unit_key") or ROUTE_REFUSED
            if isinstance(name, str) and name not in out:
                out.append(name)
    return out




# 型の義務（docs/plans/2026-10-24-fix-weapons.md の 2.4。表は src/duties.py）: 名指しの試験が単位の頭で赤になったことを輪の中で確かめた
# 記録がある（先に赤）。輪の中の test の段がこれを照らすので、受け付けの表には足す物が無い
BOX = "change"
DUTIES = ()
