"""元から赤の区別: テスト一式を走らせて 1 件ごとの結末（JUnit XML）を読み、元の結末と比べる道具と、元の結末のファイルの口。

今の works（版 2aa7c66cf7abe1fe09699ac2942d107123214168）の `works/.shared/core/graphloops/rules/review-loop-tdd.py`
と `works/blk-fix/lib/tddloop.py` の関数を、元の名のまま字のとおり写した物（各関数の docstring の末尾に元の `<パス>:<行>`）。
run_suite だけは元の試験の枠（tree_run.slotted_run の枠）を外し、tree_run.reuse_run で走らせる（優先度は lowered が 1 か所で下げる）。
元の結末のファイルの口（write_baseline・read_baseline・outcomes・test_outcomes）は新しい関数。

元の結末のファイルの必須の欄: {"suite": str, "test_cmd": str, "rev": str, "exit": int | None, "cases": [{classname, name, outcome（OUTCOMES の語）, …}]}。
ほかの欄は呼び手だけが読む（extra）。
"""
import json
import os
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ET

import tree_run

# 実行器への合図（env）: 1 なら後ろに足した試験（ファイル・node id）だけを走らせてよい（既定の一式を集めない）。輪の赤・緑の回だけが
# 付ける（元の結末・受け付け・版の写しは付けない）。解かない実行器は無視してよい（一式に足して走らせても確かめは同じ）
# 元 works/blk-fix/lib/tddloop.py:142-144
ONLY_ENV = "TDD_SUITE_ONLY"

# 起こす子の優先度（実行器と run の test_cmd と test-gate の宣言の試験。同じ機械で別の run も動くので nice -n 19 と同じだけ下げる）。
# 下げる口は lowered の 1 か所。元 works/blk-fix/lib/tddloop.py:307（実行器は argv の頭の nice）・works/.shared/core/entry.py:680
# _nice19（test_cmd は preexec で同じだけ下げた）
NICENESS = 19
NO_NICE = "（この環境では優先度を下げられない——nice -n 19 と同じだけ下げずに起こした）"   # 下げずに起こした回にログへ書く 1 行

REQUIRED = ("suite", "test_cmd", "rev", "exit", "cases")
# cases の行の outcome の語（parse_junit の出す 4 つ）と、そのうちの落ちた物。元の結末のファイルはこの語だけを持つ
OUTCOMES = ("passed", "failure", "error", "skipped")
FAILED = ("failure", "error")


# ---------------------------------------------------------------- テスト一式を走らせて結末を読む
def parse_junit(text):
    """JUnit XML → [{classname, name, outcome}]。outcome は passed / failure / error / skipped。読めなければ ET.ParseError
    （元 works/.shared/core/graphloops/rules/review-loop-tdd.py:41-49）"""
    root = ET.fromstring(text)
    cases = []
    for tc in root.iter("testcase"):
        kinds = [c.tag for c in tc if c.tag in ("failure", "error", "skipped")]
        outcome = "error" if "error" in kinds else "failure" if "failure" in kinds else "skipped" if "skipped" in kinds else "passed"
        cases.append({"classname": tc.get("classname") or "", "name": tc.get("name") or "", "outcome": outcome})
    return cases


def _id_parts(test_id):
    """『path/test_x.py::Class::test_y』→（[path, test_x, Class], test_y）。JUnit の classname は実行器の根で頭が変わるので、
    後ろ側の一致で引く（元 works/.shared/core/graphloops/rules/review-loop-tdd.py:52-57）"""
    parts = test_id.split("::")
    head = list(pathlib.PurePosixPath(parts[0]).with_suffix("").parts) + parts[1:-1]
    return head, parts[-1]


def match_case(test_id, cases):
    """名指しの 1 件に当たる JUnit の行（無ければ None）。名前が同じで、classname と識別子の頭の短い方が長い方の末尾
    （元 works/.shared/core/graphloops/rules/review-loop-tdd.py:60-68）"""
    head, name = _id_parts(test_id)
    for c in cases:
        cls = [x for x in c["classname"].split(".") if x]
        n = min(len(cls), len(head))
        if c["name"] == name and n and cls[-n:] == head[-n:]:
            return c
    return None


def _key(c):
    """元の結末の鍵 `classname::name`（元 works/.shared/core/graphloops/rules/review-loop-tdd.py:92-93）"""
    return f"{c['classname']}::{c['name']}"


def _must_pass(c, baseline):
    """名指しの外で通っていなければならないテストか——元の結末で通っていた物と、元に無かった物（この周に足した名指しの外）。
    元から落ちていた・飛ばされていた物は問わない（周の頭で赤い一式でも、TDD の確認が必ず落ちる形にしない）
    （元 works/.shared/core/graphloops/rules/review-loop-tdd.py:96-99）"""
    return baseline is None or baseline.get(_key(c), "passed") == "passed"


