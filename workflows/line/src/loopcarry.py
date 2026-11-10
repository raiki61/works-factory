"""輪（loop_group）の返りを、輪の直後の script が運ぶ欄の名と運び方（docs/design/line.md の 13.1）。標準ライブラリだけ（運び手の
fallback からも読む）。報告を組む collect は落ちうる輪を直に結ばず、ask-before-fix と theme-descend が出力の欄 rounds で運ぶ物を読む。

- ROUNDS: 計画の往復の返り（plan-rounds）のうち、ask-before-fix が運び collect が読む欄。設計の相談の欄 open・text・asked・agreed・talks・
  notes・shown・timeline は運ばない（設計の相談の答えは ask-before-fix の agreed と gates/gate-design.json から報告に出る）
- THEME_ROUNDS: 設計の往復の返り（theme-rounds）のうち、theme-descend が運び collect が読む欄
- carried(raw, names) -> dict | None: 輪の返りの字 raw から names の欄だけを写した dict。object でない・読めない・names の欄が 1 つでも
  無い時は None（欄の欠けた前の版の返りを空と読まない。落ちない）

運ぶ欄を絞る訳: 運び手の出力は collect・request-in・theme-return の入力の環境変数にまるごと乗り、Linux では 1 本が 128KB を越えると
E2BIG で起動が落ちる。request-in と theme-return は欄 rounds を読まない。
"""
import json

ROUNDS = ("done", "ok", "status", "round", "plan_prior", "record", "plan", "fix_plan", "reply", "handoffs", "ripple", "owed", "gave_up",
          "stalled", "capped", "review", "asks", "deviations", "review_status", "review_reason", "stop_reason", "pointed")
THEME_ROUNDS = ("done", "ok", "status", "round", "prior_design", "record", "design", "design_md", "review", "stalled", "capped",
                "review_status", "review_reason", "reason", "stop_reason", "open", "text", "asked", "agreed", "talks", "notes", "shown",
                "timeline")


def carried(raw, names) -> dict | None:
    try:
        got = json.loads(raw) if isinstance(raw, str) and raw.strip() not in ("", "null") else None
    except ValueError:
        return None
    if not isinstance(got, dict) or any(name not in got for name in names):
        return None
    return {name: got[name] for name in names}
