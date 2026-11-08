"""報告の頭の機械の行の文面表（docs/design/report.md の 1.8）。頭の行の文は、このモジュールの表 TABLE と NOTICES の 1 か所だけが持つ。

頭は初見の読み手が頭だけを読んで止まる所なので、機械は自由な字を頭に連結しない。行は「行の種 Line（知らせは Notice）の文」に、種ごとの
型の決まった差し込み口 SLOTS の値だけを入れて描く。差し込み口に入れてよいのは読み手の世界の値（件数・run の id・URL・PR の番号・ログのパス・
試験のコマンドの最初の語・結末の語・人の一言の引用や人が決める物の題）だけで、上流の字（人の一言・物の題）は 1 行に畳んだ字の型
OneLine でだけ受ける（字数の上限は置かない）。AI や段が書いた長い訳は頭に入れず、機械の報告の節「2. 止めたか」（書き手の誤りは注意の節）に置く。

- SLOT_TYPES: 差し込み口に許す型の全部
- Line・Notice: 頭の行の種・知らせの種の列挙（値は表の鍵。Notice の値は facts の共通の形 facts.schema.json の kind の enum と同じ）
- TABLE・NOTICES: 種 → 文（`{名}` が差し込み口）。SLOTS: 種 → 差し込み口の型（NamedTuple）
- PR_STOPPED_OF: 差分を当ててよいかの答えの行 → 出口の語 pr の道で PR を作る前に止めた run の同じ答えの行（文は答えの前に PR_STOPPED を足した物）
- render(line, slots) -> str・notice_row(kind, slots) -> str: 行を描く。種でない鍵や、型に合わない差し込み口の値は TypeError（既定の文に黙って落とさない）
- slots_of(kind, values) -> 差し込み口: facts の JSON の slots を型の付いた値に直す。形が違えば ValueError
- parse(text) -> Row | None: 頭の 1 行を表の行に読み戻す（描いた字と同じ字になる行だけ。表の外の行は None）
- NOTICE_TOPIC: 知らせの種 → 節「2. 止めたか」で本文 text の前に付ける見出しの句
"""
import enum
import re
import string
import typing

import oneline    # lib/
import report     # lib/
import suitewrite  # lib/
import userenv    # lib/


# ---------------------------------------------------------------- 差し込み口の型
class OneLine(str):
    """上流の字（人の一言の引用・人が決める物の題）を 1 行に畳んだ字。字数の上限は置かない"""

    def __new__(cls, text):
        return super().__new__(cls, oneline.one_line(text))


class RunId(str):
    """run の id"""


class Url(str):
    """URL"""


class LogPath(str):
    """ログのパス"""


class CmdWord(str):
    """試験のコマンドの最初の語"""


class Command(str):
    """人が打つ命令"""


class GroupId(str):
    """修正の段の組の id"""


Outcome = enum.Enum("Outcome", {word: word for word in report.OUTCOMES}, type=str)   # 結末の語。文は lib/report.py の OUTCOME_WORDS


class Handover(str, enum.Enum):
    """受け渡しの形。対象の既定の枝へ当てたかの言い方を決める（文は HANDOVER_WORDS）"""
    PR = "pr"
    STOPPED = "stopped"
    UNCONFIRMED = "unconfirmed"
    NONE = "none"


HANDOVER_WORDS = {Handover.PR: "PR を作っただけで、対象の既定の枝には当てていない", Handover.STOPPED: "PR は作らず、対象の既定の枝には当てていない",
                  Handover.UNCONFIRMED: "PR を作ったかは確かめられていないが、対象の既定の枝には当てていない",
                  Handover.NONE: "対象のリポジトリには何も当てていない"}


SLOT_TYPES = (int, OneLine, RunId, Url, LogPath, CmdWord, Command, GroupId, Outcome, Handover)   # 差し込み口に許す型の全部（読み手の世界の値だけ）


class Plain(typing.NamedTuple):
    """差し込み口の無い行"""


class RunSlot(typing.NamedTuple):
    run: RunId


class OutcomeSlot(typing.NamedTuple):
    outcome: Outcome


class OutcomeAsksSlot(typing.NamedTuple):
    outcome: Outcome
    n: int


class CountSlot(typing.NamedTuple):
    n: int


class DecideApplySlot(typing.NamedTuple):
    n: int
    run: RunId


class CheckApplySlot(typing.NamedTuple):
    outcome: Outcome
    run: RunId


class PrSlot(typing.NamedTuple):
    url: Url
    number: int


class UrgentSlot(typing.NamedTuple):
    handover: Handover


class UrgentEndSlot(typing.NamedTuple):
    outcome: Outcome
    handover: Handover


