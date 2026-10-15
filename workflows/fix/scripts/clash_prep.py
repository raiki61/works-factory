# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""合わせのループの頭（ノード clash-prep・clash-ruled-prep。入力 pass は first か ruled、limit はループの max_iterations）: 段で扱う組
（clash.todo。first は組を当てるノードが確かめ直しの赤で戻した組と字で当たらなかった組、ruled はその申し出が直す裁定を受けた組）の先頭を控えの差分から
作業ツリーへ当て直し（clash.stage）、合わせ役の材料と指示書を組んで置き場に書く（clash.brief・clash.prompt。決まりは
commands/fix-rules/clash.md。この組の前の回の拒否が在れば、拒否の理由の全部のファイルを 1 行目で名指す）。
当て直せない組は合わせ役を起こさずに申し出へ回し（clash.settle_parked）、次の組へ進む。扱う組が無ければ go: false。
戻せず当たったままの組が在る run（fixboard.held）は作業ツリーを動かさず、扱う組を全部申し出へ回して go: false。
返り {prompt_file, go, iteration}（iteration はループの周の数。置き場の clash-turns-<pass>.json に数え、resume で数え直さない）。
回す側の誤り（入力が読めない・控えと結果が食い違う）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import clash  # noqa: E402
import fixboard  # noqa: E402
import oneline  # noqa: E402
import policy  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules" / "clash.md"
ACCEPT = {clash.FIRST: "clash-accept", clash.RULED: "clash-ruled-accept"}   # 受け付けのノード（拒否の控えの名の頭）


def turn(place, pass_: str) -> int:
    """ループの周の数を 1 つ進めて返す（控えはファイル。数えすぎは上限の周の片付けを早めるだけで、ループを上限で落とさない側）"""
    path = place / f"clash-turns-{pass_}.json"
    n = int((fixboard.read_json(path, {}) or {}).get("turns") or 0) + 1
    fixboard.write_json(path, {"turns": n})
    return n


def main(pass_: str) -> dict:
    place, repo = boundary.place("fix"), boundary.work_tree()
    n = turn(place, pass_)
    stuck = fixboard.held(place)
    while (todo := clash.todo(place, pass_)):
        gid = todo[0]
        ok, why = (False, stuck) if stuck else clash.stage(place, repo, gid, pass_, boundary.SKIP)
        if not ok:
            ids = clash.settle_parked(place, repo, gid, pass_=pass_, why=why, skip=boundary.SKIP)
            fixboard.trace(place, "clash_parked", group=gid, stage=pass_, requests=ids, why=why)
            stuck = fixboard.held(place)
            continue
        fixboard.trace(place, "clash_staged", group=gid, stage=pass_, turn=n)
        start = startrec.read(place)
        accept = f"{ACCEPT[pass_]}-{gid}"
        k = rolekit.attempt(place, accept)
        brief = clash.brief(place, gid)
        row = next(r for r in clash.load(place) if r["group_id"] == gid)
        text = clash.prompt(RULES, pass_, {"brief_file": str(brief), "patch_file": row["patch"],
                                           "policy_path": policy.frozen_copy(start), "request_file": startrec.request_file(start)},
                            reject_file=fixboard.rejects_file(place, accept, k - 1), iteration=k, lang=rolekit.lang_line(start))
        prompt = fixboard.write_text(place / clash.PROMPT.format(gid=gid), text)
        return {"prompt_file": str(prompt), "go": True, "iteration": n}
    return {"prompt_file": "", "go": False, "iteration": n}


if __name__ == "__main__":
    pass_ = os.environ.get("INPUTS_PASS", "")
    try:
        if pass_ not in clash.PASSES:
            raise ValueError(f"入力 pass は {clash.PASSES} のどれか: {pass_!r}")
        out = main(pass_)
    except Exception as e:
        print(f"clash-prep: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
