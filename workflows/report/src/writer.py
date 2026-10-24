"""書き手のループと出口（docs/design/report.md の 1.5・2.8。lib/runreport.py の語の表・受け付け・人に向けた報告の組み立てと、
lib/report_roles.py の全部を、block の place で受ける形に写した物）。

- pack_terms()・plain_words(text)・swapped_line(counts)・glossary_section(text, terms): 語の表（glossary.json）による言い換えと語の定義
- accept(reply, cold, *, place) -> {done, ok, reason, kind, prev_file}: 書き手の返答と初見の読み手の判定の受け付け
- cold_parts(raw, *, place)・cold_body(raw, *, place): 初見の読み手に貼る本文（機械が組んだ行と書き手の頭に分けた物と、つないだ物）
- handoff_rounds(place): 前の周の引き継ぎのメモのパスの行
- collect(machine_text, *, place, stamp): 人に向けた報告と詳細のファイル
- stamp(run_id, workflow_file, rnd, line_rev, start_ok): 来歴の 1 行
- writer_fell は transcript にあり、note_writer_fell(machine, fell, *, run_id) がその訳を機械の報告の冒頭に置く
"""
import hashlib
import json
import os
import pathlib
import re

import answer     # lib/
import carry      # lib/
import handoff    # lib/。型 SCHEMA・欄の名 FIELD・控えの書き読み。文の定数は使わない
import jsonfile   # lib/
import oneline    # lib/
import rolekit    # lib/
from engine.schema import validate_schema   # lib/graphloops/engine/schema.py

from src import files

PACK_TERMS = pathlib.Path(__file__).resolve().parent / "glossary.json"

# ---------------------------------------------------------------- 定数
DECISIONS_HEAD = "人が決めること"
NOT_PASSED = "報告サブグラフの初見の読み手のノード cold が、この報告の頭を通さなかった"
MACHINE_ONLY = "初見の読み手が止まったのは機械が組んだ頭の行だけで、書き手には直せないので、書き直させずに受け取った"
MACHINE_LINE = "機械が組んだ行で止まった所（書き手には直せない）"
CELL_LIMIT = 50   # 表のセルの字数の上限（`コード` の部分を除く）。持ち主の決まり「セルには数語だけ」
MACHINE_HEADING = "## 機械が各段の出力と run の記録から組んだ事実（AI は書き換えていない）"
MACHINE_DECISIONS = "## 1. 人の判断を待つ物の機械の数え（判断の本文は報告の頭）"
FAILED_TITLE = "# 報告（AI の報告を最後まで作れなかった）"
GLOSSARY_HEADING = "## 語の定義（機械が付けた。本文の外）"
DETAIL_TITLE = "# 報告の詳しい中身（人に向けた報告から外した物。機械と、経緯を追う人のため）"
RAW_HEADING = "## 書き手の本文（字のまま。人に向けた報告では語の表で言い換えた）"
COLD_REJECTS_LINE = "- 初見の読み手の拒否（この周）:"
POINTER_LINE = "詳しい中身（書き手の本文の全部と、機械が組んだ事実——照らし・裏取り・数え直し・消したファイルなど）: 同じフォルダの {file}"
CUT_LINE = "（書き手の本文のここから先 {n} 行は {file} の「{heading}」に在る）"
SWAPPED_HEAD = "人に向けた報告で語の表（glossary.json）から言い換えた語と回数"
HEAD_LINES = 20            # 人が決める物の件数に依らない行（題・冒頭の 3 行・初見の読み手の 1 行・書き手の要約・語の定義・切った訳の 1 行・置き場の 1 行と来歴）
LINES_PER_DECISION = 8     # 人が決める物 1 件の行
WRITER_FELL = "AI が書く報告の本文は無い。書き手のノードが落ちた（{error}）。この機械の報告が報告の全部"
WRITER_QUOTA = ("。使用枠が切れて落ちたので、別のアカウントで run を resume すれば本文を書き直して報告に載せる"
                "（{command}。周の鎖が起こした run なら、この run でなく鎖の run を resume する）")