def _broken_others(cases, baseline, hit, scope=None):
    """名指しの外（hit に無い）で落ちた、通っていなければならないテスト（_must_pass）——赤と緑の確認が同じ 1 本を読む
    （元 works/.shared/core/graphloops/rules/review-loop-tdd.py:102-104）"""
    return [c for c in cases if id(c) not in hit and c["outcome"] in ("failure", "error") and _must_pass(c, baseline)
            and (scope is None or _key(c) in scope)]


def red_problems(named, cases, exit_code, baseline=None):
    """赤の確認: 名指しのテストが全部 failure で落ち、名指しの外で通っていなければならない物（_must_pass）は通る。
    一式は 0 以外で終わる（名指しが落ちたのに 0 を返す実行器は結末を映していない）。baseline＝元の結末（_key → outcome）
    （元 works/.shared/core/graphloops/rules/review-loop-tdd.py:107-129）"""
    probs, hit = [], set()
    if not named:
        probs.append("名指しのテストが無い")
    if exit_code == 0:
        probs.append("テスト一式が exit 0 で終わった——名指しのテストが落ちたなら 0 にはならない（実行器が結末を映していない）")
    for t in named:
        c = match_case(t, cases)
        if c is None:
            probs.append(f"{t}: 一式の結末に居ない——読み込み（import・構文）で落ちたか、名指しが実行器の識別子と違う")
            continue
        hit.add(id(c))
        if c["outcome"] == "error":
            probs.append(f"{t}: error で落ちた——読み込みの失敗・準備の例外は狙いどおりの赤でない（テストの中の検査で落とせ）")
        elif c["outcome"] == "passed":
            probs.append(f"{t}: もう通る——直す前に赤でないテストは修正の証拠にならない")
        elif c["outcome"] == "skipped":
            probs.append(f"{t}: 飛ばされた——赤でも緑でもない")
    probs += [f"名指しの外の {_key(c)} が {c['outcome']}——テストだけを書く段がほかを壊した（元は通っていた・この周に足した物は緑のまま）"
              for c in _broken_others(cases, baseline, hit)]
    return probs


def green_problems(named, cases, exit_code, baseline=None, baseline_exit=0, narrow=False, also=()):
    """緑の確認: 名指しのテストが全部通り、名指しの外で通っていなければならない物（_must_pass）も通る。一式が 0 で終わる
    （JUnit に載らない失敗——件数の柵など——も拾う）。元の一式が 0 で終わっていなかったなら終了コードは問わない
    narrow が真（元の結末が変更に関わる試験だけで、今の回は全部の試験を走らせた。持ち主の決め related-tests-only）なら、比べるのは元の結末に
    載った試験と名指しと also（前の単位が赤から緑にした試験の id）だけ: 元の結末に無い試験の赤は問わず、一式の終了コードも、その範囲の結果が
    全部通っていれば問わない
    （元 works/.shared/core/graphloops/rules/review-loop-tdd.py:132-147）"""
    scope = None
    if narrow and baseline is not None:
        scope = {_key(c) for c in cases if _key(c) in baseline or any(match_case(t, [c]) for t in (*named, *also))}
    clean = scope is not None and not any(c["outcome"] in ("failure", "error") for c in cases if _key(c) in scope)
    probs = [] if exit_code == 0 or baseline_exit != 0 or clean else [
        f"テスト一式が exit {exit_code} で終わった——JUnit の結末が全部通っていても、一式としては緑でない"]
    hit = set()
    for t in named:
        c = match_case(t, cases)
        if c is not None:
            hit.add(id(c))
        if c is None or c["outcome"] != "passed":
            probs.append(f"{t}: {'一式の結末に居ない' if c is None else c['outcome']}——名指しのテストが緑でない")
    probs += [f"{_key(c)} が {c['outcome']}——ほかのテストが緑でない（元は通っていた・この周に足した物）"
              for c in _broken_others(cases, baseline, hit, scope)]
    return probs


def nice19() -> None:
    """子の中で exec の前に呼ぶ（Popen の preexec_fn）: nice -n 19 と同じだけ優先度を下げる（元 works/.shared/core/entry.py:680-682 の
    _nice19）。下げるのは努めるだけ: 親が既に一番低い優先度で動いている（nice -n 19 の下の macOS など）か OS が下げるのを拒めば
    （os.nice の OSError。PermissionError を含む）、下げずにそのまま子を起こす。ほかの誤りは握らない"""
    try:
        os.nice(NICENESS)
    except OSError:
        pass