class TitledSlot(typing.NamedTuple):
    title: OneLine
    kind: OneLine


class KindSlot(typing.NamedTuple):
    kind: OneLine


class KindCountSlot(typing.NamedTuple):
    kind: OneLine
    n: int


class QuotaSlot(typing.NamedTuple):
    command: Command


class QuoteSlot(typing.NamedTuple):
    quote: OneLine


class CmdSlot(typing.NamedTuple):
    cmd: CmdWord


class GroupSlot(typing.NamedTuple):
    group: GroupId


class BrokenSlot(typing.NamedTuple):
    group: GroupId
    runner_log: LogPath
    cmd_log: LogPath


# ---------------------------------------------------------------- 行の種
class Line(str, enum.Enum):
    RUN_TITLE = "title"
    WHAT_HAPPENED = "happened"
    HAPPENED_WITH_ASKS = "happened_with_asks"
    APPLY_NO_DIFF = "apply_no_diff"
    APPLY_REFUSED = "apply_refused"
    APPLY_DECIDE_FIRST = "apply_decide_first"
    APPLY_DECIDE_FIRST_STOPPED = "apply_decide_first_stopped"
    APPLY_NOT_PLACED = "apply_not_placed"
    APPLY_OK = "apply_ok"
    APPLY_CHECK_FIRST = "apply_check_first"
    APPLY_PR = "apply_pr"
    APPLY_PR_DRAFT = "apply_pr_draft"
    APPLY_PR_STOPPED_NO_DIFF = "apply_pr_stopped_no_diff"
    APPLY_PR_STOPPED_REFUSED = "apply_pr_stopped_refused"
    APPLY_PR_STOPPED_DECIDE_FIRST = "apply_pr_stopped_decide_first"
    APPLY_PR_STOPPED_DECIDE_FIRST_STOPPED = "apply_pr_stopped_decide_first_stopped"
    APPLY_PR_STOPPED_NOT_PLACED = "apply_pr_stopped_not_placed"
    APPLY_PR_STOPPED_OK = "apply_pr_stopped_ok"
    APPLY_PR_STOPPED_CHECK_FIRST = "apply_pr_stopped_check_first"
    APPLY_PR_UNCONFIRMED = "apply_pr_unconfirmed"
    URGENT_FAILED = "urgent_failed"
    URGENT_RECORD = "urgent_record"
    URGENT_NEITHER = "urgent_neither"
    DECIDE = "decide"
    NEXT_RUN = "next_run"
    ASK_TITLED = "ask_titled"
    ASK_KIND = "ask_kind"
    ASK_KIND_COUNT = "ask_kind_count"
    WRITER_FELL_OTHER = "writer_fell"
    WRITER_FELL_QUOTA = "writer_fell_quota"


class Notice(str, enum.Enum):
    START_REFUSED = "start_refused"
    ANSWER_REDIRECTED = "answer_redirected"
    BASE_GATE_STOPPED = "base_gate_stopped"
    SUITE_BROKEN = "suite_broken"
    NO_SUITE = "no_suite"
    TESTS_NOT_RUN = "tests_not_run"
    SUITE_USED = "suite_used"
    SUITE_WROTE = "suite_wrote"
    SUITE_NOT_MADE = "suite_not_made"
    USER_ENV = "user_env"
    TEST_CMD_NOTE = "test_cmd_note"


# ---------------------------------------------------------------- 文面表
_APPLY = "差分を当ててよいか: "
_STOPPED_FLAG = "（--allow-stopped は止まった run の差分を当てる指定）"
_INFO = "知らせ（決めることではない）: "
PR_STOPPED = "PR を作らずに止めた。対象の既定の枝には当てていない。"   # 出口の語 pr の道で PR を作る前に止めた run の答えの前に足す句
_FELL = "AI が書く報告の本文は無い。書き手の段が"

