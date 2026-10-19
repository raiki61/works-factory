"""腕の照らし（docs/design/gate-efficacy.md の 3 節）: 腕が赤・対照の緑・守る行の通過をそろえずに clean を名乗るのを拒む。
元 lib/judge_accept.py の _unproven・gate_arms_all_red（raise Reject を文の返しに替えた）"""
import materialkit  # lib/
import recount  # lib/


def unproven(arms) -> list:
    """覆いの証拠にならない腕——赤・対照の緑・守る行の通過の印のどれかが欠けた腕の名前"""
    return [a["arm"] for a in arms
            if not (a.get("red_confirmed") and a.get("control_green") and not recount.blank(a.get("hit_evidence"), 10))]


def arms_problem(name: str, reply: dict):
    """拒む文（最初に当たった 1 つ）。どれにも当たらなければ None"""
    arms = reply.get("arms", [])
    st = reply.get("material", {}).get("status")
    if not arms and st in materialkit.OBSERVED_STATUS:
        return f"観点 {name}: status={st} なのに腕が 0 行——撃った腕を行にするか、撃てた腕が無いなら not_run（理由つき）で書け"
    unred = [a["arm"] for a in arms if not a.get("red_confirmed")]
    nocontrol = [a["arm"] for a in arms if not a.get("control_green")]
    nohit = [a["arm"] for a in arms if recount.blank(a.get("hit_evidence"), 10)]
    if st != "found" and unproven(arms) and st != "awaiting_human":
        return (f"観点 {name}: 赤を見ていない腕 {unred} / 壊していない写しで緑を確かめていない腕 {nocontrol} / "
                f"守る行を通ったことを測っていない腕 {nohit} が在るのに status=clean"
                "——未達は found（count と detail に腕を書く）、人の起動待ちなら awaiting_human（reason に何を待つか）")
    proven = [a["arm"] for a in arms
              if a.get("red_confirmed") and a.get("control_green") and recount.blank(a.get("hit_evidence"), 10)]
    if proven:
        return (f"観点 {name}: 腕 {proven} は赤も control の緑も見ているが、**その腕が守る行を通ったこと**を測っていない"
                "（hit_evidence）——赤は柵の不在の検知であって、この腕がその柵に当たった証拠にならない。"
                "分岐が書く値を一意の印に替え、その印が出力か記録に現れることを確かめて hit_evidence に書け")
    return None
