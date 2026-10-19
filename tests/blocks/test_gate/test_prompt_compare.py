"""指示の比べ（docs/design/README.md の 11.4。1 つ目の commit の試験。2 つ目の commit で消す）。

この block の prep が組む 3 つの指示が、今の工場の指示（workflows/test-gate/commands/ci.md・suite-write.md と、出し直しの指示書
rolekit.write_resubmit が書く物）に同じ値を差し込んだ字と、空白を除いて同じ。
"""
import json
import pathlib
import re

from tests.blocks.test_gate import test_test_gate as base
from tests.blocks import kit

ROOT = base.ROOT
COMMANDS = ROOT / "workflows" / "test-gate" / "commands"
rolekit = base.rolekit
declared_checks = base.declared_checks


def squashed(text: str) -> str:
    return re.sub(r"\s+", "", text)


def filled(command: str, node: str, values: dict) -> str:
    """今の指示（commands/<command>.md）の $<node>.output.<欄> に値を差し込む"""
    text = (COMMANDS / f"{command}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(f"$ {node}.output.{key}".replace("$ ", "$"), str(value))
    return text


class CompareCase(base.ScriptCase):
    def snap(self) -> dict:
        return json.loads((self.place("base") / "ci-snapshot.json").read_text(encoding="utf-8"))

    def test_ci_prompt_equals_the_current_command_filled_with_the_same_values(self):
        for reject in ("", "前の理由: 欄を直せ $ci.output.material と $INPUTS.mode"):
            with self.subTest(reject=reject):
                self.write_start(base=self.head)
                self.intake("base")
                if reject:
                    rolekit.with_done(self.place("base"), declared_checks.CI_ROLE, {"ok": False, "reason": reject})
                got = self.ok("ci_prep", "base")
                snap = self.snap()
                self.addCleanup(base.shutil.rmtree, pathlib.Path(snap["top"]), True)
                rejects = rolekit.rejected(self.place("base"), declared_checks.CI_ROLE)
                expected = filled("ci", "ci-prep", {"reject": rolekit.rejects_text(rejects), "root": self.repo.resolve(),
                                                    "base_rev": self.head, "copy_dir": snap["copy_dir"], "tmp_dir": snap["tmp_dir"],
                                                    "mode": "base", "attempt": len(rejects) + 1})
                self.assertEqual(squashed(got["prompt"]), squashed(expected))
                rolekit.rejects_path(self.place("base"), declared_checks.CI_ROLE).unlink(missing_ok=True)

    def test_ci_fix_prompt_equals_the_current_resubmit_brief(self):
        reason = "素材の欄 material を丸ごと直して出し直せ: final の not_run には systems が要る\n```\n囲いの字"
        self.intake("base")
        place = self.place("base")
        rolekit.with_done(place, declared_checks.CI_ROLE, {"ok": False, "reason": reason})
        place.joinpath("candidate-ci.json").write_text('{"material": {}}', encoding="utf-8")
        got = self.ok("ci_fix_prep", "base")
        path, _ = rolekit.write_resubmit(place, declared_checks.CI_ROLE, "compare-{n}.md", rolekit.FIELD_RULES)
        self.assertEqual(squashed(got["prompt"]), squashed(path.read_text(encoding="utf-8")))

    def test_suite_write_prompt_equals_the_current_command_filled_with_the_same_values(self):
        self.write_start(test_cmd="make test")
        self.ok("run", "base")
        got = self.ok("suite_prep", "base")
        brief = self.place("base") / "suite" / "writer-brief.md"
        expected = filled("suite-write", "suite-prep", {"brief_file": brief.resolve()})
        self.assertEqual(squashed(got["prompt"]), squashed(expected))