TABLE = {
    Line.RUN_TITLE: "# 報告（run {run}）",
    Line.WHAT_HAPPENED: "起きたこと: {outcome}",
    Line.HAPPENED_WITH_ASKS: "起きたこと: {outcome}。人が決めること {n} 件が残っている",
    Line.APPLY_NO_DIFF: _APPLY + "当てる差分が無い（この run は差分を確定していない）",
    Line.APPLY_REFUSED: _APPLY + "当てない。修正に関わっていない AI の見直しが「作り直しが要る」と言った run の差分は、bin/apply でも当てない",
    Line.APPLY_DECIDE_FIRST: _APPLY + "人が決めること {n} 件を決めてから当てる。当てる命令: bin/apply {run}",
    Line.APPLY_DECIDE_FIRST_STOPPED: (_APPLY + "人が決めること {n} 件を決めてから当てる。差分を置かずに止まった run なので、当てる命令: bin/apply {run} --allow-stopped"
                                      + _STOPPED_FLAG),
    Line.APPLY_NOT_PLACED: (_APPLY + "差分を置かずに止まった run。止めた訳を確かめてから当てる。当てる命令: bin/apply {run} --allow-stopped"
                            + _STOPPED_FLAG),
    Line.APPLY_OK: _APPLY + "当ててよい。当てる命令: bin/apply {run}",
    Line.APPLY_CHECK_FIRST: _APPLY + "確かめてから当てる。この run の結末: {outcome}。当てる命令: bin/apply {run}",
    Line.APPLY_PR: _APPLY + "PR を作った: {url}（PR #{number}。merge は対象のレビューと決まりに任せる）",
    Line.APPLY_PR_DRAFT: _APPLY + "PR を作った: {url}（下書きの PR #{number}。merge は対象のレビューと決まりに任せる）",
    Line.APPLY_PR_UNCONFIRMED: _APPLY + "PR を作ったと確かめられなかった。対象の既定の枝には当てていない。差分を手元で当てる命令: bin/apply {run}",
    Line.URGENT_FAILED: "急ぎ: 壊れた所がある。この run の段が落ちた。{handover}",
    Line.URGENT_RECORD: "急ぎ: 壊れた所がある。この run の結末: {outcome}。{handover}",
    Line.URGENT_NEITHER: "急ぎ: この run の段はどれも落ちていない。試験の外で対象が動くかは、機械は確かめていない。{handover}",
    Line.DECIDE: "人が決めること: {n} 件（下の行は種類ごと。題のある物は 1 件ずつ）",
    Line.NEXT_RUN: "次の run に渡す物: {n} 件",
    Line.ASK_TITLED: "- {title}（{kind}）",
    Line.ASK_KIND: "- {kind}",
    Line.ASK_KIND_COUNT: "- {kind}（{n} 件）",
    Line.WRITER_FELL_OTHER: _FELL + "使用枠の切れ以外の誤りで落ちた。resume しても直るとは限らない。この機械の報告が報告の全部",
    Line.WRITER_FELL_QUOTA: (_FELL + "使用枠の切れで落ちた。別のアカウントで run を resume すれば本文を書き直して報告に載せる"
                             "（別の run が続けて起こした run なら、この run でなくその大元の run を resume する）。resume の命令: {command}。"
                             "この機械の報告が報告の全部"),
}

NOTICES = {
    Notice.START_REFUSED: _INFO + "run を始める前に入力が断られた。AI は起こしておらず、対象には何も当てていない。断られた入力を直して起こし直す",
    Notice.ANSWER_REDIRECTED: (_INFO + "修正の前の承認での人の一言「{quote}」が、計画と違う向きだったので、修正の前で止めた。"
                               "下書きの一言を見直し、その向きで計画し直す依頼にするか、計画どおりなら continue と書いて回し直す"),
    Notice.BASE_GATE_STOPPED: (_INFO + "直す前の試験の関門が止めた。試験のコマンド「{cmd}」で、直す前の試験の結果を確かめられなかったので、判定は起こしていない。"
                               "試験のコマンドが走る環境にして起こし直す"),
    Notice.SUITE_BROKEN: (_INFO + "修正の段が止まった（組 {group}）。試験の起動スクリプトが、書き直しても壊れたままだった。"
                          "起動スクリプトのログ: {runner_log}。試験のコマンドだけを走らせたログ: {cmd_log}。2 つのログを見比べて、どちらが壊れているかを確かめる"),
    Notice.NO_SUITE: (_INFO + "修正の段が止まった（組 {group}）。試験の実行器が無いか、走らない。"
                      "実行器を直すか、JUnit XML を第 1 引数に書く実行器を入力 tdd_suite に渡して起こし直す"),
    Notice.TESTS_NOT_RUN: _INFO + "最後のテストが走っていないか、走ったと確かめられていない。緑と読まず、手元で試験を走らせて確かめる",
    Notice.SUITE_USED: _INFO + suitewrite.USED,
    Notice.SUITE_WROTE: _INFO + suitewrite.WROTE,
    Notice.SUITE_NOT_MADE: _INFO + suitewrite.NOT_MADE + "。" + suitewrite.NO_LOOP,
    Notice.USER_ENV: _INFO + userenv.NOTE,
    Notice.TEST_CMD_NOTE: _INFO + "試験のコマンドに注意が在る。試験が直しでなく手元のコードを試し、緑でも直しの確かめにならないことがある",
}

