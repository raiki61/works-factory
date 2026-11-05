"""run を 1 枚の HTML のページに組む（見る道具のページ。入口は viewer/runpage.py、設計は docs/design/viewer.md の 9 章、持ち主の決め
run-page-v4）。持ち主が良いと見た試作の 4 版を、組みの形のまま移した物。

- 読む物は入口が渡すデータ（viewer/runtrace.py の read と同じ欄。作り・記録・会話）だけで、DB は開かない（run の入力と置き場の根は
  src/runread.py の run が読む）。ほかに読むのは雛形（viewer/page/）と、run の入力の頼みのファイル（JSON）と、run の写しの中の pack
  （指示の md の断片と筋書きの名）だけ。ファイルは書かず、ページの字を返す
- 組む物: 段 → block → ループ → ノードの木・block の入出力（src/ioflow.py）・実行条件を記録の値で解いた分岐と、同じ値で分かれる兄弟を
  1 つにした分岐の合成ノード・リジェクト（受け付けの script が ok=false を返した周）・承認の回答・失敗・AI の費用の上位・指示の md の
  プレースホルダに入った値（src/fill.py）・block を記録の値で回し直す命令の下書き（試していない）
- 雛形の /*TOKENS*/・/*DAGRE*/・/*DATA*/ を、色と字の値・図の配置のライブラリ・データの JSON で埋める。データの < は \\u003c にし、
  script の中身を閉じない
"""
import json
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path

from viewer.src import fill, ioflow, runread, stages

ASSETS = Path(__file__).resolve().parents[1] / "page"
TEMPLATE = ASSETS / "page.tpl.html"


