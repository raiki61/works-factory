# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出口の語 pr の commit の node pr-commit。照らした差分を run の作業ツリーの枝へ、修正案の項目（1 つの論理の変更）ごとの commit に積み、
PR を作る子の run に渡す枝を返す。

積む前に止める（go: false と訳。何も積まない）: 本体の作業ツリーか切り離された HEAD（lib/runbranch.py）・run の枝の名が対象の既定の
枝（origin の HEAD が指す枝）と同じ・既定の枝を読めない・origin の URL から PR を出す repo を決められない・今の差分の hash が封じた
hash と違う。
分け方は lib/itemcommits.py の split: 修正の段の記録（入力 items。単位ごとの触ったファイルと承認済みの項目）で差分のパスを項目に
決め、依存（depends_on）の位相順に 1 項目 1 commit で積む。決められない時（記録が無い・読めない、どの項目も申告していないか複数の
項目が触ったパスが在る）は 1 つの commit に倒し、訳を split に返して commit の文にも書く。項目ごとの commit のどれかで hooks が
落ちた時も（runbranch.commit_parts が積み始める前の HEAD に戻す）、最後の木で hooks が通れば届くように 1 つの commit に積み直し、
何本目で落ちたかと hooks の言葉を split に返す。各 commit の時点で試験が通るかは確かめない（確かめるのは積み終えた木の差分の hash
だけ）。
commit（項目ごとの各 commit と、1 つに積み直す commit）は対象の commit の hooks を飛ばさずに走らせ、1 つの commit で hooks が落ちれば
go: false と hooks の言葉（積み始める前の HEAD に戻し、積まない）。hooks は対象のコマンドなので、git commit を対象のコマンドの環境
（tree_run.outside_env）と印の置き場（入力 user_env_dir）で起こす。git commit 自身も利用者の HOME・XDG で走るので、走る hooks は
利用者の大域の git の設定（core.hooksPath など）で決まり、利用者自身の commit と同じ形になる。git add・git diff など積む前後の git は
節の環境のまま。印は積む変更が在る時だけ、最初の commit の前に置き（tree_run.split_mark・place_mark）、置けなければ積まずに止める
（積む変更が無い回は置かない）。git が落ちた回は hooks が走ったかを口から見分けられないので、印は残す側に倒す。RECORD の形が違う・
RECORD が在るのに印の置き場が空なら、積まずに go: false。push の hooks（pre-push）は pr-open の archon-pr が工場の環境で走らせ、
この節の外にある。
積んだ後に、差分の根から積んだ最後の commit までの差分の hash を封じた hash と照らし、違えば go: false（積んだ commit は run の
枝に残るが、push はされない）。作業ツリーに変更が無く、封じた差分が既に枝の commit に在る時は積まずに進む。push・PR の作成はこの節でしない。
commit の文が PR を作る子の run への渡し物（子の run には枝しか入力で渡せないので）: 項目の commit の題は項目の番号と approach の
頭、本文は approach・依存する前の項目・積んだパス。最後の commit（1 つに倒した時はその 1 つ）の本文に、照らしの要約・封じた hash・
run の id・報告の在りか（報告は merge の後に書かれるので、run の id から組める在りかだけ）・向け先の既定の枝・項目と commit の対
（PR の本文に載せる物）か 1 つに倒した訳・依頼が名指した issue（閉じない参照）を書く。
出力の branch・base・repo（origin の {host, path}）は、PR を作る子の run の入力と読み戻しの照らしに使う。commits は積んだ項目の
commit の並び [{item, subject, head}]（1 つに倒した・積まなかった時は []）、split は 1 つに倒した・積まなかった訳（分けたら空）。
落ちない: どの誤りも go: false と訳を返す。

入力: mode（照らしの形。apply か check）・base_rev（差分の根の版）・sealed_hash（封じた差分の sha256）・request（依頼のファイルのパス。
相対なら対象の根から。空は無し）・items（修正の段の記録 itemcommits.merged の形。空は無し）・
user_env_dir（利用者の HOME・XDG に戻した印を置く置き場の絶対パス。空は置き場が無い）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