# 知らせの本文 text（返りの訳を 1 行に畳んだ字）を節「2. 止めたか」に置く時の頭の句。本文の無い種（利用者の環境）は置かない
NOTICE_TOPIC = {
    Notice.START_REFUSED: "入口が入力を断った訳", Notice.ANSWER_REDIRECTED: "修正の前の一言が計画と違う向きだった訳",
    Notice.BASE_GATE_STOPPED: "直す前の試験の関門が止めた訳", Notice.SUITE_BROKEN: "試験の起動スクリプトが壊れたままだった訳",
    Notice.NO_SUITE: "試験の実行器が無い訳", Notice.TESTS_NOT_RUN: "最後のテストが走っていない訳",
    Notice.SUITE_USED: "TDD の実行器の状態", Notice.SUITE_WROTE: "TDD の実行器の状態", Notice.SUITE_NOT_MADE: "TDD の実行器の状態",
    Notice.USER_ENV: "利用者の環境で走らせた", Notice.TEST_CMD_NOTE: "試験のコマンドの注意",
}
# 出口の語 pr の道で PR を作る前に止めた run の行: PR の道でない run と同じ答え（差分が無い・作り直しが要るので当てない・決めてから当てる・
# --allow-stopped つき…）の行の前に PR_STOPPED を足す。答えの分かれは PR の道でない行と同じ 1 か所（report の machine._apply_row）が選ぶ
PR_STOPPED_OF = {Line.APPLY_NO_DIFF: Line.APPLY_PR_STOPPED_NO_DIFF, Line.APPLY_REFUSED: Line.APPLY_PR_STOPPED_REFUSED,
                 Line.APPLY_DECIDE_FIRST: Line.APPLY_PR_STOPPED_DECIDE_FIRST,
                 Line.APPLY_DECIDE_FIRST_STOPPED: Line.APPLY_PR_STOPPED_DECIDE_FIRST_STOPPED,
                 Line.APPLY_NOT_PLACED: Line.APPLY_PR_STOPPED_NOT_PLACED, Line.APPLY_OK: Line.APPLY_PR_STOPPED_OK,
                 Line.APPLY_CHECK_FIRST: Line.APPLY_PR_STOPPED_CHECK_FIRST}
TABLE.update({stopped: _APPLY + PR_STOPPED + TABLE[base].removeprefix(_APPLY) for base, stopped in PR_STOPPED_OF.items()})

SLOTS = {
    Line.RUN_TITLE: RunSlot, Line.WHAT_HAPPENED: OutcomeSlot, Line.HAPPENED_WITH_ASKS: OutcomeAsksSlot, Line.APPLY_NO_DIFF: Plain,
    Line.APPLY_REFUSED: Plain, Line.APPLY_DECIDE_FIRST: DecideApplySlot, Line.APPLY_DECIDE_FIRST_STOPPED: DecideApplySlot,
    Line.APPLY_NOT_PLACED: RunSlot, Line.APPLY_OK: RunSlot, Line.APPLY_CHECK_FIRST: CheckApplySlot, Line.APPLY_PR: PrSlot,
    Line.APPLY_PR_DRAFT: PrSlot, Line.APPLY_PR_UNCONFIRMED: RunSlot, Line.URGENT_FAILED: UrgentSlot,
    Line.URGENT_RECORD: UrgentEndSlot, Line.URGENT_NEITHER: UrgentSlot, Line.DECIDE: CountSlot, Line.NEXT_RUN: CountSlot,
    Line.ASK_TITLED: TitledSlot, Line.ASK_KIND: KindSlot, Line.ASK_KIND_COUNT: KindCountSlot, Line.WRITER_FELL_OTHER: Plain,
    Line.WRITER_FELL_QUOTA: QuotaSlot,
    Notice.START_REFUSED: Plain, Notice.ANSWER_REDIRECTED: QuoteSlot, Notice.BASE_GATE_STOPPED: CmdSlot, Notice.SUITE_BROKEN: BrokenSlot,
    Notice.NO_SUITE: GroupSlot, Notice.TESTS_NOT_RUN: Plain, Notice.SUITE_USED: Plain, Notice.SUITE_WROTE: Plain,
    Notice.SUITE_NOT_MADE: Plain, Notice.USER_ENV: Plain, Notice.TEST_CMD_NOTE: Plain,
}
SLOTS.update({stopped: SLOTS[base] for base, stopped in PR_STOPPED_OF.items()})   # PR を作る前に止めた行の差し込み口は、同じ答えの行と同じ


# ---------------------------------------------------------------- 描く
def _fits(value, kind) -> bool:
    if kind is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, kind)


