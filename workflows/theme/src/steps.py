"""theme の block の中身（docs/design/theme.md）。入口・指示の値・受け付け・出口。指示の文は prompts/theme-writer.md と
prompts/theme-writer-fix.md が持ち、ここは材料と値だけを組む。"""
from __future__ import annotations

import pathlib

import ports
import prompt

import converge    # lib/。held・owed_faces・answer_gaps
import eyekit      # lib/。断片 policy の本文 policy_body・断片 recorded-policy の値 recorded_rows_text
import jsonfile    # lib/
import oneline     # lib/
import rolekit     # lib/。却下の控え・出し直し・諦め
import worldmark   # lib/。rows・WEB

from src import check, files, render

NOT_RUN = "書き手の loop が回らなかった"
CRASHED = "{step} の node が落ちた（{why}）"
NO_DESIGN = "受け付けを通った設計の案が無い"
WORLD_WORDS = {worldmark.SAME: "same as the practice", worldmark.DIFFERS: "differs from the practice",
               worldmark.NONE: "the theme shows no approach"}


# ---------------------------------------------------------------- 入口
def _port(name: str, read):
    try:
        return read()
    except (ValueError, OSError) as e:
        raise ValueError(f"入力 {name}: {e}") from None


def _blank(raw) -> bool:
    return not ports.text(raw).strip() or ports.text(raw).strip() == "null"


def intake(place, k: int, raw: dict) -> dict:
    """port を読み、周のフォルダ r<k>/ を開いて intake.json を書く。返答 {due, round, reason}。読めない port は due 偽と訳。落ちない"""
    folder = files.round_dir(place, k)
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"theme": "", "prior": "", "prior_design": "", "answers": [], "world": [], "policy": "", "recorded": [], "base": "", "lang": "",
           "due": False, "reason": ""}
    try:
        for name in files.OWN_FILES:
            (folder / name).unlink(missing_ok=True)
        theme = _port("theme", lambda: ports.file(raw.get("theme"), "file"))
        if theme is None:
            raise ValueError("入力 theme: テーマの md が渡されていない")
        _port("theme", lambda: theme.read_text(encoding="utf-8"))
        doc["theme"] = str(theme)
        if not _blank(raw.get("prior")):
            prior = _port("prior", lambda: ports.json(raw["prior"], "shared:plan-converge.schema.json"))
            doc["prior"] = str(files.write_json(folder / files.PRIOR, prior))
        if not _blank(raw.get("prior_design")):
            got = _port("prior_design", lambda: ports.json(raw["prior_design"], "shared:theme-design.schema.json"))
            doc["prior_design"] = str(files.write_json(folder / files.PRIOR_DESIGN, got))
        if not _blank(raw.get("answers")):
            doc["answers"] = _port("answers", lambda: ports.json(raw["answers"], "shared:human-answers.schema.json"))
            ids = [a["id"] for a in doc["answers"]]
            if len(set(ids)) != len(ids):
                raise ValueError(f"入力 answers: 人の答えの id が重なる（{', '.join(ids)}）")
        world = _port("world_rows", lambda: ports.file(raw.get("world_rows"), "jsonl(lib:world-row.schema.json)"))
        doc["world"] = _port("world_rows", lambda: worldmark.rows(world)) if world is not None else []
        policy_path = _port("policy", lambda: ports.file(raw.get("policy"), "file"))
        doc["policy"] = str(policy_path) if policy_path is not None else ""
        if not _blank(raw.get("recorded")):
            doc["recorded"] = _port("recorded", lambda: ports.json(raw["recorded"], "shared:recorded.schema.json"))
        doc["base"], doc["lang"] = ports.text(raw.get("base")).strip(), ports.text(raw.get("lang")).strip()
        doc.update(due=True, reason="")
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        doc.update(due=False, reason=oneline.one_line(f"{type(e).__name__}: {e}"))
    files.write_json(folder / files.INTAKE, doc)
    return {"due": doc["due"], "round": k, "reason": doc["reason"]}


def load(place) -> tuple[pathlib.Path, dict]:
    """(今の周のフォルダ, intake.json)。無い・読めなければ ValueError"""
    folder = files.folder(place)
    doc = files.read_json(folder / files.INTAKE)
    if not isinstance(doc, dict):
        raise ValueError(f"{folder / files.INTAKE} が無いか読めない（入口の node が走っていない）")
    return folder, doc


def prior_of(ctx: dict) -> dict | None:
    return files.read_json(ctx["prior"]) if ctx.get("prior") else None


