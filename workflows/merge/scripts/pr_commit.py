# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出口の語 pr の commit の節 pr-commit。照らした差分を run の作業ツリーの枝へ、修正案の項目（1 つの論理の変更）ごとの commit に積み、
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
commit は対象の commit の hooks を飛ばさずに走らせ（hooks は対象のコマンドなので、PATH の頭に読むだけの gh の口を置く。
lib/userenv.py の read_gh_first）、1 つの commit で hooks が落ちれば go: false と hooks の言葉（積み始める前の HEAD に戻し、積まない）。
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
相対なら対象の根から。空は無し）・items（修正の段の記録 itemcommits.merged の形。空は無し）
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 返す節が結ぶので落ちない（上の docstring）
    boundary, unread = None, error

if boundary is not None:
    with boundary.guarded_imports():
        import entryshape
        import forge
        import green_cert
        import itemcommits
        import oneline
        import runbranch
        import seal
        import userenv

CHECKED = {
    "apply": "最後の承認ノードの後に、封じた差分の hash・修正の後のテストの緑の認証・独立の確かめ・守りのパスの当たりを照らして通った",
    "check": "封じた差分の hash を今の差分と照らして通った（テストと確かめは差分を作った所で済んだ）",
}
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


def stack(repo: Path, record, mode: str, run_id: str, sealed: str, name: str, base: str, issues: list) -> tuple:
    """今の変更を積む: (積んだ項目の commit の並び, 1 つに倒した・積まなかった訳)。git の誤りは runbranch.GitFailed のまま"""
    paths = runbranch.staged(repo, boundary.RUNTIME_COPY)
    if not paths:
        return [], NOTHING
    parts, split = itemcommits.split(record, paths)
    if parts:
        tail = handoff(mode, run_id, sealed, name, base)
        try:
            heads = runbranch.commit_parts(repo, [p.paths for p in parts],
                                           lambda i, done: item_message(parts, i, done, run_id, tail, issues), hook_env())
            return [{"item": p.item, "subject": subject(p), "head": h} for p, h in zip(parts, heads)], ""
        except runbranch.PartFailed as error:
            split = f"項目ごとの {error.index + 1} 本目で hooks が落ちた: {error}"
    runbranch.commit(repo, message(mode, run_id, sealed, name, base, issues, split), boundary.RUNTIME_COPY, hook_env=hook_env())
    return [], split


def origin_repo(repo: Path):
    try:
        got = forge.repo_of(runbranch.git(repo, "config", "--get", f"remote.{runbranch.ORIGIN}.url"))
    except runbranch.GitFailed:
        return None
    return None if got is None else {"host": got["host"], "path": f"{got['owner']}/{got['name']}"}


def hook_env() -> dict:
    env = dict(os.environ)
    userenv.read_gh_first(env)
    return env


def commit() -> dict:
    repo = Path.cwd()
    run_id = os.environ["WORKFLOW_ID"]
    mode = boundary.text(os.environ.get("INPUTS_MODE"))
    base_rev = boundary.text(os.environ.get("INPUTS_BASE_REV"))
    sealed = boundary.text(os.environ.get("INPUTS_SEALED_HASH"))
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
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_bytes(repo, base_rev, skip=boundary.SKIP)))
    if why:
        return stopped(f"{why}（commit しない）")
    _, issues = entryshape.named({"request": boundary.text(os.environ.get("INPUTS_REQUEST"))}, repo)
    try:
        commits, split = stack(repo, boundary.value(os.environ.get("INPUTS_ITEMS")), mode, run_id, sealed, name, base, issues)
        head = runbranch.git(repo, "rev-parse", "HEAD")
    except runbranch.GitFailed as error:
        return stopped(f"commit が通らなかった（対象の commit の hooks が落ちたか）: {error}（積まない・push しない）")
    why = seal.hash_refusal(sealed, seal.digest(green_cert.diff_between(repo, base_rev, head, skip=boundary.SKIP)))
    if why:
        return stopped(f"積んだ commit {head} の差分が封じた差分と違う: {why}（push しない）")
    return {"go": True, "head": head, "branch": name, "base": base, "repo": target, "commits": commits, "split": split, "reason": ""}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(stopped(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(commit, stopped)


if __name__ == "__main__":
    main()