def _text(value) -> str:
    """差し込み口の値の字。結末の語と受け渡しの形は、表の言い方に直す"""
    if isinstance(value, Outcome):
        return report.OUTCOME_WORDS[value.value]
    if isinstance(value, Handover):
        return HANDOVER_WORDS[value]
    return str(value)


def _fill(table: dict, key_type: type, key, slots) -> str:
    if not isinstance(key, key_type) or key not in table:
        raise TypeError(f"{key!r} は {key_type.__name__} の値でない（文面表に無い鍵）")
    shape = SLOTS[key]
    if slots is None and not shape._fields:
        slots = shape()
    if not isinstance(slots, shape):
        raise TypeError(f"{key.value} の差し込み口は {shape.__name__} の値でなければならない（{type(slots).__name__}）")
    for name, kind in shape.__annotations__.items():
        if not _fits(getattr(slots, name), kind):
            raise TypeError(f"{key.value} の差し込み口 {name} は {kind.__name__} の値でなければならない"
                            f"（{type(getattr(slots, name)).__name__}）")
    return table[key].format_map({name: _text(getattr(slots, name)) for name in shape._fields})


def render(line, slots=None) -> str:
    """頭の行の種 line の文に差し込み口の値 slots を入れた 1 行。種でない鍵・型に合わない値は TypeError"""
    return _fill(TABLE, Line, line, slots)


def notice_row(kind, slots=None) -> str:
    """知らせの種 kind の文に差し込み口の値 slots を入れた 1 行。種でない鍵・型に合わない値は TypeError"""
    return _fill(NOTICES, Notice, kind, slots)


# ---------------------------------------------------------------- facts の JSON から
def slots_of(kind, values) -> tuple:
    """facts の知らせの slots（名 → 値の object）を、種 kind の差し込み口の型の値に。欄の過不足・型の違い・結末の語でない字は ValueError"""
    shape = SLOTS[kind]
    if not isinstance(values, dict):
        raise ValueError(f"{kind.value} の slots が object でない（{type(values).__name__}）")
    if set(values) != set(shape._fields):
        raise ValueError(f"{kind.value} の slots の欄が {list(shape._fields)} でない（{sorted(values)}）")
    got = {}
    for name, ann in shape.__annotations__.items():
        value = values[name]
        if ann is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{kind.value} の slots.{name} が整数でない")
        elif not isinstance(value, str):
            raise ValueError(f"{kind.value} の slots.{name} が字でない")
        got[name] = _typed(ann, value)
    return shape(**got)


def _typed(ann, value):
    if ann is int:
        return value
    if ann in (Outcome, Handover):
        try:
            return ann(value)
        except ValueError:
            raise ValueError(f"{value!r} は {ann.__name__} の語でない") from None
    return ann(value)


# ---------------------------------------------------------------- 読み戻す
class Row(typing.NamedTuple):
    """parse が読み戻した頭の行: 表の鍵（Line か Notice）と、その種の差し込み口の値（SLOTS の型）"""
    kind: typing.Any
    slots: tuple


def _regex(template: str) -> tuple[re.Pattern, int]:
    pattern, fixed = "", 0
    for literal, name, _, _ in string.Formatter().parse(template):
        pattern += re.escape(literal) + (f"(?P<{name}>.+?)" if name else "")
        fixed += len(literal)
    return re.compile(pattern), fixed


_PATTERNS = [(kind, *_regex(table[kind])) for table in (TABLE, NOTICES) for kind in table]


def _from_text(ann, text: str):
    if ann is int:
        if not text.isdigit():
            raise ValueError(text)
        return int(text)
    if ann is Outcome:
        return Outcome(next(word for word, said in report.OUTCOME_WORDS.items() if said == text))
    if ann is Handover:
        return next(h for h, said in HANDOVER_WORDS.items() if said == text)
    return ann(text)


def parse(text) -> Row | None:
    """頭の 1 行を表の行 (種, 差し込み口の値) に読み戻す。描いた字（render・notice_row）と同じ字になる行だけが読め、表の外の行は None。
    当たる表の行が複数なら、決まった字が一番長い行"""
    best = None
    for kind, pattern, fixed in _PATTERNS:
        found = pattern.fullmatch(str(text))
        if not found:
            continue
        shape = SLOTS[kind]
        try:
            slots = shape(**{name: _from_text(ann, found.group(name)) for name, ann in shape.__annotations__.items()})
            same = (render if isinstance(kind, Line) else notice_row)(kind, slots) == text
        except (ValueError, StopIteration, TypeError):
            continue
        if same and (best is None or fixed > best[0]):
            best = (fixed, Row(kind, slots))
    return best[1] if best else None