COLD_UNREADABLE = "初見の読み手の返答を読めない（判定の語が無い）"
COLD_EMPTY = "（止まった所・推測の欄が空）"
CELL_REASON = f"「。」を含むか {CELL_LIMIT} 字を超える表のセルが在る:\n"
# 拒否の種類: cold＝書き手の頭を読んだ初見の読み手が pass でない／format＝表のセル／answer＝返答の型・受け付けの拒否
REJECT_KINDS = ("cold", "format", "answer")
UNKNOWN_KIND = "unknown"   # 読むときだけの種類: kind の無い行・知らない kind の行を捨てずに数える先
REPORT_NODES = (files.ROLE,)
TERM_SCHEMA = {"type": "object", "required": ["term", "definition"], "additionalProperties": False,
               "properties": {"term": {"type": "string", "minLength": 1}, "definition": {"type": "string", "minLength": 1}}}
TEXT_SCHEMA = {"type": "object", "required": ["text", handoff.FIELD], "additionalProperties": False,
               "properties": {"text": {"type": "string", "minLength": 1},
                              "terms": {"type": "array", "items": TERM_SCHEMA},
                              handoff.FIELD: handoff.SCHEMA}}
# 初見の読み手の返答の型。型の正本は YAML の cold の output_format で、これと同じかを試験が縛る
# stops・guessed は書き手の頭の所、machine_lines は機械が組んだ行の所（書き手には直せない）
COLD_SCHEMA = {"type": "object", "required": ["verdict", "stops", "guessed", "machine_lines", "decidable"], "additionalProperties": False,
               "properties": {"verdict": {"type": "string", "enum": ["pass", "redesign-needed"]},
                              "stops": {"type": "array", "items": {"type": "string"}},
                              "guessed": {"type": "array", "items": {"type": "string"}},
                              "machine_lines": {"type": "array", "items": {"type": "string"}},
                              "decidable": {"type": "boolean"}}}


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v) -> list:
    return v if isinstance(v, list) else []


def write_text(path, text: str) -> pathlib.Path:
    """一時の名に書いて os.replace で一度に置く"""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- 語の表と語の定義
def pack_terms() -> list:
    """語の表（glossary.json の terms。記録の名 term と人に向けた言い方 plain の対）。無ければ空、在って読めなければ ValueError"""
    if not PACK_TERMS.is_file():
        return []
    try:
        rows = list(_dict(json.loads(PACK_TERMS.read_text(encoding="utf-8"))).get("terms") or [])
    except (OSError, ValueError) as e:
        raise ValueError(f"{PACK_TERMS} を読めない: {e}") from None
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("term"), str) and r["term"]
            and isinstance(r.get("plain"), str) and r["plain"]]