def lowered() -> tuple[dict, str]:
    """起こす子の優先度を下げる Popen の引数と、下げない訳（下げたら空）。実行器（run_suite）・run の test_cmd（tddloop._cmd_material）・
    test-gate の宣言の試験（declared_checks.local_checks_material の niced）の起こし口がここを引く。argv・環境・作業の場は変えない
    ので、起こせるかの証明（tree_run.run の prove_launchable）は走らせる時と同じ環境・作業の場・起こし方のまま行われる（argv の頭に
    nice を付けると証明が nice を見て通り、bash -c の中の起こせない語が exit 127 の赤やパイプの後ろの緑に化ける）。os.nice の無い
    環境（層の E14: 普通の利用者の機械）は {} と NO_NICE（呼び手がログに 1 行書く）"""
    if getattr(os, "nice", None) is None:
        return {}, NO_NICE
    return {"preexec_fn": nice19}, ""


def exe_path(repo, suite: str) -> pathlib.Path:
    """入力 tdd_suite の実行器のパス（相対なら作業ツリー repo の根から解く。ファイル名だけの名を PATH で探させない）"""
    return pathlib.Path(suite) if pathlib.Path(suite).is_absolute() else pathlib.Path(repo) / suite


def run_suite(exe: str, repo, work: pathlib.Path, n, args=(), only=False, reuse=None, note=None):
    """実行器を 1 回走らせる ——（結末の一覧, 終了コード, 問題）。結末が取れなければ一覧は None。相対の exe は repo の根から解く（exe_path）。
    .py はこの Python で走らせる（写しの rules の run_suite と同じ）。出力は work/suite-<n>.log に丸ごと。
    args は JUnit の書き先の後ろに足す（段の外の試験のファイル・node id を絶対パスで・受け付けの -k。works/dev/tdd-suite.sh は
    試験の実行器に渡し、試験の根（conftest.py の置き場）が違う名指しは根ごとに別のプロセスで流して JUnit を 1 つに合わせる）。同じ鍵の行は 1 つにまとめる（段のファイルと足した node id が重なっても 1 件）。
    only なら env に合図 ONLY_ENV=1 を付ける（後ろの試験だけでよい。輪の赤・緑の回）。付けない回は外の env の合図も落とす。
    優先度は nice -n 19 と同じだけ下げる（lowered。下げられない環境は下げずに起こし、ログの頭に NO_NICE の 1 行）。
    reuse（tree_run.reuse_place の返り）を渡した呼びは、同じ run の中で同じ木・同じ引数の緑の回を控えから使い回して子を起こさない
    （JUnit XML は書き戻す）。note（dict）を渡せば、呼び手が出どころ（reused）と理由（reuse_off）を読める。
    （元 works/blk-fix/lib/tddloop.py:296-333。試験の枠（slotted_run の枠・待った秒）を外し、tree_run.reuse_run で
    自分のプロセスグループで走らせる。使い回しの句はログでなく note に置く。rules().parse_junit は同じファイルの parse_junit）"""
    argv = ([sys.executable] if exe.endswith(".py") else []) + [str(exe_path(repo, exe))]
    nice_kw, bare = lowered()
    junit = work / f"junit-{n}.xml"
    log = work / f"suite-{n}.log"
    env = {k: v for k, v in tree_run.outside_env(os.environ).items() if k != ONLY_ENV}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", **({ONLY_ENV: "1"} if only else {})})
    with open(log, "wb") as out:
        if bare:
            out.write(f"{bare}\n".encode("utf-8"))
            out.flush()
        try:
            rc = tree_run.reuse_run([*argv, str(junit), *args], env, place=reuse, outputs=(junit,), note=note,
                                    stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, cwd=str(repo), **nice_kw)
        except OSError as e:
            return None, None, [f"テストの実行器を起こせない（{type(e).__name__}: {e}。ログ {log}）"]
    if not junit.is_file():
        return None, rc, [f"テストの実行器が JUnit XML を書かなかった（exit {rc}。ログ {log}）"]
    try:
        text = junit.read_text(encoding="utf-8", errors="replace")
        cases = parse_junit(text)
        fails = _failure_attrs(text)
    except Exception as e:   # ET.ParseError（写しの rules の中の型）
        return None, rc, [f"JUnit XML が読めない（{e}。ログ {log}）"]
    finally:
        junit.unlink(missing_ok=True)
    return _unique([{**c, **fails.get(_key(c), NO_FAILURE)} for c in cases]), rc, []


# 元 works/blk-fix/lib/tddloop.py:336
NO_FAILURE = {"fail_message": "", "fail_text": ""}


def _failure_attrs(text: str) -> dict:
    """JUnit XML の testcase の鍵（_key）→ {fail_message, fail_text}（failure の子の message の属性と本文。同じ鍵は最初の行。
    failure の子の無い行は載せない）。写しの parse_junit は属性を返さないので、同じ XML を ElementTree で読み直す（failure の
    文を読む所はここ 1 か所）（元 works/blk-fix/lib/tddloop.py:339-349）"""
    out = {}
    for tc in ET.fromstring(text).iter("testcase"):
        f = tc.find("failure")
        if f is not None:
            out.setdefault(_key({"classname": tc.get("classname") or "", "name": tc.get("name") or ""}),
                           {"fail_message": f.get("message") or "", "fail_text": f.text or ""})
    return out


