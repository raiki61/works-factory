"""工場の作りの単位（block の出入口と分岐）の値を、run の記録から解く（ページ src/page.py だけが使う。docs/design/viewer.md の 9 章）。
- block を呼ぶ所の with/refs から、入口ごとの値と出どころ（兄弟の block・つなぎの script・上の入力・字のまま）を出す
- block の返しのノード（graph の returns）の出力から、返した欄の値を出す
- when の式の $<node>.output.<欄> を実際の値で置き換えて解き、Archon が実際に走らせたかと突き合わせる"""
import json
import re

REF = re.compile(r"\$([A-Za-z0-9_-]+)\.output((?:\.[A-Za-z0-9_]+)*)")
INREF = re.compile(r"\$INPUTS\.([A-Za-z0-9_]+)")


CUT = "… [truncated; original output was"   # Archon が DB に書く出力を切った印


def parse(text):
    if text is None:
        return None
    if isinstance(text, (dict, list, int, float, bool)):
        return text
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        pass
    if isinstance(text, str) and text.lstrip().startswith("{"):
        got = partial(text)
        if got:
            return got
    return text


def partial(text):
    """途中で切れた JSON の object の、切れる前に閉じた一番上の欄だけ（Archon は長い出力を切って DB に書く）"""
    dec = json.JSONDecoder(strict=False)
    i = text.index("{") + 1
    out = {}
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n,":
            i += 1
        if i >= n or text[i] != '"':
            break
        try:
            key, i = dec.raw_decode(text, i)
            while i < n and text[i] in " \t\r\n":
                i += 1
            if i >= n or text[i] != ":":
                break
            i += 1
            while i < n and text[i] in " \t\r\n":
                i += 1
            val, i = dec.raw_decode(text, i)
        except ValueError:
            break
        out[key] = val
    if out:
        out["\u2702"] = "Archon の記録で出力が切れていて、切れる前の欄だけを読んだ"
    return out


def dig(v, path):
    for p in [x for x in path.split(".") if x]:
        if isinstance(v, dict) and p in v:
            v = v[p]
        else:
            return None, False
    return v, True


