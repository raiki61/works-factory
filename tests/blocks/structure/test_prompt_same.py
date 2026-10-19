"""指示の比べ（docs/design/README.md の 11.4。この block の PR の 1 つ目の commit だけにある試験。2 つ目の commit〔英語にする〕で消す）:
block の prep が組む指示が、今の構造の目の指示（workflows/structure/commands/structure-eye.md に lib/eye.py の render の本文を入れた物）と
空白の違いを除いて同じ字であること。同じ値は、同じ対象に survey を回して置いた structure.json から取る。"""
import json

from tests.blocks import kit
from tests.blocks.structure import test_structure as base

OLD_COMMAND = kit.ROOT / "workflows" / "structure" / "commands" / "structure-eye.md"
SLOT = "$structure-eye-prep.output.prompt"


def squeezed(text: str) -> str:
    return " ".join(text.split())


class SamePromptCase(base._RepoCase):
    def old_prompt(self, rejects=()) -> str:
        eye = kit.load("structure", "eye")   # lib/ を読めるようにする
        import eye as old_eye   # lib/eye.py（今の目）
        doc = json.loads(self.place("structure.json").read_text(encoding="utf-8"))
        body = old_eye.render(doc, eye.rolekit.rejects_text(list(rejects)) if rejects else "")
        return OLD_COMMAND.read_text(encoding="utf-8").replace(SLOT, body.strip())

    def test_first_round(self):
        self.target({"docs/concepts.md": base.CONCEPT_MAP, "docs/concepts.json": json.dumps(base.CONCEPT_TABLE, ensure_ascii=False),
                     "AGENTS.md": "# 対象の決まり\n\n層は下へだけ依存する\n", "POLICY.md": "決まり: 結末の語は report.py だけが持つ\n",
                     "src/report.py": 'OUT = "round_limit"\n', "src/edge.py": 'x = "round_limit"\n'})
        self.survey([{"id": base.MEAN, "paths": ["src/edge.py"], "summary": "境の節が結末の語を書く"},
                     {"id": base.CLAMP, "paths": ["stats.py"], "summary": "上限"}], policy="POLICY.md")
        new = self.run.script("prep")["prompt"]
        self.assertEqual(squeezed(new), squeezed(self.old_prompt()))
        self.assertIn("known_places", new)

    def test_after_rejections(self):
        self.survey()
        self.run.script("prep")
        self.take({"rows": []})
        self.run.script("prep")
        self.take({"rows": []})
        new = self.run.script("prep")["prompt"]
        reasons = kit.load("structure", "eye").rolekit.rejected(self.place(), "structure-eye")
        self.assertEqual(len(reasons), 2)
        self.assertEqual(squeezed(new), squeezed(self.old_prompt(reasons)))
