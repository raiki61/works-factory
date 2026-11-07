"""送った指示から、md の差し込み口ごとの値を取り出す（ページ src/page.py だけが使う。docs/design/viewer.md の 9 章）。md を断片まで開き、空白を 1 つに縮めた上で、決まった字を前から順に探して、
その間を値とする。段落（if）は、その頭の字が次の決まった字より先に見つかれば有ったとみなす"""
import re
from pathlib import Path

SLOT = re.compile(r"\{([a-z0-9_]+)\}")
FRAGMENT = re.compile(r"\{(shared|part):([a-z0-9][a-z0-9_-]*)\}")
MARK = re.compile(r"^<!-- (if|if not|end) ([a-z0-9_]+) -->$")
REQUIRED_FOR = re.compile(r"\A<!-- required-for-(?:tools|fields): [A-Za-z_.]+(?: [A-Za-z_.]+)* -->\n")
OPEN, CLOSE = "\x00", "\x01"
WS = re.compile(r"\s+")


def expand(text, block: Path, shared: Path, depth=0):
    def one(m):
        kind, name = m.groups()
        p = (shared / "prompts" if kind == "shared" else block / "prompts" / "parts") / f"{name}.md"
        try:
            body = p.read_text(encoding="utf-8").rstrip("\n")
        except OSError:
            return m.group(0)
        if kind == "shared":
            body = REQUIRED_FOR.sub("", body + "\n", count=1).rstrip("\n")
        return expand(body, block, shared, depth + 1) if depth < 8 else body
    return FRAGMENT.sub(one, text)


def norm(s):
    """空白の続きを 1 つの空白にした字と、その字の位置 → 元の位置"""
    out, idx, i = [], [], 0
    for m in WS.finditer(s):
        for j in range(i, m.start()):
            out.append(s[j]); idx.append(j)
        out.append(" "); idx.append(m.start())
        i = m.end()
    for j in range(i, len(s)):
        out.append(s[j]); idx.append(j)
    idx.append(len(s))
    return "".join(out), idx


def tokens(text):
    """[("lit", 字) | ("slot", 名) | ("opt", [..])]"""
    def body(seg):
        o = []
        for i, p in enumerate(SLOT.split(seg)):
            if i % 2:
                o.append(("slot", p))
            else:
                p = WS.sub(" ", p.replace(OPEN, "{").replace(CLOSE, "}")).strip()
                if p:
                    o.append(("lit", p))
        return o
    out, buf = [], []
    for line in text.split("\n"):
        m = MARK.match(line.strip())
        if not m:
            buf.append(line); continue
        seg = body("\n".join(buf)); buf = []
        if m.group(1) == "end":
            out.append(("opt", seg))
        else:
            out.extend(seg)
    out.extend(body("\n".join(buf)))
    return out


def first_lit(toks):
    for t in toks:
        if t[0] == "lit":
            return t[1]
        if t[0] == "opt":
            continue
    return None


class Miss(Exception):
    pass


def walk(toks, ns, st, follow):
    for i, t in enumerate(toks):
        if t[0] == "lit":
            L = t[1]
            if st["pending"] is not None:
                j = ns.find(L, st["pos"])
                if j < 0:
                    raise Miss(L[:60])
                st["out"].append((st["pending"], st["pos"], j)); st["pending"] = None
            else:
                j = st["pos"]
                while j < len(ns) and ns[j] == " ":
                    j += 1
                if not ns.startswith(L, j):
                    raise Miss(L[:60])
            st["pos"] = j + len(L)
        elif t[0] == "slot":
            if st["pending"] is not None:
                st["out"].append((st["pending"], st["pos"], st["pos"]))
            st["pending"] = t[1]
        else:
            head = first_lit(t[1])
            after = first_lit(toks[i + 1:]) or follow
            if head is None:
                continue
            a = ns.find(head, st["pos"])
            b = ns.find(after, st["pos"]) if after else -1
            if a >= 0 and (b < 0 or a <= b):
                save = dict(st, out=list(st["out"]))
                try:
                    walk(t[1], ns, st, after)
                except Miss:
                    st.clear(); st.update(save)


def values(md_text, md_file, pack: Path, sent: str):
    """返り: [(名, 値の始め, 値の終わり)]（元の字の位置）か None（合わない）"""
    f = Path(md_file)
    f = f if f.is_absolute() else pack / f
    block = f.parent.parent if f.parent.name == "prompts" else f.parent.parent.parent
    text = expand(md_text, block, pack / ".shared").replace("{{", OPEN).replace("}}", CLOSE)
    ns, idx = norm(sent)
    st = {"pos": 0, "pending": None, "out": []}
    try:
        walk(tokens(text), ns, st, None)
    except Miss as m:
        values.last = str(m)
        return None
    if st["pending"] is not None:
        st["out"].append((st["pending"], st["pos"], len(ns.rstrip())))
    res = []
    for n, a, b in st["out"]:
        while a < b and ns[a] == " ":
            a += 1
        while b > a and ns[b - 1] == " ":
            b -= 1
        res.append((n, idx[a], idx[b - 1] + 1 if b > a else idx[a]))
    return res
