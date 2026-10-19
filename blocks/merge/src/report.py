"""報告に載せる日本語の行（docs/design/merge.md の 9 節）。lib/runreport.py が merge の返りから組んでいた行のうち、この block の事実だけで
決まる物を同じ字で組む。守りの当たりの行と bin/apply の打ち方の行は、ほかの block の事実と合わせて決まるので入れない（欄で返す）。"""
import oneline  # lib/
import seal  # lib/

PR_MADE = "PR を作った: "
PR_STOPPED = "PR を作らずに止めた: "
PR_UNCONFIRMED = "PR を作ったと確かめられなかった: "
PR_COMMITS = "PR の commit: "
DOING = {"seal": "封じ", "apply": "置き", "check": "照らし"}


def _commit_lines(deliver: dict) -> list:
    commits = [c for c in deliver.get("commits") or [] if isinstance(c, dict)]
    if commits:
        return [f"{PR_COMMITS}修正案の項目ごとに {len(commits)} 本（依存の順。各 commit の時点で試験が通るかは確かめていない。確かめたのは"
                "積み終えた木の差分の hash）",
                *(f"項目 {c.get('item')}: {str(c.get('head'))[:12]}（{oneline.one_line(c.get('subject') or '')}）" for c in commits)]
    split = deliver.get("split")
    return [f"{PR_COMMITS}項目ごとに分けなかった（{oneline.one_line(split)}）"] if isinstance(split, str) and split else []


def _delivery_lines(deliver: dict) -> list:
    act = deliver.get("act")
    if act == "pr":
        pr = deliver.get("pr") or {}
        kind = "下書きの PR" if pr.get("is_draft") else "PR"
        head = [f"{PR_MADE}{pr.get('url')}（{kind} #{pr.get('number')}。merge は対象のレビューと決まりに任せる）"]
    elif act in ("stopped", "unconfirmed"):
        word = PR_STOPPED if act == "stopped" else PR_UNCONFIRMED
        head = [f"{word}{oneline.one_line(deliver.get('reason') or '訳の記録が無い')}"]
    else:
        head = []
    return [*head, *_commit_lines(deliver)]


def _deleted_lines(sealed_diff) -> list:
    try:
        text = sealed_diff.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return [f"{seal.DELETED_HEAD}: 封じた差分が読めない（{oneline.one_line(error)}）"]
    return seal.deleted_lines(seal.deleted_paths(text), where=str(sealed_diff))


def lines(place: dict, deliver, sealed_diff) -> list:
    """place は照らしの node の返り、deliver は渡し方（seal は None）、sealed_diff は封じた差分の実のパス"""
    mode = place.get("mode")
    out = []
    if place.get("ok") is not True:
        out.append(f"差分の{DOING.get(mode, mode)}（{mode}）が ok でない: {oneline.one_line(place.get('reason') or '訳の記録が無い')}")
    if mode == "seal" and place.get("diff"):
        out += _deleted_lines(sealed_diff)
    if isinstance(deliver, dict):
        out += _delivery_lines(deliver)
    return out