try:
    import entryshape
    import forge
    import green_cert
    import itemcommits
    import oneline
    import runbranch
    import seal
    import tree_run
    unread = None
except Exception as error:   # lib/ を読めなくても落ちない（go: false と訳を返す）
    unread = error

CHECKED = {
    "apply": "最後の承認ノードの後に、封じた差分の hash・修正の後のテストの緑の認証・独立の確かめ・守りのパスの当たりを照らして通った",
    "check": "封じた差分の hash を今の差分と照らして通った（テストと確かめは差分を作った所で済んだ）",
}
SKIP = (ports.RUNTIME_COPY_PREFIX,)
SUBJECT_WIDTH = 60   # 項目の commit の題に載せる approach の頭の字数
UNCHECKED = "各 commit の時点で試験が通るかは確かめていない（確かめたのは、積み終えた木の差分の hash が封じた hash と同じこと）"
NOTHING = "作業ツリーに積む変更が無い（封じた差分は既に枝の commit に在る）"


def stopped(reason: str) -> dict:
    return {"go": False, "head": "", "branch": "", "base": "", "repo": None, "commits": [], "split": "", "reason": reason}


def handoff(mode: str, run_id: str, sealed: str, name: str, base: str) -> list:
    return [f"照らし（merge の {mode}）: {CHECKED[mode]}",
            f"封じた差分の sha256: {sealed}",
            f"run: {run_id}",
            f"報告: run {run_id} の報告（merge の後に書かれる。workflow get {run_id} の出力の report が指す）",
            f"向け先: 対象の既定の枝 {base}（この枝 {name} から）"]


def message(mode: str, run_id: str, sealed: str, name: str, base: str, issues: list, split: str) -> str:
    lines = [f"works-factory の run {run_id} が照らした差分", "", *handoff(mode, run_id, sealed, name, base),
             f"1 つの commit にまとめた訳: {split}"]
    lines += [f"Refs #{n}" for n in issues]
    return "\n".join(lines) + "\n"


def subject(part) -> str:
    head = oneline.one_line(part.approach)
    return f"項目 {part.item}: " + (head if len(head) <= SUBJECT_WIDTH else head[:SUBJECT_WIDTH] + "…")


def item_message(parts: list, i: int, heads: list, run_id: str, tail: list, issues: list) -> str:
    """i 本目の項目の commit の文（頭の注記）。heads は前に積んだ commit、tail は最後の commit に載せる照らしの要約"""
    part = parts[i]
    lines = [subject(part), "", oneline.one_line(part.approach), "",
             f"works-factory の run {run_id} が照らした差分のうち、修正案の項目 {part.item}（{i + 1}/{len(parts)} 本目）"]
    if part.after:
        lines.append(f"依存: {'・'.join(f'項目 {n}' for n in part.after)} に依存する（この枝の前の commit に在る）")
    lines.append(f"積んだパス: {'・'.join(part.paths)}")
    if i == len(parts) - 1:
        pairs = [f"- 項目 {p.item}: {h}（{subject(p)}）" for p, h in zip(parts, heads)]
        lines += ["", *tail, "項目と commit の対（PR の本文に載せる）:", *pairs, f"- 項目 {part.item}: この commit（{subject(part)}）",
                  UNCHECKED, *(f"Refs #{n}" for n in issues)]
    return "\n".join(lines) + "\n"


def stack(repo: Path, record, hook_env, mode: str, run_id: str, sealed: str, name: str, base: str, issues: list) -> tuple:
    """今の変更を積む: (積んだ項目の commit の並び, 1 つに倒した・積まなかった訳)。git の誤りは runbranch.GitFailed のまま。
    hook_env() は積む変更が在る時だけ 1 度呼び、hooks を走らせる commit の環境を返す（印を置く）"""
    paths = runbranch.staged(repo, ports.RUNTIME_COPY)
    if not paths:
        return [], NOTHING
    env = hook_env()
    parts, split = itemcommits.split(record, paths)
    if parts:
        tail = handoff(mode, run_id, sealed, name, base)
        try:
            heads = runbranch.commit_parts(repo, [p.paths for p in parts],
                                           lambda i, done: item_message(parts, i, done, run_id, tail, issues), env)
            return [{"item": p.item, "subject": subject(p), "head": h} for p, h in zip(parts, heads)], ""
        except runbranch.PartFailed as error:
            split = f"項目ごとの {error.index + 1} 本目で hooks が落ちた: {error}"
    runbranch.commit(repo, message(mode, run_id, sealed, name, base, issues, split), ports.RUNTIME_COPY, hook_env=env)
    return [], split


