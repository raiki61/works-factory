"""設計の案を人と審査役に見せる md（docs/design/theme.md の 3 章と 1.3 の design.md）。見出しと札は人に見せる決まった字で、
欄の字は書き手の lang のまま写す。持ち主に聞く問いは MADR と同じ並び（問い → 案 → 案ごとの得と代償 → 推しと訳）で描く。"""
from __future__ import annotations


def _rows(items, line) -> list[str]:
    return [line(x) for x in items] or ["- なし"]


def md(doc: dict) -> str:
    owner = [p for p in doc["premises"] if p["by"] == "owner"]
    assumed = [p for p in doc["premises"] if p["by"] == "assumed"]
    out = ["# 設計の案", "", "## 問い", "", doc["question"], "", "## 目的", "", doc["purpose"], "",
           "## 前提", "", "### 人が決めた前提", "", *_rows(owner, lambda p: f"- {p['id']}: {p['what']}（出どころ: {p['from']}）"), "",
           "### 仮に置いた前提", "", *_rows(assumed, lambda p: f"- {p['id']}: {p['what']}（置いた訳: {p['from']}）"), "",
           "## 今在る物", "", *_rows(doc["current"], lambda n: f"- {n['id']}: {n['what']}（{n['where']}）"), "",
           "## 設計", "", *_rows(doc["parts"], lambda d: f"- {d['id']}: {d['what']}（{d['where']}）——{d['why']}"), "",
           "## 在る物で足りない訳", "",
           *_rows(doc["reuse"], lambda r: f"- {r['part']}: 先に見た物 {', '.join(r['existing']) or 'なし'}——{r['why_not']}"), "",
           "## 決まりが求める確かめ", "", *_rows(doc["checks"], lambda c: f"- {c['rule']}: {c['answer']}（{c['where']}）"), "",
           "## 持ち主に聞く問い", ""]
    for q in doc["asks"]:
        out += [f"### {q['id']}: {q['ask']}", ""]
        out += [f"- 案 {o['id']}: {o['what']}\n  - 得: {o['gain']}\n  - 代償: {o['cost']}" for o in q["options"]]
        out += ["", f"推し: {q['pick']}——{q['pick_why']}", ""]
    if not doc["asks"]:
        out += ["- なし", ""]
    out += ["## 部署の決め", "", *_rows(doc["decided"], lambda r: f"- {r['id']}: {r['what']}（出どころ: {r['by']}）——{r['why']}"), "",
            "## 変える所", "",
            *_rows(doc["changes"], lambda c: f"- {c['id']}（{c['op']}）{c['where']}: {c['what']}（部品: {', '.join(c['parts']) or 'なし'}）"), "",
            "## 作り変えの照らし", "",
            *_rows(doc["inventory"], lambda r: f"- {r['path']}:{r['lines']} {r['gist']} → {r['to']}"
                   + (f"（行き先: {r['dest']}）" if r["dest"] else "") + (f"——{r['why']}" if r["why"] else "")), "",
            "## 狭める所", "",
            *_rows(doc["narrows"], lambda n: f"- {n['what']}（" + (f"決め: {n['decided_by']}" if n.get("decided_by")
                                                                    else f"未決: {n.get('undecided_because') or ''}") + "）"), "",
            "## 前の往復の穴への答え", "", *_rows(doc["block_answers"], lambda a: f"- {a['key']}: {a['handled']}——{a['how']}"), "",
            "## 人の答えの使い道", "",
            *_rows(doc["answers_used"], lambda u: f"- {u['answer']}: " + (f"入れた欄 {', '.join(u['applied'])}" if u.get("applied")
                                                                          else f"入れなかった訳 {u.get('declined_why') or ''}"))]
    return "\n".join(out).rstrip() + "\n"