def render(data: dict, target: Path, pack_name: str) -> str:
    """ページの字。data は runtrace.read の答え、target は対象の根（回し直しの命令の --cwd）、pack_name は run の写しの中の pack の
    フォルダの名"""
    run, graphs = data["run"], data["shape"]["graphs"]
    by_name = {g["name"]: k for k, g in graphs.items()}
    top_graph = by_name.get(run["graph"])
    # 段に畳むのは line の run だけ（段の表は line の物）。ほかの graph の run は一番上のノードを根の下に並べる
    table = stages.TABLE["stages"] if top_graph == stages.TABLE["graph"] else []
    events = run["events"]
    skipped = run.get("skipped") or []


    def under(key, toks):
        return tuple(toks[:len(key)]) == key


    # 木: key（tokens の組）→ 物
    tree = {}


    def add(key, name, kind, item=None, kids=()):
        tree[key] = {"key": key, "name": name, "kind": kind, "item": item or {}, "kids": list(kids)}


    def walk_items(prefix, items):
        keys = []
        for it in items:
            k = prefix + (it["id"],)
            keys.append(k)
            if it["kind"] == "block" and it.get("target") in graphs:
                sub = walk_items(k, graphs[it["target"]]["items"])
                add(k, it["id"], "block", it, sub)
            elif it["kind"] == "loop":
                sub = walk_items(k, it.get("kids") or [])
                add(k, it["id"], "loop", it, sub)
            else:
                add(k, it["id"], it["kind"], it)
        return keys


    top_keys = walk_items((), graphs[top_graph]["items"] if top_graph in graphs else [])
    stage_of = {}
    wiring = set()
    for i, s in enumerate(table):
        for n in s["nodes"]:
            stage_of[n] = i
        wiring |= set(s.get("wiring") or [])
    root_kids = []
    for i, s in enumerate(table):
        sk = ("#stage", i)
        kids = [k for k in top_keys if stage_of.get(k[0]) == i]
        add(sk, s["name"], "stage", {"desc": s.get("line") or ""}, kids)
        root_kids.append(sk)
    add((), top_graph or run["graph"], "root", {}, root_kids if table else top_keys)


    def leaf_events(key):
        if key and key[0] == "#stage":
            ks = tree[key]["kids"]
            return [e for e in events if any(under(k, e["tokens"]) for k in ks)]
        return [e for e in events if under(key, e["tokens"])]


    def own_events(key):
        return [e for e in events if tuple(e["tokens"]) == key]


    def look(key):
        evs = leaf_events(key)
        if not evs:
            sk = [s for s in skipped if (key and key[0] != "#stage" and under(key, s["tokens"]))]
            if key and key[0] == "#stage":
                sk = [s for s in skipped if any(under(k, s["tokens"]) for k in tree[key]["kids"])]
            return "skipped" if sk else "none"
        sts = [e["status"] for e in evs]
        for s in ("failed", "running", "waiting"):
            if s in sts:
                return s
        return "ok"


    def cost(key):
        return sum(float(e.get("cost") or 0) for e in leaf_events(key) if e["kind"] not in runread.GROUP_KINDS)


    def secs(key):
        evs = [e for e in leaf_events(key) if e.get("start") and e.get("end")]
        if not evs:
            return None
        p = lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))
        return (max(p(e["end"]) for e in evs) - min(p(e["start"]) for e in evs)).total_seconds()


    def what(key):
        t = tree[key]
        it = t["item"]
        if t["kind"] == "block" and it.get("target") in graphs:
            return graphs[it["target"]].get("desc") or it.get("desc") or ""
        return it.get("desc") or ""


    def first_sentence(s, n=46):
        s = (s or "").strip().split("\n")[0]
        s = s.split("。")[0]
        return s[:n] + ("…" if len(s) > n else "")


    WORD = {"ok": "完了", "failed": "失敗", "skipped": "スキップ", "none": "未実行", "running": "実行中", "waiting": "入力待ち"}
    KIND = {"ai": "AI", "script": "script", "bash": "bash", "gate": "承認", "halt": "停止", "block": "block", "loop": "ループ", "child": "子 run",
            "stage": "ステージ"}


    def fmt_s(s):
        if s is None:
            return ""
        return f"{s/60:.0f}分" if s >= 60 else f"{s:.0f}秒"


    def esc(s):
        return str(s).replace("\\", "\\\\").replace('"', '\\"')


    # ── 会話の記録（Claude Code の jsonl を viewer/src/session.py が読んだ物）と、プロンプトの中の値
    texts, sessions = data["texts"], run.get("sessions") or {}
    pack = Path(run["copy"]) / pack_name if run.get("copy") else None
    used, SESS = set(), {}
    CUT = 20000


    def slim(s):
        for k, m, *r in s["seq"]:
            if k in ("user", "say", "think", "result"):
                used.add(m)
            elif k == "call":
                used.add(r[0])
        used.update(s["system"])
        turns = []
        for t in s["turns"]:
            for c in t["calls"]:
                used.update(x for x in (c.get("text"), c.get("out")) if x)
            turns.append({"at": t.get("at"), "start": t.get("start"), "end": t.get("end"), "model": t.get("model"), "usage": t.get("usage") or {},
                          "copied": bool(t.get("copied")),
                          "calls": [{k2: c.get(k2) for k2 in ("id", "name", "text", "out", "error", "at", "done")} for c in t["calls"]]})
        return {"system": s["system"], "seq": s["seq"], "turns": turns, "cost": s.get("cost"),
                "agents": [dict(slim(a), id=a.get("id"), meta=a.get("meta") or {}) for a in s.get("agents") or []]}


    def talk(e, md):
        pre = e.get("session")
        if not pre or pre not in sessions:
            return {}
        if pre not in SESS:
            SESS[pre] = slim(sessions[pre])
        s = sessions[pre]
        sent = next((m for k, m, *r in s["seq"] if k == "user"), None)
        vals = None
        if sent and md and pack is not None:
            vals = fill.values(md.get("text", ""), md.get("file", ""), pack, texts[sent])
        return {"session": pre, "sent": sent, "values": vals, "model": e.get("model"), "usage": e.get("usage") or {}, "turns": e.get("turns")}


    # ── 3 版目: 1 枚のキャンバスに、dagre の入れ子の並べで、枠をその場で開け閉めする（見た目は attention の milestone-map に寄せる）
    K = lambda key: json.dumps(list(key), ensure_ascii=False)
    objs = {}
    for key, t in tree.items():
        it = t["item"]
        parent = K(key[:-1]) if key else None
        if key and key[0] == "#stage":
            parent = K(())
        elif len(key) == 1:
            parent = K(("#stage", stage_of.get(key[0], -1))) if stage_of.get(key[0]) is not None else K(())
        if len(key) == 1:
            sibs = {k[0]: K(k) for k in top_keys}
        elif key and key[0] != "#stage":
            sibs = {tree[k]["name"]: K(k) for k in tree[key[:-1]]["kids"]}
        else:
            sibs = {}
        deps = [sibs[d] for d in (it.get("deps") or []) if d in sibs]
        is_wire = (not t["kids"] and t["kind"] == "script" and (key[-1] in wiring or str(key[-1]).endswith(("-out", "-in"))))
        evs = own_events(key) if not t["kids"] else []
        md = it.get("md") if isinstance(it.get("md"), dict) else None
        objs[K(key)] = {
            "name": t["name"], "kind": t["kind"], "kindWord": KIND.get(t["kind"], t["kind"]), "state": look(key),
            "what": first_sentence(what(key), 80), "whatFull": what(key), "cost": round(cost(key), 4), "time": fmt_s(secs(key)),
            "runs": len(evs), "kids": [K(k) for k in t["kids"]], "parent": parent, "deps": deps, "wire": is_wire,
            "when": it.get("when") or "", "depsNames": it.get("deps") or [],
            "skip": next((s.get("cause") for s in skipped if tuple(s["tokens"]) == key), None),
            "skipAt": next((s.get("time") for s in skipped if tuple(s["tokens"]) == key), None),
            "md": (md or {}).get("text", "")[:12000] if md else "", "mdPath": (md or {}).get("file", "") if md else "",
            "script": it.get("script_file") or "", "doc": it.get("doc") or "",
            "events": [{"loop": e.get("loop"), "status": e["status"], "start": e.get("start"), "end": e.get("end"), "cost": e.get("cost"),
                        "error": e.get("error") or "", "output": (e.get("output") or "")[:8000], **talk(e, md)} for e in evs],
        }
    # ── 出入口と分岐（ioflow）: block の入力値・出力値、条件の式を値で解いた物、連鎖のスキップの元
    fl = ioflow.Flow(tree, events, graphs)
    fl.root = run.get("inputs") or {}
    ran_at = {}
    for e in events:
        if e.get("start"):
            ran_at.setdefault(tuple(e["tokens"]), []).append(e["start"])
    skip_of = {tuple(x["tokens"]): x for x in skipped}
    flat_key = {}
    for key in tree:
        if key and key[0] != "#stage":
            flat_key["__".join(key)] = key
            if len(key) >= 2:
                flat_key["__".join(key[:-1]) + "." + key[-1]] = key


    def short(v, n=4000):
        t = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        return t if len(t) <= n else t[:n] + f"…（残り {len(t) - n} 文字）"


    def code_reads(k, depth=0):
        """つなぎの script（code）が読んだ物を、block まで辿った一覧 [[名, key]]。*-out の script は、その block の返しを包む物なので、
        包んだ block に読み替える。辿れない物（run の入力など）は名だけ"""
        it = tree[k]["item"]
        got = []
        for rs in (it.get("refs") or {}).values():
            for r in rs:
                node = r.get("node")
                if node == "INPUTS":
                    got.append(["親の入力 " + str(r.get("field")), None])
                    continue
                sk = None
                for i in range(len(k) - 1, -1, -1):
                    if tuple(k[:i]) + (node,) in tree:
                        sk = tuple(k[:i]) + (node,)
                        break
                if not sk:
                    got.append([node, None])
                    continue
                t2 = tree[sk]
                if t2["kind"] == "block":
                    got.append([node, K(sk)])
                elif t2["kind"] in ("script", "bash") and depth < 3:
                    inner = code_reads(sk, depth + 1)
                    got.extend(inner if inner and node.endswith("-out") else [[node, K(sk)]])
                else:
                    got.append([node, K(sk)])
        seen, uniq = set(), []
        for n_, k_ in got:
            if n_ not in seen:
                seen.add(n_)
                uniq.append([n_, k_])
        return uniq


    def src_of(scope, refs):
        out = []
        for r in refs or []:
            node, field = r.get("node"), r.get("field")
            if node == "INPUTS":
                out.append({"kind": "inputs", "field": field})
                continue
            k = None
            for i in range(len(scope), -1, -1):
                if tuple(scope[:i]) + (node,) in tree:
                    k = tuple(scope[:i]) + (node,)
                    break
            kind = tree[k]["kind"] if k else "?"
            ent = {"kind": "block" if kind == "block" else "code" if kind in ("script", "bash") else kind, "key": K(k) if k else None, "name": node, "field": field}
            if ent["kind"] == "code" and k:
                ent["reads"] = code_reads(k)
            out.append(ent)
        return out


    for key, t in tree.items():
        o = objs[K(key)]
        it = t["item"]
        if t["kind"] == "block" and it.get("target") in graphs:
            got = fl.block_inputs(key)
            decl = {p["name"]: p for p in graphs[it["target"]].get("inputs") or []}
            o["portsIn"] = [{"n": n, "v": short(got.get(n)), "empty": got.get(n) in (None, "", [], {}), "src": src_of(key[:-1], (it.get("refs") or {}).get(n)),
                             "desc": (decl.get(n) or {}).get("desc", "")[:300]} for n in (it.get("with") or {})]
            ret = fl.returned(key)
            types = {f[0]: f[1] for f in graphs[it["target"]].get("return_fields") or []}
            o["portsOut"] = [{"n": n, "v": short(v), "empty": v in (None, "", [], {}), "type": types.get(n, "")} for n, v in ret.items()] if isinstance(ret, dict) else []
            o["nIn"], o["nOut"] = len(o["portsIn"]), len(o["portsOut"])
        w = it.get("when")
        if w and key and key[0] != "#stage":
            sk = skip_of.get(key)
            st_ = o["state"]
            if not sk and key not in ran_at and t["kids"] and st_ == "skipped":
                # 枠（block・ループ）がスキップの時、記録は中のノードのスキップに在る。一番早い物を、この枠のスキップとして読む
                inner = sorted((x for x in skipped if tuple(x["tokens"])[:len(key)] == key and x.get("time")), key=lambda x: x["time"])
                sk = inner[0] if inner else None
                if sk and (sk.get("cause") or {}).get("kind") == "condition" and tuple(sk["tokens"]) != key:
                    sk = dict(sk, cause={"kind": "condition", "expr": w})
            ran_now = key in ran_at or (t["kids"] and st_ in ("ok", "failed", "running", "waiting"))
            at = max(ran_at[key]) if key in ran_at else (sk.get("time") if sk else min((e["start"] for e in leaf_events(key) if e.get("start")), default=None))
            if sk and (sk.get("cause") or {}).get("kind") == "upstream_skipped":
                ok_ = flat_key.get((sk["cause"] or {}).get("origin", ""))
                o["branch"] = {"expr": w, "upstream": K(ok_) if ok_ else None, "upName": (sk["cause"] or {}).get("origin")}
            else:
                shown, res, refs_used = fl.cond_at(key[:-1], w, at)
                actual = "ran" if ran_now else "skipped" if sk or st_ == "skipped" else "none"
                o["branch"] = {"expr": w, "shown": shown, "result": res, "actual": actual,
                               "used": [[t_.split(".")[-1], json.dumps(v, ensure_ascii=False)[:40]] for t_, v in refs_used], "refs": sorted({t_ for t_, _ in refs_used}),
                               "mismatch": (res is True and actual == "skipped") or (res is False and actual == "ran")}
    # 分かれ道: 同じ親の中で、同じ値を見る兄弟の一方が走り、一方がスキップになった物だけを「分岐」とする（どこにでも在る ok=true の見張りを札にしない）
    by_parent = {}
    for key in tree:
        o = objs[K(key)]
        b = o.get("branch")
        if b and "used" in b:
            by_parent.setdefault(key[:-1], []).append((key, set(b["refs"]), b))
    for sibs in by_parent.values():
        for key, refs_, b in sibs:
            b["fork"] = b.get("actual") in ("ran", "skipped") and any(k2 != key and refs_ & r2 and b2.get("actual") in ("ran", "skipped") and b2.get("actual") != b.get("actual") for k2, r2, b2 in sibs)
    # ── 分岐のノード（表示だけの擬似ノード）: 同じ親の中で、同じ値（$x.output.f か $INPUTS.f）を見て、違う値で分かれる兄弟の組
    _ATOM = re.compile(r"(\$[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_]+)+)\s*(==|!=)\s*('[^']*'|\"[^\"]*\"|[A-Za-z0-9_.-]+)")


    def _canon(op, lit):
        v = lit.strip("'\"")
        if v in ("true", "false") and op == "!=":
            op, v = "==", "false" if v == "true" else "true"
        return ("= " if op == "==" else "≠ ") + v


    RAN = ("ok", "failed", "running", "waiting")
    SWITCHES = []
    for pk, po in list(objs.items()):
        kids = [k for k in po.get("kids") or [] if objs[k].get("when")]
        if len(kids) < 2:
            continue
        lab = {}   # key → {ref: label}
        for k in kids:
            atoms = _ATOM.findall(objs[k]["when"])
            cnt = {}
            for ref, op, lit in atoms:
                cnt[ref] = cnt.get(ref, 0) + 1
            for ref, op, lit in atoms:
                if cnt[ref] == 1:
                    lab.setdefault(k, {})[ref] = _canon(op, lit)
        refs_all = list(dict.fromkeys(r for d in lab.values() for r in d))
        cand = []
        for ref in refs_all:
            mem = [k for k in kids if ref in lab.get(k, {})]
            if len({lab[k][ref] for k in mem}) >= 2:
                cand.append([[ref], set(mem)])
        # 同じノードの組を見る分岐（review-prep の resubmit と tree など）は 1 つのひし形にまとめ、道は値の組み合わせで分ける
        merged = True
        while merged:
            merged = False
            for i in range(len(cand)):
                for j in range(i + 1, len(cand)):
                    if cand[i][1] & cand[j][1]:
                        cand[i][0] += cand[j][0]
                        cand[i][1] |= cand[j][1]
                        del cand[j]
                        merged = True
                        break
                if merged:
                    break
        par = json.loads(pk)
        for refs_, memset in cand:
            mem = [k for k in kids if k in memset]
            one = len(refs_) == 1
            combo = {k: (lab[k][refs_[0]] if one else ", ".join(f"{r.split('.')[-1]} {lab[k][r]}" for r in refs_ if r in lab[k])) for k in mem}
            labels = list(dict.fromkeys(combo[k] for k in mem))
            arms = [{"label": l, "keys": [k for k in mem if combo[k] == l]} for l in labels]
            for a_ in arms:
                a_["taken"] = any(objs[k]["state"] in RAN for k in a_["keys"])
            vals = {}
            for r in refs_:
                for k in mem:
                    m_ = re.search(re.escape(r) + "〔(.*?)〕", (objs[k].get("branch") or {}).get("shown") or "")
                    if m_ and m_.group(1) not in ("null", "None"):
                        vals[r.split(".")[-1]] = m_.group(1)
                        break
            srcs = list(dict.fromkeys(r[1:].split(".")[0] for r in refs_))
            dks = [K(tuple(par) + (x,)) for x in srcs if x != "INPUTS" and K(tuple(par) + (x,)) in po["kids"]]
            keys = [k for a_ in arms for k in a_["keys"]]
            common = set(objs[keys[0]]["deps"]).intersection(*(set(objs[k]["deps"]) for k in keys[1:]))
            sdeps = dks if dks else sorted(common)
            sk = K(tuple(par) + ("#sw:" + "|".join(refs_),))
            fields = [r.split(".")[-1] for r in refs_]
            name = (srcs[0] if srcs[0] != "INPUTS" else "入力") + "." + "・".join(fields) if len(srcs) == 1 else "・".join(r[1:].replace(".output", "") for r in refs_)
            objs[sk] = {"name": name, "kind": "switch", "kindWord": "分岐", "state": "ok" if any(a_["taken"] for a_ in arms) else "skipped",
                        "what": "", "whatFull": "・".join(refs_) + " の値で道が分かれる所（Archon のノードではなく、各ノードの実行条件から合成した物）", "cost": 0, "time": "",
                        "runs": 0, "kids": [], "parent": pk, "deps": sdeps, "wire": False, "when": "", "depsNames": [], "skip": None, "skipAt": None,
                        "md": "", "mdPath": "", "script": "", "doc": "", "events": [], "ref": "・".join(refs_), "value": ", ".join(f"{f}={v}" for f, v in vals.items()) if not one else vals.get(fields[0]),
                        "arms": arms, "decider": dks[0] if len(dks) == 1 else None}
            po["kids"].append(sk)
            drop = set(dks) if dks else common
            for a_ in arms:
                for k in a_["keys"]:
                    o2 = objs[k]
                    o2["deps"] = [d for d in o2["deps"] if d not in drop] + [sk]
                    o2.setdefault("swArm", {})[sk] = a_["label"]
                    if o2.get("branch"):
                        o2["branch"]["sw"] = True
            SWITCHES.append(sk)
    print("分岐のノード", len(SWITCHES), "うち道が分かれた", sum(1 for k in SWITCHES if sum(a["taken"] for a in objs[k]["arms"]) == 1),
          file=sys.stderr)
    # 擬似の札: 開いた block の中の「受けた」「返した」
    for key, t in list(tree.items()):
        o = objs[K(key)]
        if "portsIn" in o and o["kids"]:
            for tag, kind, word in (("#in", "pin", "入力"), ("#out", "pout", "出力")):
                pk = K(key + (tag,))
                objs[pk] = {"name": word, "kind": kind, "kindWord": "I/O", "state": o["state"], "what": "", "whatFull": "", "cost": 0, "time": "",
                            "runs": 0, "kids": [], "parent": K(key), "deps": [], "wire": False, "when": "", "depsNames": [], "skip": None, "skipAt": None,
                            "md": "", "mdPath": "", "script": "", "doc": "", "events": [], "of": K(key)}
                o["kids"].append(pk)
    # ── 修正と検証道: block ごとに、設計書・プロンプトのテンプレート・筋書き・記録した入力で block だけを回し直す命令の下書き
    art_root = Path(run["output_root"]) / runread.ARTIFACTS / runread.RUNS_DIR / run["id"] if run.get("output_root") else None


    def as_arg(v):
        """入口の値を --input の字にする。記録の置き場を指す pointer は、置き場のファイルの絶対パスに直す（直したかを返す）"""
        def art(x):
            return isinstance(x, dict) and x.get("type") == "archon_artifact" and x.get("path")
        if art(v) and art_root:
            return str(art_root / v["path"]), True
        if isinstance(v, list) and v and all(art(x) for x in v) and art_root:
            return json.dumps([str(art_root / x["path"]) for x in v], ensure_ascii=False), True
        return (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)), False


    pack_dir = pack
    for key, t in tree.items():
        o = objs[K(key)]
        it = t["item"]
        if t["kind"] != "block" or it.get("target") not in graphs:
            continue
        g = graphs[it["target"]]
        folder = Path(g["file"]).parent.name if g.get("file") else it["target"]
        fixtures = sorted(p_.name for p_ in (pack_dir / folder / "fixtures").glob("*.yaml")) if pack_dir and (pack_dir / folder / "fixtures").is_dir() else []
        ai_md = []
        def ai_walk(items):
            for x in items:
                if x["kind"] == "ai" and isinstance(x.get("md"), dict):
                    ai_md.append(f"workflows/{x['md'].get('file', '')}")
                if x["kind"] == "loop":
                    ai_walk(x.get("kids") or [])
        ai_walk(g["items"])
        args, conv, longest = [], [], 0
        for prt in o.get("portsIn") or []:
            v = fl.block_inputs(key).get(prt["n"])
            if v in (None, "", [], {}):
                continue
            a, c = as_arg(v)
            if c:
                paths_ = json.loads(a) if a.startswith("[") else [a]
                conv.append({"n": prt["n"], "missing": [x for x in paths_ if not Path(x).exists()]})
            longest = max(longest, len(a))
            args.append(f"--input {prt['n']}={shlex.quote(a)}")
        o["fixit"] = {"design": [f"docs/design/{d_}" if not str(d_).startswith("docs/") else d_ for d_ in (g.get("docs") or [])], "yaml": f"workflows/{g.get('file', '')}",
                      "md": ai_md, "fixtures": [f"workflows/{folder}/fixtures/{x}" for x in fixtures], "tests": f"tests/blocks/{folder.replace('-', '_')}/",
                      "cmd": " \\\n  ".join([f"bin/works-factory workflow run {g['name']} --cwd {shlex.quote(str(target))}"] + args),
                      "converted": conv, "longest": longest}

    # ── ループの周とリジェクト（受け付けの script が ok=false を返した周）
    def parse_out(e):
        try:
            return json.loads(e.get("output") or "null")
        except ValueError:
            return None


    REJECTS = []
    for e in events:
        if not e["tokens"][-1].endswith("accept"):
            continue
        oo = parse_out(e)
        if isinstance(oo, dict) and oo.get("ok") is False:
            key = tuple(e["tokens"])
            sib_ai = [k2 for k2 in tree.get(key[:-1], {}).get("kids", []) if tree[k2]["kind"] == "ai"]
            REJECTS.append({"key": K(key), "ai": K(sib_ai[0]) if sib_ai else None, "loop": K(key[:-1]), "round": (e.get("loop") or [None])[-1],
                            "reason": str(oo.get("reason") or "")[:3000], "giveUp": bool(oo.get("give_up")), "at": e.get("end") or e.get("start")})
    for key, t in tree.items():
        if t["kind"] == "loop":
            o = objs[K(key)]
            rounds = {tuple(e.get("loop") or []) for e in leaf_events(key) if e.get("loop")}
            o["rounds"] = len({r[-1] for r in rounds if r}) if rounds else 0
            o["rejects"] = sum(1 for r in REJECTS if r["loop"] == K(key))
    for r in REJECTS:
        if r["ai"]:
            objs[r["ai"]]["rejects"] = objs[r["ai"]].get("rejects", 0) + 1

    # ── 承認の回答（承認のノード）と、run の要約
    GATES = []
    for e in events:
        if e["kind"] == "wait":
            oo = parse_out(e)
            GATES.append({"key": K(tuple(e["tokens"])), "decision": (oo or {}).get("decision") if isinstance(oo, dict) else None,
                          "text": str((oo or {}).get("text") or "")[:2000] if isinstance(oo, dict) else "", "at": e.get("end") or e.get("start"), "status": e["status"]})
            objs[K(tuple(e["tokens"]))]["answer"] = GATES[-1]["decision"]
    FAILS = [{"key": K(tuple(e["tokens"])), "error": (e.get("error") or "")[:1500], "at": e.get("start")} for e in events if e["status"] == "failed" and e["kind"] not in runread.GROUP_KINDS]
    ai_cost = {}
    for key, t in tree.items():
        if t["kind"] == "ai":
            c_ = sum(float(e.get("cost") or 0) for e in own_events(key))
            if c_:
                ai_cost[K(key)] = c_
    TOPCOST = sorted(ai_cost.items(), key=lambda x: -x[1])[:6]
    MISMATCH = [k for k, o in objs.items() if (o.get("branch") or {}).get("mismatch")]
    REQUEST = None
    _req = (run.get("inputs") or {}).get("request")
    if isinstance(_req, str) and _req.endswith(".json") and Path(_req).is_file():
        try:
            REQUEST = json.loads(Path(_req).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            REQUEST = None
    SUMMARY = {"inputs": {k: (v if len(str(v)) < 400 else str(v)[:400] + "…") for k, v in (run.get("inputs") or {}).items()},
               "request": REQUEST if REQUEST is None or len(json.dumps(REQUEST, ensure_ascii=False)) < 30000 else None,
               "counts": run.get("node_counts") or {}, "gates": GATES, "rejects": REJECTS, "fails": FAILS,
               "topcost": [[k, round(c_, 3)] for k, c_ in TOPCOST], "mismatch": MISMATCH, "seconds": run.get("seconds"), "outcome": run.get("outcome"),
               "result": run.get("result_word")}
    # 段どうしの線: 段の中の一番上のノードの deps が別の段を指す物は、上の deps（line の兄弟）で辿れる
    title = f"{run['graph']} の run {run['id'][:8]}"
    head = {"title": title, "started": run.get("started"), "status": run.get("status"),
            "result": run.get("result_word") or run.get("outcome") or "", "cost": run.get("cost") or 0}
    dagre_js = (ASSETS / "dagre.js").read_text(encoding="utf-8")
    tokens = (ASSETS / "tokens.css").read_text(encoding="utf-8")
    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("/*TOKENS*/", tokens).replace("/*DAGRE*/", dagre_js.replace("</script", "<\\/script"))
    TX = {m: (t if len(t) <= CUT or any(ev.get("sent") == m for o in objs.values() for ev in o["events"]) else t[:CUT] + f"\n…（残り {len(t) - CUT} 文字は省略）")
          for m, t in texts.items() if m in used}
    blob = json.dumps({"head": head, "objs": objs, "words": WORD, "sess": SESS, "tx": TX, "summary": SUMMARY}, ensure_ascii=False).replace("<", "\\u003c")
    page = page.replace("/*DATA*/", blob)
    return page