def origin_repo(repo: Path):
    try:
        got = forge.repo_of(runbranch.git(repo, "config", "--get", f"remote.{runbranch.ORIGIN}.url"))
    except runbranch.GitFailed:
        return None
    return None if got is None else {"host": got["host"], "path": f"{got['owner']}/{got['name']}"}


def request_path(raw) -> str:
    """依頼のファイルのパス。空・読めない・無いファイルは空（依頼が名指した issue を引けなくても止めない）。形の違う依頼は ShapeError"""
    try:
        path = ports.file(raw, "json(shared:request.schema.json)")
    except ports.ShapeError:
        raise   # 形の違う依頼は読めない依頼と分けて名指す（黙って依頼の無い run にしない）
    except ValueError:
        return ""
    return "" if path is None else str(path)


def item_record(raw):
    """修正の段の記録。空と null は無し。読めない記録は字のまま渡し、itemcommits.split が 1 つの commit に倒す"""
    try:
        return ports.json(raw, "items.schema.json") if ports.text(raw).strip() not in ("", "null") else None
    except ports.ShapeError:
        raise   # 機械が組んだ記録の形の外れは工場の不具合（読めない記録の 1 つの commit の道に倒さない）
    except ValueError:
        return ports.text(raw)


def commit() -> dict:
    if unread is not None:
        raise unread
    repo = Path.cwd()
    run_id = os.environ["WORKFLOW_ID"]
    mode = ports.text(os.environ.get("INPUTS_MODE"))
    base_rev = ports.text(os.environ.get("INPUTS_BASE_REV"))
    sealed = ports.text(os.environ.get("INPUTS_SEALED_HASH"))
    if mode not in CHECKED:
        return stopped(f"照らしの形 {mode!r} は {' か '.join(CHECKED)} でない（照らした差分しか積まない）")
    if not base_rev:
        return stopped("差分の根 base_rev が無い")
    name, base, reason = runbranch.pr_branches(repo, runbranch.ORIGIN)
    if reason:
        return stopped(reason)
    target = origin_repo(repo)
    if target is None:
        return stopped(f"{runbranch.ORIGIN} の URL から PR を出す repo（host と owner/name）を決められない")
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_bytes(repo, base_rev, skip=SKIP)))
    if why:
        return stopped(f"{why}（commit しない）")
    _, issues = entryshape.named({"request": request_path(os.environ.get("INPUTS_REQUEST"))}, repo)
    record = item_record(os.environ.get("INPUTS_ITEMS"))
    ports.drop_runner_env(os.environ.get("INPUTS_USER_ENV_DIR", ""))   # 入力を読み終えた。hooks に Archon の変数を継がせない
    env, mark = tree_run.split_mark(tree_run.outside_env(os.environ))

    def hook_env() -> dict:
        if mark is not None:
            tree_run.place_mark(mark)
        return env

    try:
        commits, split = stack(repo, record, hook_env, mode, run_id, sealed, name, base, issues)
        head = runbranch.git(repo, "rev-parse", "HEAD")
    except OSError as error:   # 印を置けない（tree_run.MARK_FAILED）
        return stopped(f"{error}（積まない・push しない）")
    except runbranch.GitFailed as error:
        return stopped(f"commit が通らなかった（対象の commit の hooks が落ちたか）: {error}（積まない・push しない）")
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_between(repo, base_rev, head, skip=SKIP)))
    if why:
        return stopped(f"積んだ commit {head} の差分が封じた差分と違う: {why}（push しない）")
    return {"go": True, "head": head, "branch": name, "base": base, "repo": target, "commits": commits, "split": split, "reason": ""}


ports.run(commit, stopped)