# 言い換えない所: コードの囲みと `…`（識別子とパス）・問いの key と答えの鍵（人が次の run の依頼の answers に字のまま写す）。
# 問いの key は判定の役が書く自由な 1 行なので、key の終わりは後ろの印「（kind・status」（英小文字の決まった語）の頭で決める
ASK_HEAD = "問いの台帳の問い"
ANSWER_KEY_HEAD = "答える時の answers の question"
KEPT_SPAN = re.compile(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)|`[^`\n]*`"
                       + "|(?<=" + re.escape(ASK_HEAD) + r" )[^\n]+?(?=（[a-z_]+・[a-z_]+[・）])"
                       + "|(?<=" + re.escape(ANSWER_KEY_HEAD) + r': )"(?:[^"\\\n]|\\.)*"', re.S)
KATAKANA = "ァ-ヺー"
KANJI = "一-鿿々"
OKURIGANA = {"周": "り"}   # 漢字 1 字の語が送り仮名を取って一般の語になる時の送り仮名


def _term_pattern(term: str) -> str:
    """語の表の語を当てる式。片仮名で始まる・終わる語は、続く片仮名語の一部には当てない。漢字 1 字の語は、熟語の一部（周囲・周知・一周）と
    送り仮名の付いた語（周り）には当てない"""
    if re.fullmatch(f"[{KANJI}]", term):
        return f"(?<![{KANJI}]){re.escape(term)}(?![{KANJI}{OKURIGANA.get(term, '')}])"
    head = f"(?<![{KATAKANA}])" if re.match(f"[{KATAKANA}]", term) else ""
    tail = f"(?![{KATAKANA}])" if re.search(f"[{KATAKANA}]$", term) else ""
    return head + re.escape(term) + tail


def plain_words(text: str, pack=None) -> tuple[str, dict]:
    """人に向けた文の、語の表の記録の名を人に向けた言い方に置き換えた字と、置き換えた語ごとの回数 {term: 回数}（長い語から当てる。
    KEPT_SPAN の所と、長い片仮名語の一部は置き換えない）"""
    text = str(text or "")
    rows = sorted(pack_terms() if pack is None else pack, key=lambda r: -len(r["term"]))
    if not rows:
        return text, {}
    to = {r["term"]: r["plain"] for r in rows}
    word = re.compile("|".join(_term_pattern(r["term"]) for r in rows))
    counts = {}

    def swap(m):
        counts[m.group(0)] = counts.get(m.group(0), 0) + 1
        return to[m.group(0)]

    out, at = [], 0
    for kept in KEPT_SPAN.finditer(text):
        out += [word.sub(swap, text[at:kept.start()]), kept.group(0)]
        at = kept.end()
    out.append(word.sub(swap, text[at:]))
    return "".join(out), counts


def swapped_line(counts: dict) -> str:
    """詳細のファイルに残す、人の報告で置き換えた語と回数の 1 行"""
    to = {r["term"]: r["plain"] for r in pack_terms()}
    return f"{SWAPPED_HEAD}: " + ("・".join(f"{t}→{to.get(t)} {n} 回" for t, n in counts.items()) or "無い")


def glossary_section(text, terms=()) -> str:
    """書き手の terms のうち text に現れる語だけを並べた語の定義のセクション。無ければ空の字"""
    seen, rows = set(), []
    for t in list(terms or []):
        term = t.get("term") if isinstance(t, dict) else None
        if not term or term in seen:
            continue
        seen.add(term)
        if term in str(text or ""):
            rows.append(f"- {term}: {t.get('definition')}")
    return f"{GLOSSARY_HEADING}\n\n" + "\n".join(rows) + "\n" if rows else ""


# ---------------------------------------------------------------- 書き手の返答の形
def terms_problems(reply) -> list:
    """書き手の返答の terms の欄の型の破れ（欄が無ければ空）"""
    if "terms" not in reply:
        return []
    return validate_schema(reply["terms"], TEXT_SCHEMA["properties"]["terms"], "$.terms")


def head_of(text) -> str:
    """報告の頭: 最初の見出し（## ）より前の冒頭と、見出しに『人が決めること』を持つセクション。見出しが無ければ全文"""
    head, keep, found = [], True, False
    for line in str(text or "").splitlines():
        if line.startswith("## "):
            found = True
            keep = DECISIONS_HEAD in line
        if keep:
            head.append(line)
    return "\n".join(head).strip() if found else str(text or "").strip()


def format_problems(text) -> list:
    """表のセルの書式の破れ（「。」を含むか CELL_LIMIT 字を超えるセル。`コード` の部分とコードの囲みの中は数えない）。1 行につき 1 つの文"""
    out, fence = [], False
    for i, line in enumerate(str(text or "").splitlines(), 1):
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = not fence
            continue
        if fence or not s.startswith("|"):
            continue
        body = re.sub(r"`[^`]*`", "", s).strip().strip("|")
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", body)]
        if all(re.fullmatch(r":?-{3,}:?", c) or not c for c in cells):
            continue
        bad = [c for c in cells if "。" in c or len(c) > CELL_LIMIT]
        if bad:
            out.append(f"{i} 行目のセル「{bad[0][:30]}{'…' if len(bad[0]) > 30 else ''}」（{len(bad[0])} 字）")
    return out


def count_rejects(rows) -> dict:
    """拒否の行の回数 {名: {種類: 回数}}（kind を数える。文は読まない）。kind の無い行・知らない kind の行は UNKNOWN_KIND に数え、
    REPORT_NODES の名でない行は数えない"""
    got = {name: dict.fromkeys((*REJECT_KINDS, UNKNOWN_KIND), 0) for name in REPORT_NODES}
    for r in rows:
        if r.get("node") in got:
            kind = r.get("kind") if r.get("kind") in REJECT_KINDS else UNKNOWN_KIND
            got[r["node"]][kind] += 1
    return got


# ---------------------------------------------------------------- 初見の読み手
def _parse(raw) -> tuple[dict | None, str]:
    if isinstance(raw, dict):
        return raw, ""
    try:
        got = json.loads(raw) if isinstance(raw, str) and raw.strip() else None
    except ValueError as e:
        return None, f"返答が JSON でない: {oneline.one_line(e)}"
    return (got, "") if isinstance(got, dict) else (None, "返答が JSON のオブジェクトでない")


def _cold_of(cold) -> dict:
    got, _ = _parse(cold)
    got = got or {}
    verdict = got.get("verdict") if got.get("verdict") in COLD_SCHEMA["properties"]["verdict"]["enum"] else ""
    return {"verdict": verdict, "stops": [str(s) for s in _list(got.get("stops"))],
            "guessed": [str(g) for g in _list(got.get("guessed"))],
            "machine_lines": [str(m) for m in _list(got.get("machine_lines"))], "decidable": got.get("decidable") is True}


def machine_only(c: dict) -> bool:
    """初見の読み手が通さなかった所が、機械が組んだ行だけか（書き手の頭に止まった所も推測も無い）。判定を読めなければ偽"""
    return c["verdict"] == "redesign-needed" and bool(c["machine_lines"]) and not (c["stops"] or c["guessed"])


def _cold_lines(c: dict) -> list[str]:
    """初見の読み手が通さなかった所（止まった所・推測で埋めた所）。判定を読めなければその事実の 1 つ"""
    if not c["verdict"]:
        return [COLD_UNREADABLE]
    return ([f"止まった所: {s}" for s in c["stops"]] + [f"推測で埋めた所: {g}" for g in c["guessed"]]
            + [f"{MACHINE_LINE}: {m}" for m in c["machine_lines"]])


def _cold_facts(c: dict) -> str:
    """通らなかった所の 1 行（ai.json の not_passed。報告の拒みの数の行の尾に出す）"""
    return oneline.one_line("；".join(_cold_lines(c)) or COLD_EMPTY)


def _cold_reason(c: dict) -> str:
    """書き手に返す拒みの文"""
    if not c["verdict"]:
        return COLD_UNREADABLE
    return ("初見の読み手（道具なし・報告の頭だけを読む）が redesign-needed を返した。通らなかった所:\n"
            + "\n".join(f"- {x}" for x in _cold_lines(c) or [COLD_EMPTY]))


def machine_head(machine_text: str) -> str:
    """機械の報告の冒頭（題・冒頭の 3 行・人が決める物の 1 件 1 行。最初のセクションの見出しより前）"""
    return str(machine_text or "").split("\n## ", 1)[0].strip()


def cold_parts(raw, *, place) -> tuple[str, str]:
    """初見の読み手に貼る本文を (機械が組んだ行, 書き手の頭) に分けた物。機械が組んだ行は機械の報告（place の report.md）の冒頭、書き手の頭は
    書き手の返答の頭（head_of）とその後ろに付く語の定義のセクション。どちらも語の表で言い換える。書き手の返答を読めなければ、機械が組んだ行は
    空で、書き手の頭の所に読めない事実"""
    got, why = _parse(raw)
    text = got.get("text") if got else None
    if not (isinstance(text, str) and text.strip()):
        return "", f"（書き手の返答を読めない: {why or '本文が無い'}）"
    terms = _list(got.get("terms")) if not terms_problems(got) else []
    try:
        machine = machine_head((pathlib.Path(place) / files.REPORT_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        machine = f"（機械の報告の冒頭を読めない: {type(e).__name__}）"
    head = head_of(text)
    sec = glossary_section(head, terms)
    writer = "\n\n".join(x.strip() for x in (head, sec) if x.strip())
    return plain_words(machine.strip())[0], plain_words(writer)[0]


def cold_body(raw, *, place) -> str:
    """初見の読み手に貼る本文をつないだ物（人に向けた報告の頭と同じ物）"""
    return "\n\n".join(x for x in cold_parts(raw, place=place) if x) + "\n"


# ---------------------------------------------------------------- 受け付け
def _refused(reason: str, kind: str) -> dict:
    return {"ok": False, "reason": reason, "kind": kind}


def _reject_count(place: pathlib.Path) -> dict:
    """拒否の控え（rolekit の rejects-report.json）の種類ごとの回数。控えが読めなければ空の控えとして数える"""
    try:
        rows = rolekit.reject_rows(place, files.ROLE)
    except (rolekit.BoardGap, OSError):
        rows = []
    return count_rejects([{**r, "node": files.ROLE} for r in rows])


def _give_up(refused: dict, what: str) -> dict:
    """拒否 refused に、前の周の引き継ぎのメモを次の周へ渡せない訳 what を足し、1 回目で諦めさせる（出し直させても直らない）"""
    return {**refused, "give_up": True, "reason": f"{refused['reason']}\n{what}"}


def prior_rounds(place: pathlib.Path, n: int) -> list:
    """輪の今の回 n（rolekit.attempt）の前までの周のフォルダ（古い順。フォルダがまだ無い周も含む）"""
    return [pathlib.Path(place) / files.NOTE_ROUND.format(n=i) for i in range(1, n)]


def _carry_rejected(place: pathlib.Path, reply: dict, refused: dict) -> dict:
    text = reply.get("text")
    if not isinstance(text, str) or not text.strip():
        return refused
    n, unusable = rolekit.current_round(place, files.ROLE)
    if unusable:
        return refused
    broken = handoff.unreadable(prior_rounds(place, n))
    if broken:
        return _give_up(refused, f"前の周の引き継ぎのメモ {'・'.join(str(p) for p in broken)} が読めないので、次の周へ渡せない")
    candidate = rolekit.candidate_path(place, files.ROLE)
    note = reply.get(handoff.FIELD)
    folder = place / files.NOTE_ROUND.format(n=n)
    try:
        jsonfile.write(candidate, {"text": text, "terms": _list(reply.get("terms"))}, indent=2)
    except OSError as e:
        return _give_up(refused, f"前の答えの控え {candidate} に書けない（{type(e).__name__}）ので、前の周の引き継ぎのメモを次の周へ渡せない")
    try:
        handoff.save(folder, note if isinstance(note, dict) else None)
    except OSError as e:
        return _give_up(refused, f"前の周の引き継ぎのメモ {handoff.path_of(folder)} に書けない（{type(e).__name__}）ので、次の周へ渡せない")
    return refused


def handoff_rounds(place) -> str:
    """前の周の引き継ぎのメモのパスの行（1 周 1 行 `- r<k>: <パス>`。メモの無い周は `(no notes)`、読めない周は `(unreadable)`）。
    前の周が無ければ空の字。今の回は rolekit.current_round で、拒否の控えが読めない時（回 0）も空の字"""
    place = pathlib.Path(place)
    n, _ = rolekit.current_round(place, files.ROLE)
    rounds = prior_rounds(place, n)
    broken = set(handoff.unreadable(rounds))
    lines = []
    for board in rounds:
        path = handoff.path_of(board)
        note = "(unreadable)" if path in broken else (str(path) if path.is_file() else "(no notes)")
        lines.append(f"- {board.name}: {note}")
    return "\n".join(lines)


def accept(reply, cold, *, place) -> dict:
    """書き手の返答を受け付ける。{done, ok, reason, kind, prev_file}。拒んだ回の返答の本文 text・terms は前の答えの控え
    rolekit.candidate_path(place, ROLE) に書き、まだ諦めていない拒否の回の prev_file がその絶対パスを指す（受け取った回・諦めた回・
    控えの無い回は空の字）。返答の handoff（読んだ所・保つと決めた事・脇に置いた案・まだ決まっていない所）は、その回の周のフォルダ
    place/r<n> に handoff.save で置く。handoff は ai.json にも初見の読み手に貼る本文にも載らない。前の周のメモが読めない時・控えに
    書けない時は、拒否に give_up を付けて1 回目で諦めさせる。順: 読む（読めない返答・本文の無い返答は kind answer）→ terms の型 →
    表のセルの書式 → 初見の読み手の判定。拒否が rolekit.GIVE_UP_AFTER 回に達した時か、控えが扱えない時は ai.json に受け取れなかった訳
    （accepted: False）を書く。初見の読み手だけが通さない時は rolekit.is_last_attempt の回に受け取り、NOT_PASSED の印を ai.json に残す。
    初見の読み手が止まったのが機械が組んだ行だけ（machine_only）なら、書き手には直せないので、どの回でも書き直させずに受け取って印を残す"""
    place = pathlib.Path(place)
    place.mkdir(parents=True, exist_ok=True)
    c = _cold_of(cold)

    def take(got: dict) -> dict:
        if not isinstance(got.get("text"), str) or not got["text"].strip():
            return _refused("返答に本文 text が無い", "answer")
        bad = terms_problems(got)
        if bad:
            return _refused("返答の terms の欄が型に合わない（各要素は空でない term と definition の 2 つだけ）:\n"
                            + "\n".join(f"- {x}" for x in bad), "answer")
        bad = format_problems(got["text"])
        if bad:
            return _refused(CELL_REASON + "\n".join(f"- {x}" for x in bad), "format")
        not_passed, why = "", ""
        if c["verdict"] != "pass":
            if machine_only(c):
                why = MACHINE_ONLY
            elif rolekit.is_last_attempt(rolekit.attempt(place, files.ROLE)):
                why = "上限の回なので受け取った"
            else:
                return _refused(_cold_reason(c), "cold")
            not_passed = _cold_facts(c)
        reason = f"{why}。ただし{NOT_PASSED}（機械の事実の拒みの数の行に出す）" if not_passed else ""
        return {"ok": True, "reason": reason, "text": got["text"], "terms": _list(got.get("terms")), "not_passed": not_passed,
                "machine_only": machine_only(c)}

    def kept(got: dict) -> dict:
        out = take(got)
        return out if out.get("ok") is True else _carry_rejected(place, got, out)

    out = rolekit.accept_round(place, files.ROLE, reply, kept, reject=lambda why: _refused(why, "answer"))
    if out["ok"]:
        carry.write(place / files.AI_FILE, {"accepted": True, "text": out["text"], "terms": out["terms"], "cold": c,
                                            "not_passed": out["not_passed"], "machine_only": out["machine_only"],
                                            "rejects": _reject_count(place)})
        return {"done": True, "ok": True, "reason": out["reason"], "kind": "", "prev_file": ""}
    if out["done"]:   # 諦めた時も、控えが扱えない時も、受け取れなかった訳を残す（出口が輪が落ちたと読まない）
        try:
            why = rolekit.given_up_reason(place, files.ROLE)
        except (rolekit.BoardGap, OSError):
            why = ""
        carry.write(place / files.AI_FILE, {"accepted": False, "reason": why or out["reason"], "cold": c, "rejects": _reject_count(place)})
    rolekit.reject_file_or_blank(place, files.ROLE)   # 拒否の全部の rejects-report.md（控えの読み物）
    candidate = rolekit.candidate_path(place, files.ROLE)
    return {"done": out["done"], "ok": False, "reason": out["reason"], "kind": out.get("kind") or "answer",
            "prev_file": str(candidate) if not out["done"] and candidate.is_file() else ""}


# ---------------------------------------------------------------- 出口
def note_writer_fell(machine, fell: dict | None, *, run_id: str) -> None:
    """機械の報告のファイル machine の冒頭の終わりに、書き手のループが落ちた訳 fell（transcript.writer_fell の返り）の 1 行を置く。
    前の周（resume の前）に置いた行は外す。fell が None なら外すだけで、何度呼んでも同じ"""
    path = pathlib.Path(machine)
    text = path.read_text(encoding="utf-8")
    head, sep, rest = text.partition("\n## ")
    mark = WRITER_FELL.partition("{error}")[0]
    kept = "\n".join(x for x in head.splitlines() if not x.startswith(mark)).rstrip()
    line = (WRITER_FELL.format(error=fell["error"]) + (WRITER_QUOTA.format(command=answer.resume(run_id)) if fell["quota"] else "")
            if fell else "")
    new = kept + (f"\n\n{line}" if line else "") + "\n" + (f"\n## {rest}" if sep else "")
    if new != text:
        write_text(path, new)


def stamp(run_id: str, workflow_file, rnd, line_rev: str, start_ok: bool) -> str:
    """報告の頭の来歴の 1 行（機械が刻む）: グラフの名（ファイルの名）・run・周（計画の何回目の案か。無ければ —）・グラフのファイルの sha256 の頭
    12 字・メイングラフの版（line_rev の頭 12 字）。グラフのファイルが読めなければグラフの版の所に、始めの記録が読めなければメイングラフの版の
    所にその旨。読めた記録に版が無ければ「無い」と分けて書く"""
    try:
        sha = hashlib.sha256(pathlib.Path(workflow_file).read_bytes()).hexdigest()[:12]
    except OSError as e:
        sha = f"読めない（{type(e).__name__}）"
    parts = [pathlib.Path(workflow_file).stem, f"run {run_id or '—'}", f"周 {rnd if rnd is not None else '—'}", f"グラフの版 {sha}"]
    if not start_ok:
        parts.append("メイングラフの版 読めない（始めの記録が読めない）")
    else:
        parts.append(f"メイングラフの版 {line_rev[:12]}" if line_rev else "メイングラフの版 始めの記録に無い")
    return " / ".join(parts)


def embedded(machine_text: str) -> str:
    """詳細のファイルに付ける機械の事実: 見出しを 1 段下げて機械の事実の見出しの下に入れ、機械の「人が決めること」の見出しを
    MACHINE_DECISIONS に言い換える（人が決めることのセクションは書き手の頭の 1 か所だけ）"""
    out = []
    for line in machine_text.splitlines():
        if line == files.DECISIONS_HEADING:
            line = MACHINE_DECISIONS
        out.append(f"#{line}" if line.startswith("#") else line)
    return "\n".join(out) + ("\n" if machine_text.endswith("\n") else "")


def _not_passed_note(ai: dict) -> str:
    """初見の読み手が通さないまま受け取った時の句（「。」で始まる。詳細のファイルの拒みの数の行の尾と、人に向けた報告の冒頭の 1 行。
    通っていれば空）"""
    if ai.get("accepted") is not True or not ai.get("not_passed"):
        return ""
    why = MACHINE_ONLY if ai.get("machine_only") is True else f"上限の {rolekit.GIVE_UP_AFTER} 回目で受け取った"
    return f"。{NOT_PASSED}（{why}。{oneline.one_line(ai['not_passed'])}）"


def line_budget(decisions: int) -> int:
    """人に向けた報告の行の上限: 件数に依らない HEAD_LINES と、人が決める物 1 件ごとの LINES_PER_DECISION"""
    return HEAD_LINES + LINES_PER_DECISION * decisions


def _fences(lines: list) -> list:
    return [x.strip()[:3] for x in lines if x.strip().startswith(("```", "~~~"))]


def _cut(block: str, room: int) -> str:
    """書き手の頭を room 行に切る（超えれば room - 1 行と、残りの行の置き場の 1 行。切った所がコードの囲みの中なら閉じる）"""
    lines = block.splitlines()
    if len(lines) <= room:
        return block
    shown = room - 1
    if len(_fences(lines[:shown])) % 2:
        shown -= 1
    opened = _fences(lines[:shown])
    kept = [*lines[:shown], *([opened[-1]] if len(opened) % 2 else [])]
    return "\n".join([*kept, CUT_LINE.format(n=len(lines) - shown, file=files.DETAIL_FILE, heading=RAW_HEADING.lstrip("# "))])


def collect(machine_text: str, *, place, stamp: str) -> pathlib.Path | None:
    """人に向けた報告（AI_REPORT_FILE）と詳細のファイル（DETAIL_FILE）を書き、人に向けた報告のパスを返す。ai.json が無ければ None
    （書き手のループが落ちた・飛ばされた）。
    人に向けた報告: 機械の報告の冒頭 → 初見の読み手が通さないまま受け取った時はその 1 行 → 書き手の頭（平易な要約と人が決めることの
    セクション）と、切った後に見えている頭に現れる語の定義 → 詳細のファイルを指す 1 行と来歴。来歴より前を語の表で言い換え、行は
    line_budget（人が決める物の件数）までに書き手の頭を切る。受け取れなかった時は書き手の頭の所に訳。
    詳細のファイル: 来歴・言い換えた語と回数の 1 行・書き手の本文の字のまま・語の定義・機械の事実（拒みの数の行と embedded）"""
    place = pathlib.Path(place)
    try:
        ai = json.loads((place / files.AI_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        ai = {"accepted": False, "reason": f"{files.AI_FILE} が読めない: {oneline.one_line(e)}"}
    ai = _dict(ai)
    if ai.get("accepted") is True:
        body = str(ai.get("text") or "").strip()
        writer = head_of(body)
    else:
        body = writer = f"{FAILED_TITLE}\n\n{ai.get('reason') or '書き手の返答を受け取れなかった'}"
    terms = ai.get("terms") or []
    note = _not_passed_note(ai)
    head = machine_head(machine_text)
    if note:
        head += f"\n{note.removeprefix('。')}"
    tail = f"{POINTER_LINE.format(file=files.DETAIL_FILE)}\n{stamp}"
    room = line_budget(sum(1 for x in head.splitlines() if x.startswith("- "))) - len(head.splitlines()) - len(tail.splitlines()) - 2
    held = glossary_section(writer, terms).rstrip()
    shown = _cut(writer, max(room - (len(held.splitlines()) + 1 if held else 0), 2))
    sec = glossary_section(shown, terms).rstrip()
    human, counts = plain_words("\n\n".join([head, shown + (f"\n\n{sec}" if sec else "")]))
    human += f"\n\n{tail}\n"
    colds = sum(c.get("cold", 0) for c in _dict(ai.get("rejects")).values() if isinstance(c, dict))
    whole = glossary_section(f"{body}\n{note}", terms)
    detail = (f"{stamp}\n\n{DETAIL_TITLE}\n\n- {swapped_line(counts)}\n\n{RAW_HEADING}\n\n{body}\n\n"
              + (f"{whole}\n" if whole else "")
              + f"---\n\n{MACHINE_HEADING}\n\n{COLD_REJECTS_LINE} {colds} 回{note}\n\n{embedded(machine_text)}")
    write_text(place / files.DETAIL_FILE, detail)
    return write_text(place / files.AI_REPORT_FILE, human)