# ---------------------------------------------------------------- 指示の値
def numbered(text: str) -> str:
    return "\n".join(f"{n:>4}  {line}" for n, line in enumerate(text.splitlines(), 1))


def owed_rows(prior: dict | None) -> str:
    """前の往復の答えの要る穴（converge.owed_faces）の行。1 件 1 行"""
    row = converge.held(prior) if prior else None
    owed = converge.owed_faces(prior, row) if row else []
    return "\n".join(f"- `{f['key']}` ({f['severity']}, {f.get('kind') or '-'}) at {oneline.one_line(f.get('where') or '-')}: "
                     f"{oneline.one_line(f.get('why') or '')}" for f in owed)


def answer_rows(answers: list) -> str:
    out = []
    for a in answers:
        tail = (f" (answers {a['ask']} with {a['pick']})" if a.get("ask") and a.get("pick") else "") + (f" [from {a['from']}]" if a.get("from") else "")
        out.append(f"- {a['id']} ({a['kind']}){tail}: {a['text']}")
    return "\n".join(out)


def world_rows(rows: list) -> str:
    rows = sorted((r for r in rows if isinstance(r, dict)), key=lambda r: (r.get("versus") or {}).get("verdict") != worldmark.DIFFERS)
    out = []
    for r in rows:
        v = r.get("versus") or {}
        urls = ", ".join(str(s.get("url")) for s in r.get("sources") or [] if isinstance(s, dict) and s.get("url")) or "none"
        mark = "" if r.get("basis") == worldmark.WEB else " (not confirmed on the web)"
        out.append(f"- {r.get('problem')}: practice {r.get('practice')}{mark} (sources: {urls})"
                   f" · versus {WORLD_WORDS.get(v.get('verdict'), v.get('verdict'))}"
                   + (f" · challenge {v.get('challenge')}" if v.get("challenge") else ""))
    return "\n".join(out)


def values(folder: pathlib.Path, ctx: dict) -> tuple[dict, dict]:
    """書き手の指示の値と段落の真偽"""
    theme = pathlib.Path(ctx["theme"]).read_text(encoding="utf-8")
    rejected = rolekit.rejected(folder, files.ROLE)
    owed = owed_rows(prior_of(ctx))
    recorded, recorded_none = eyekit.recorded_rows_text(ctx["recorded"])
    v = {"rejection": rolekit.rejects_text(rejected), "theme_file": ctx["theme"], "theme_text": numbered(theme),
         "prior_design_file": ctx["prior_design"], "owed_rows": owed, "answer_rows": answer_rows(ctx["answers"]),
         "world_rows": world_rows(ctx["world"]), "policy_body": eyekit.policy_body(ctx["policy"]),
         "recorded_rows": recorded, "base_rev": ctx["base"] or "HEAD", "lang": prompt.lang(ctx["lang"])}
    w = {"rejected": bool(rejected), "prior_design": bool(ctx["prior_design"]), "owed": bool(owed), "answers": bool(ctx["answers"]),
         "world": bool(ctx["world"]), "policy": bool(ctx["policy"]), "recorded_none": recorded_none, "spawns": False}
    return v, w


def prep(place, prev) -> dict:
    """書き手の指示を組む（返答 {prompt, resubmit}）。前の回の受け付けが拒み、合わせた答えの控えが在れば（rolekit.resubmitting）出し直しの役を
    起こすので指示は組まない"""
    folder, ctx = load(place)
    if rolekit.resubmitting(folder, files.ROLE, prev):
        return {"prompt": "", "resubmit": True}
    v, w = values(folder, ctx)
    return {"prompt": prompt.emit(files.WRITER, v, w, prompt.round_of(files.WRITER))["prompt"], "resubmit": False}


def fix_prep(place) -> dict:
    """出し直しの役の指示を組む（最後の拒否の理由と、合わせた前の答えの控えのパス）。返答 {prompt}"""
    folder, _ = load(place)
    rejected = rolekit.rejected(folder, files.ROLE)
    vals = {"rejection": rejected[-1] if rejected else "", "candidate": str(rolekit.candidate_path(folder, files.ROLE))}
    return {"prompt": prompt.emit(files.FIXER, vals, {"spawns": False}, prompt.round_of(files.FIXER))["prompt"]}


# ---------------------------------------------------------------- 受け付け
def value(raw):
    """役の返答の JSON の値。null・空・無い入力は None。JSON でなければ字のまま（受け付けが『JSON として読めない』と拒む）"""
    try:
        return ports.parsed(raw)
    except ValueError:
        return raw


