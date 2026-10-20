"""変更に関わる試験だけを選ぶ口（持ち主の決め related-tests-only）。test-gate（実行器の照らしの回・最後のテスト）と fix（TDD の輪の頭）が使う。

工場が走らせる試験は、走らせ方が決まらない対象（applies: test_cmd が空で、対象の根に走らせる段の宣言が無い）では、変更に関わる
試験だけにする。全体の試験は CI と人に任せる。test_cmd と宣言は利用者が走らせ方を決めた道なので、ここで絞らない。

- applies(root, test_cmd) -> bool: 走らせ方が決まらない対象か
- pick(repo, *, rev, seeds, cache_dir) -> {whole, reasons, files, left, far}: rev から今の作業ツリーまでに触ったファイル（未追跡を含む）と
  seeds を起点に、直に関わる試験（impact.select_tests の direct_only。起点か深さ 1）を選ぶ。whole が真なら選べない（地図が引けない・
  分からない物が直に関わる所に在る）ので、呼び手は今までどおり一式を走らせる。files は回す試験のファイル（根からの相対。作業ツリーに
  在る物だけ）、left は届いただけで回さない試験、far は深さ 2 以上の分からない物（理由の形）。関わる試験が無いのは files が空
- args(repo, picked) -> list: files を絶対パスにした並び（TDD の実行器の第 1 引数の後ろに足す。whole なら空）
- lines(picked) -> list: 報告の行

言語・試験の実行器の名を持たない。試験の見分けと関わりの辺は impact が持つ。
"""
import os
import pathlib
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import declared_checks  # noqa: E402
import impact  # noqa: E402

LEFT_TO_OTHERS = "全体の試験は CI と人に任せた（工場は変更に関わる試験だけを走らせる）"


def applies(root, test_cmd) -> bool:
    return not (test_cmd or "").strip() and "fallback" in declared_checks.checks_plan(root)


def pick(repo, *, rev, seeds, cache_dir) -> dict:
    repo = pathlib.Path(repo)
    try:
        m = impact.map(repo, rev=rev, seeds=sorted(str(s) for s in seeds), diff=True, cache_dir=cache_dir)
        sel = impact.select_tests(m, direct_only=True)
    except (RuntimeError, OSError, ValueError) as e:
        return {"whole": True, "reasons": [f"変更の周りの地図が引けない（{type(e).__name__}: {' '.join(str(e).split())[:200]}）"],
                "files": [], "left": [], "far": []}
    if sel["run_all"]:
        return {"whole": True, "reasons": list(sel["reasons"]) or ["分からない物が直に関わる所に在る"], "files": [], "left": [],
                "far": []}
    return {"whole": False, "reasons": [], "files": [t for t in sel["selected"] if (repo / t).is_file()],
            "left": list(sel["left"]), "far": list(sel["far"])}


def args(repo, picked) -> list:
    if picked.get("whole"):
        return []
    root = pathlib.Path(repo).resolve()
    return [str(root / f) for f in picked.get("files") or []]


def lines(picked) -> list:
    if picked.get("whole"):
        return ["変更に関わる試験を選べなかったので、一式を走らせた: " + "・".join(picked.get("reasons") or [])]
    files, left, far = picked.get("files") or [], picked.get("left") or [], picked.get("far") or []
    out = [f"走らせた試験: 変更に関わる試験 {len(files)} 件" if files else "変更に関わる試験が無いので、試験は走らせなかった"]
    out += [f"  - {f}" for f in files]
    if left:
        out.append(f"走らせなかった試験（変更に届くが直には関わらない。{len(left)} 件）:")
        out += [f"  - {f}" for f in left]
    if far:
        out.append(f"どの試験に関わるか読み切れないので一式の理由にしなかった物（{len(far)} 件）:")
        out += [f"  - {f}" for f in far]
    return [*out, LEFT_TO_OTHERS]
