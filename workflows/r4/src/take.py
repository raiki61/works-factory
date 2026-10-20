"""範囲の役の返答の受け付け（docs/design/r4.md の 4 節）。lib/eyeverdict.r4_accept に、まとめた形の r3 の照らしを足した物"""
import accept      # lib/
import policy      # lib/
import rolekit     # lib/
import seal        # lib/
from engine.util import Reject   # lib/graphloops

from src import files, gate

R3_MISSING = "まとめた形の R3 全体の整合の答え（欄 r3 の status・reason・seen・unseen）が無いか形が違う"


def r3_problem(r3) -> bool:
    """欄 r3 が R3 の答えの形（object で、status が R3 の語、reason が空でない字、seen と unseen が配列）でないか"""
    return not (isinstance(r3, dict) and r3.get("status") in seal.eye_statuses("r3") and isinstance(r3.get("reason"), str)
                and r3["reason"].strip() and isinstance(r3.get("seen"), list) and isinstance(r3.get("unseen"), list))


def scope(place, got: tuple, doc: dict) -> dict:
    """got は (読めた返答, 読めない訳)（rolekit.resubmitted の返り）、doc は intake.json。返り {ok, done, give_up, reason}。
    方針とのぶつかりのうち、人が通しておらず記録された方針の行を名指さない行が在れば拒み、まとめた形では欄 r3 の形も照らす。
    消えた能力 lost は照らさない。3 回目の拒否で輪を抜ける（rolekit.GIVE_UP_AFTER）"""
    reply, _ = got
    passed = gate.human_passed(doc["asked"], doc["before_fix"])

    def check() -> dict:
        reasons = []
        off = [x for kind, _, x in gate.rows(reply) if kind == policy.POLICY_KIND and gate.passed_key(kind, x) not in passed
               and not policy.hits(doc["recorded"], x)]
        if off:
            reasons.append(gate.R4_REJECT + "\n" + gate.lines(off))
        if doc["coherence"] is True and r3_problem(reply.get("r3")):
            reasons.append(R3_MISSING)
        if reasons:
            raise Reject("\n\n".join(reasons))
        return {"ok": True}

    return rolekit.round_outcome(rolekit.accept_parsed(place, files.R4_NODE, got, lambda _: accept.guard(check)))