def accept(place, repo, reply, fix_reply) -> dict:
    """書き手（か出し直しの役）の返答を受け付ける。出し直しは前の答えの控えと合わせてから全体を照らす（rolekit.resubmitted）。
    通れば design.json と design.md を置く。拒否は控えに積み、rolekit.GIVE_UP_AFTER 回目で done・give_up。返答 {ok, done, give_up, reason}"""
    folder, ctx = load(place)
    got, why = rolekit.resubmitted(folder, files.ROLE, reply, fix_reply, rolekit.merge_fields, required=files.REQUIRED)
    if got is None:
        out = {"ok": False, "reason": why}
    else:
        theme_lines = pathlib.Path(ctx["theme"]).read_text(encoding="utf-8").splitlines()
        gaps = check.gaps(got, repo=repo, base=ctx["base"], theme_lines=theme_lines, answer_ids=[a["id"] for a in ctx["answers"]],
                          prior=prior_of(ctx))
        if gaps:
            out = {"ok": False, "reason": "設計の案が受け付けを通らない:\n" + "\n".join(f"- {g}" for g in gaps)}
        else:
            files.write_json(folder / files.DESIGN, got)
            (folder / files.DESIGN_MD).write_text(render.md(got), encoding="utf-8")
            out = {"ok": True, "reason": ""}
    return rolekit.round_outcome(rolekit.accept_round(folder, files.ROLE, None, lambda _: out))


# ---------------------------------------------------------------- 出口
def record_crash(place, step: str, why: str) -> None:
    """prep・accept の node が落ちた訳を周のフォルダに残す（出口が読む。ここ自体は落ちない）"""
    try:
        files.write_json(files.folder(place) / files.CRASH, {"step": step, "why": oneline.one_line(why)})
    except Exception:  # noqa: BLE001 — 落ちた訳を残す口が落ちても、元の誤りを隠さない
        pass


def result(status: str, reason: str, folder: pathlib.Path | None = None, made: dict | None = None) -> dict:
    """block の返答。ok は status が ok か"""
    lines = report_lines(status, reason, made)
    return {"ok": status == "ok", "status": status,
            "design": ports.pointer(folder / files.DESIGN, "json(shared:theme-design.schema.json)") if made else None,
            "design_md": ports.pointer(folder / files.DESIGN_MD, "file") if made else None,
            "reason": reason, "report": lines}


def report_lines(status: str, reason: str, made: dict | None) -> list[str]:
    """報告に載せる日本語の行（docs/design/theme.md の 10 章）"""
    if status != "ok" or not made:
        return [f"設計の案: {reason}"]
    return [f"設計の案: 問い {len(made['asks'])}・部署の決め {len(made['decided'])}・変える所 {len(made['changes'])}"
            f"（作り変え {sum(1 for c in made['changes'] if c['op'] == 'rework')}）・作り変えの照らしの行 {len(made['inventory'])}"]


def finish(place) -> dict:
    """block の返答 {ok, status, design, design_md, reason, report}。finish.json にも写す。落ちる道は scripts/finish.py の fallback"""
    folder = files.folder(place)
    ctx = files.read_json(folder / files.INTAKE)
    made = jsonfile.read_or(folder / files.DESIGN)
    if not isinstance(ctx, dict):
        got = result("failed", "入口の控えが無い（入口の node が落ちた）")
    elif not ctx.get("due"):
        got = result("failed", str(ctx.get("reason") or "入口が書き手を起こさなかった"))
    elif isinstance(made, dict) and (folder / files.DESIGN_MD).is_file():
        got = result("ok", "", folder, made)
    else:
        crash = files.read_json(folder / files.CRASH)
        gave_up = rolekit.given_up_reason(folder, files.ROLE)
        if isinstance(crash, dict) and crash.get("why"):
            got = result("failed", f"{NO_DESIGN}: " + CRASHED.format(step=crash.get("step") or "?", why=crash["why"]))
        elif gave_up:
            got = result("gave_up", f"{NO_DESIGN}: {gave_up}")
        elif rejected := rolekit.rejected(folder, files.ROLE):
            got = result("failed", f"{NO_DESIGN}: 最後の拒否は「{oneline.one_line(rejected[-1])}」")
        else:
            got = result("failed", f"{NO_DESIGN}: {NOT_RUN}")
    files.write_json(folder / files.FINISH, got)
    return got