class Flow:
    def __init__(self, tree, events, graphs):
        self.tree, self.graphs = tree, graphs
        self.outs = {}   # key → [(終わりの時刻, 出力)]（時刻の順）
        for e in events:
            if e.get("output") is not None:
                self.outs.setdefault(tuple(e["tokens"]), []).append((e.get("end") or e.get("start") or "", parse(e["output"])))
        for v in self.outs.values():
            v.sort(key=lambda x: x[0])
        self.root = {}   # 一番上の graph の入力（run の入力。$INPUTS を囲む block が無い時に引く）
        self.at = None   # 解く時刻（この時刻までに終わった出力だけを見る。None は最後の出力）
        self.inputs_cache = {}

    def _out(self, k):
        t = self.tree.get(k)
        if t and t["kind"] == "block":
            # block の出力は、その graph の返しのノードの出力（block の枠の出来事が持つ出力より先に見る）
            g = self.graphs.get(t["item"].get("target"))
            rk = k + ((g or {}).get("returns") or "finish",)
            if rk in self.outs:
                k = rk
        got = self.outs.get(k)
        if not got:
            return None, False
        if self.at:
            got = [x for x in got if x[0] and x[0] <= self.at] or []
            if not got:
                return None, True
        return got[-1][1], True

    def node_out(self, scope, name):
        """名の物の出力。ループの中からループの外の兄弟を指すこともあるので、内から外へ順に探す"""
        scope = tuple(scope)
        for i in range(len(scope), -1, -1):
            k = scope[:i] + (name,)
            v, found = self._out(k)
            if found or k in self.tree:
                return v
        return None

    def owner(self, scope):
        """scope を囲む一番内の block の key（無ければ None）"""
        scope = tuple(scope)
        for i in range(len(scope), 0, -1):
            t = self.tree.get(scope[:i])
            if t and t["kind"] == "block":
                return scope[:i]
        return None

    def block_inputs(self, key):
        """block（の呼び出しの key）が受けた値 {入口: 値}。上の入力（$INPUTS）は親の block の受けた値から引く"""
        key = tuple(key)
        if key in self.inputs_cache:
            return self.inputs_cache[key]
        self.inputs_cache[key] = {}
        t = self.tree.get(key)
        if not t or t["kind"] != "block":
            return {}
        it = t["item"]
        res = {}
        for port, raw in (it.get("with") or {}).items():
            res[port] = self.resolve(key[:-1], raw)
        self.inputs_cache[key] = res
        return res

    def resolve(self, scope, raw):
        """with の値の字を解く。字が 1 つの参照だけなら、その値そのもの。ほかは参照を JSON の字で置き換えた字"""
        if not isinstance(raw, str):
            return raw
        s = raw.strip()
        m = REF.fullmatch(s)
        if m:
            v, ok = dig(self.node_out(scope, m.group(1)), m.group(2))
            return v if ok else None
        m = INREF.fullmatch(s)
        if m:
            o = self.owner(scope)
            return self.block_inputs(o).get(m.group(1)) if o else self.root.get(m.group(1))

        def sub(mm):
            v, ok = dig(self.node_out(scope, mm.group(1)), mm.group(2))
            return json.dumps(v, ensure_ascii=False) if ok else "null"
        s2 = REF.sub(sub, raw)
        o = self.owner(scope)
        s2 = INREF.sub(lambda mm: json.dumps(self.block_inputs(o).get(mm.group(1)) if o else self.root.get(mm.group(1)), ensure_ascii=False), s2)
        return parse(s2)

    def returned(self, key):
        t = self.tree.get(tuple(key))
        if not t or t["kind"] != "block":
            return None
        g = self.graphs.get(t["item"].get("target"))
        if not g:
            return None
        v, _ = self._out(tuple(key) + (g.get("returns") or "finish",))
        return v

    # ── 条件の式（== != && || ! と括弧、true false null・数・字）
    def cond_at(self, scope, expr, at):
        old, self.at = self.at, at
        self.inputs_cache = {}
        try:
            return self.cond(scope, expr)
        finally:
            self.at = old
            self.inputs_cache = {}

    def cond(self, scope, expr):
        """返り: (値で置き換えた式の字, 真偽か None, 置き換えた参照の一覧 [(参照の字, 値)])"""
        used = []

        def val(name, path):
            if name == "INPUTS":
                o = self.owner(scope)
                v, ok = dig(self.block_inputs(o) if o else self.root, path)
            else:
                v, ok = dig(self.node_out(scope, name), path)
            return v if ok else None
        toks = re.findall(r"\$[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_]+)*|&&|\|\||==|!=|!|\(|\)|'[^']*'|\"[^\"]*\"|-?\d+(?:\.\d+)?|true|false|null|\S", expr)
        pos = [0]

        def peek():
            return toks[pos[0]] if pos[0] < len(toks) else None

        def take():
            pos[0] += 1
            return toks[pos[0] - 1]

        def atom():
            t = take()
            if t == "(":
                v = orx()
                take()
                return v
            if t == "!":
                return not truthy(atom())
            if t.startswith("$"):
                m = re.fullmatch(r"\$([A-Za-z0-9_-]+)((?:\.[A-Za-z0-9_]+)*)", t)
                name, path = m.group(1), m.group(2)
                if name != "INPUTS":
                    path = path[len(".output"):] if path.startswith(".output") else None
                    if path is None:
                        raise ValueError(t)
                v = val(name, path)
                used.append((t, v))
                return v
            if t in ("true", "false", "null"):
                return {"true": True, "false": False, "null": None}[t]
            if t[0] in "'\"":
                return t[1:-1]
            if re.fullmatch(r"-?\d+(?:\.\d+)?", t):
                return float(t) if "." in t else int(t)
            raise ValueError(t)

        def truthy(v):
            return bool(v) and v not in ("false",)

        def cmp():
            a = atom()
            if peek() in ("==", "!="):
                op = take()
                b = atom()
                eq = (a == b) or (str(a).lower() == str(b).lower() if isinstance(a, bool) or isinstance(b, bool) else False)
                return eq if op == "==" else not eq
            return a

        def andx():
            v = cmp()
            while peek() == "&&":
                take()
                w = cmp()
                v = truthy(v) and truthy(w)
            return v

        def orx():
            v = andx()
            while peek() == "||":
                take()
                w = andx()
                v = truthy(v) or truthy(w)
            return v
        try:
            r = orx()
            result = truthy(r) if not isinstance(r, bool) else r
        except (ValueError, IndexError, AttributeError):
            result = None
        shown = expr
        for t, v in sorted(set((t, json.dumps(v, ensure_ascii=False)) for t, v in used), key=lambda x: -len(x[0])):
            shown = shown.replace(t, f"{t}〔{v}〕")
        return shown, result, [(t, v) for t, v in used]
