"""実測役の指示が、今の指示と同じ字か（1 つ目の commit だけの試験。docs/design/premises.md の 7.3。2 つ目の commit で英語にして消す）。

block の prep が組んだ指示から共通の断片 query-rule の字を除いた物と、今の指示（workflows/judge/commands/premises.md）に同じ値を入れた物を、
空白と改行の違いを除いて比べる。今の指示から外す・替える所は設計書の 2.6 の差の一覧のとおり。
"""
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

OLD = kit.ROOT / "workflows" / "judge" / "commands" / "premises.md"
# 例の run の依頼の行（置く値は何でもよい。入れ方が同じかを見る）
FINDINGS = [{"where": "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）",
             "text": "出口の語 deliver=pr の run で PR 用の commit を積む時、commit のフックに渡す環境を作る hook_env は、{x} の字を持つ",
             "measured": "約 380 字"}]
LANG_SENTENCE = "`text` と `measured_how` は {lang} で書け。キー・列挙値・識別子・パス・コマンド・コマンドの出力・エラー文言はそのまま。"
REQUEST_LINE = ("- 人の修正依頼の行: 下の JSON の配列（機械が型を確かめた依頼の行）。各行は `where`・`text` と、任意の `mechanism`・`measured`・"
                "`false_positive_if`。空の配列なら依頼の行の無い run（対象の差分だけを審査する）で、測る主張は無い——`constraints` は"
                "空の配列にせよ。")


def squash(text: str) -> str:
    return "".join(text.split())


def current_prompt(findings: list) -> str:
    """今の指示に、新しい指示と同じ値を入れた物（2.6 の差の一覧のとおりに外す・替える）"""
    lines = OLD.read_text(encoding="utf-8").split("\n")   # 行 n は lines[n - 1]
    keep = [line for n, line in enumerate(lines, 1) if not (n == 1 or 3 <= n <= 10 or 12 <= n <= 22 or n == 40)]
    text = "\n".join(keep)
    text = text.replace("拒んだ理由が次の回の指示書の頭に届く。", "")
    request = f"```json\n{json.dumps(findings, ensure_ascii=False, indent=1)}\n```"
    old_request = next(line for line in keep if line.startswith("- 人の修正依頼の行:"))
    old_target = next(line for line in keep if line.startswith("- 対象リポジトリ:"))
    text = text.replace(old_request, REQUEST_LINE).replace(old_target, f"{old_target}\n\n{request}")
    text = text.replace("依頼を受け付けた時に取った作業ツリーの姿", "役を起こす前に取った作業ツリーの姿")
    text = text.replace("判定役", "後の役")
    return f"{text}\n\n{LANG_SENTENCE}"


class PromptCompareCase(unittest.TestCase):
    def test_new_prompt_is_the_current_prompt(self):
        run = kit.Run(self, "premises")
        (run.repo / "a.txt").write_text("x\n", encoding="utf-8")
        git(run.repo, "add", "-A")
        git(run.repo, "commit", "-q", "-m", "seed")
        run.script("intake", request=json.dumps(FINDINGS, ensure_ascii=False), carried="[]", lang="")
        built = run.script("measure_prep")["prompt"]
        rule = (kit.SHARED / "prompts" / "query-rule.md").read_text(encoding="utf-8").splitlines()
        rule = [line for line in rule if not line.startswith("<!--")]
        del rule[next(i for i, line in enumerate(rule) if line.startswith("- If you start a sub-agent"))]
        head = squash("\n".join(rule))
        self.assertTrue(squash(built).startswith(head), "指示の頭に断片 query-rule が入る")
        lang = (kit.SHARED / "prompts" / "lang-default.md").read_text(encoding="utf-8").strip()
        self.assertEqual(squash(built)[len(head):], squash(current_prompt(FINDINGS).replace("{lang}", lang)))


if __name__ == "__main__":
    unittest.main()