def _unique(cases) -> list:
    """同じ鍵の行を最初の 1 つにまとめる（名指しの写しを red_problems が名指しの外と数えない）（元 works/blk-fix/lib/tddloop.py:449-452）"""
    seen = set()
    return [c for c in cases if not (_key(c) in seen or seen.add(_key(c)))]


# ---------------------------------------------------------------- 元の結末のファイル
def outcomes(cases) -> dict:
    """結末の並び → {_key: outcome}（同じ鍵は最初の 1 つ）。red_problems・green_problems・_must_pass の baseline の形（新しい関数）"""
    out = {}
    for c in cases:
        out.setdefault(_key(c), c["outcome"])
    return out


def test_outcomes(baseline_cases, cases) -> list:
    """テストごとの元の結末と今の結末 [{key, base, final, fail_message}]（元の結末の順、今にだけ居るテストはその後ろに今の順。片側に
    居なければその側は ""。fail_message は今が赤なら今の物、でなければ元の物。新しい関数）"""
    base = {_key(c): c for c in _unique(baseline_cases)}
    now = {_key(c): c for c in _unique(cases)}
    rows = []
    for key in [*base, *(k for k in now if k not in base)]:
        b, f = base.get(key), now.get(key)
        red = f if f and f["outcome"] in FAILED else b
        rows.append({"key": key, "base": b["outcome"] if b else "", "final": f["outcome"] if f else "",
                     "fail_message": (red or {}).get("fail_message") or ""})
    return rows


def _problems(doc) -> list:
    """元の結末の dict の必須の欄の欠けと型の違い（欄の名を載せた文の並び。無ければ空）"""
    if not isinstance(doc, dict):
        return [f"JSON の object でない（{type(doc).__name__}）"]
    probs = [f"欄 {k} が無い" for k in REQUIRED if k not in doc]
    for k in ("suite", "test_cmd", "rev"):
        if k in doc and not isinstance(doc[k], str):
            probs.append(f"欄 {k} が文字列でない（{type(doc[k]).__name__}）")
    if "exit" in doc and doc["exit"] is not None and (isinstance(doc["exit"], bool) or not isinstance(doc["exit"], int)):
        probs.append(f"欄 exit が整数か null でない（{type(doc['exit']).__name__}）")
    if "cases" in doc:
        rows = doc["cases"]
        if not isinstance(rows, list):
            probs.append(f"欄 cases が並びでない（{type(rows).__name__}）")
        else:
            bad = [i for i, c in enumerate(rows)
                   if not isinstance(c, dict) or not all(isinstance(c.get(f), str) for f in ("classname", "name", "outcome"))]
            if bad:
                probs.append(f"欄 cases の行 {bad[:5]} に classname・name・outcome の文字列が揃わない")
            unknown = [i for i, c in enumerate(rows)
                       if i not in bad and c["outcome"] not in OUTCOMES]
            if unknown:
                probs.append(f"欄 cases の行 {unknown[:5]} の outcome が {'・'.join(OUTCOMES)} のどれでもない")
    return probs


def write_baseline(path, *, suite, test_cmd, rev, exit, cases, **extra) -> None:
    """元の結末を path に JSON で書く。必須の欄は suite（実行器の実行ファイルのパスか ""）・test_cmd・rev（書いた時の HEAD の sha）・
    exit（cases を取った一式の終了コード。走らなければ None）・cases（parse_junit の並びの形。_unique で同じ鍵は最初の 1 つ）。
    extra は呼び手だけが読む欄で、そのまま書く。必須の欄の型が違えば書かずに ValueError（新しい関数）"""
    doc = {"suite": suite, "test_cmd": test_cmd, "rev": rev, "exit": exit,
           "cases": _unique(cases) if isinstance(cases, list) else cases, **extra}
    probs = _problems(doc)
    if probs:
        raise ValueError(f"元の結末を書けない（{path}）: {'；'.join(probs)}")
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def read_baseline(path) -> dict:
    """元の結末のファイルを読み、必須の欄が在り型が合えば dict を返す（extra の欄もそのまま）。無い・読めない・欄が欠けた・
    型が違えば ValueError（文にパスと欠けた欄）（新しい関数）"""
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"元の結末が読めない（{path}）: {type(e).__name__}: {e}") from e
    probs = _problems(doc)
    if probs:
        raise ValueError(f"元の結末の形が違う（{path}）: {'；'.join(probs)}")
    return doc
