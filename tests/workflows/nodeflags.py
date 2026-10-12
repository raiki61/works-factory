"""ブロックの YAML の節の印の照らし（各ブロックの試験 test_<ブロック>.py が呼ぶ。test_* でないので unittest の発見に拾われない）。

- coldwrite_named(doc): plugins: に coldwrite を名指す節の id。coldwrite は隔離した設定の settings.json の hooks で全部の役に効かせる
  （bin/_lib/toolset.py）。節に名指すと、入れていない普通の利用者（E14）の run でその節が落ちる
- guarded_mismatches(doc): 作業ツリーの姿を比べる受け付けの節の with: の status_guarded が真 ⇔ 受ける役の節（depends_on の
  ただ 1 つの prompt・command の節）が mutates_checkout: false、に合わない節の id。真の節の script は INPUTS_STATUS_GUARDED を読む。
  同じ script を回すほかの節は偽を書く（Archon の validate は、script が読む INPUTS_* を全部の節が結ぶことを求める）
"""
import pathlib

WORKFLOWS = pathlib.Path(__file__).resolve().parents[2] / "workflows"
# 役の前後の作業ツリーの姿（lib/accept.tree_state）を比べる受け付けの script
TREE_ACCEPTS = frozenset({"ci_accept", "rule_accept", "delta_accept", "review2_accept", "r2_accept", "review_accept",
                          "diagnose_accept", "verify", "purpose_accept", "spec_accept", "rejudge_accept", "material_accept",
                          "pr_accept", "premises_accept"})


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk((n.get("loop_group") or {}).get("nodes") or [])


def coldwrite_named(doc) -> list:
    return [n["id"] for n in walk(doc["nodes"]) if any("coldwrite" in str(p) for p in n.get("plugins") or [])]


def guarded_mismatches(doc, block: str) -> list:
    nodes = {n["id"]: n for n in walk(doc["nodes"])}
    out = []
    for n in nodes.values():
        flag = (n.get("with") or {}).get("status_guarded")
        if n.get("script") not in TREE_ACCEPTS:
            if flag is not None:
                out.append(f"{n['id']}: 作業ツリーを比べない節に status_guarded")
            continue
        roles = [nodes[d] for d in n.get("depends_on") or [] if d in nodes and ("prompt" in nodes[d] or "command" in nodes[d])]
        if not roles:
            if flag not in (None, False):
                out.append(f"{n['id']}: 役を受けない節の status_guarded が {flag!r}")
            continue
        if len(roles) != 1:
            out.append(f"{n['id']}: 受ける役が 1 つでない（{[r['id'] for r in roles]}）")
            continue
        want = roles[0].get("mutates_checkout") is False
        if (flag is True) != want or flag not in (None, True, False):
            out.append(f"{n['id']}: status_guarded {flag!r} だが役 {roles[0]['id']} の mutates_checkout は "
                       f"{roles[0].get('mutates_checkout')!r}")
        script = WORKFLOWS / block / "scripts" / f"{n['script']}.py"
        if flag is True and "INPUTS_STATUS_GUARDED" not in script.read_text(encoding="utf-8"):
            out.append(f"{n['id']}: script {script.name} が INPUTS_STATUS_GUARDED を読まない")
    return out
