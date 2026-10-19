"""報告の節「仕様」の行（docs/design/spec.md の 9 節）。事実を持つ block が組む。"""


def _exit(a: dict) -> str:
    code = a.get("exit_at_approval")
    if code is None:
        return f"走らない（{a.get('run_error') or '理由の記録が無い'}）"
    return "既に緑（赤を見ていない）" if code == 0 else f"exit {code}"


def approved(spec: dict) -> list:
    note = str((spec.get("approval") or {}).get("note") or "").strip()
    head = f"仕様: 要件 {len(spec['requirements'])} 件・受け入れ条件 {len(spec['acceptance'])} 件を人が承認した" + (f"（一言: {note}）" if note else "")
    return [head] + [f"- {a['key']}（要件 {a['requirement']}）: {a['file']} の {a['name']}——承認の時 {_exit(a)}" for a in spec["acceptance"]]


def stopped(reason: str) -> list:
    return [f"仕様: 人が承認ノードで止めた: {reason}"]


def failed(reason: str) -> list:
    return [f"仕様: 固まらなかった（{reason}）"]


def checked(questions: list, unchecked: bool) -> list:
    if not questions:
        return ["仕様: 承認した受け入れ条件のテストは承認の版のまま"]
    head = "受け入れ条件のテストが変わったかを照らせなかった" if unchecked else f"承認し直すかの問い {len(questions)} 件"
    return [f"仕様: {head}"] + [f"- {q}" for q in questions]
