"""診断の block の試験の助け（試験のモジュールではない）: 種のリポジトリ（tests/e2e/target-seed）を commit した使い捨ての対象と、
block の src を読み込む口。"""
import pathlib
import shutil

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = "diagnose"
SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
REQUEST = [{"where": "stats.py", "text": "mean([1, 2, 3]) が 2 でなく 3 を返す。test_mean_of_three が赤"},
           {"where": "stats.py", "text": "clamp(15, 0, 10) が 10 でなく 0 を返す。test_clamp_above_range が赤"}]


def seeded(run) -> None:
    """run の作業ツリーに種を写して commit する"""
    shutil.copytree(SEED, run.repo, dirs_exist_ok=True)
    git(run.repo, "add", "-A")
    git(run.repo, "commit", "-q", "-m", "seed")


def modules():
    """block の src の module（files・judge・rejudge・inputs・exit・report）を、この過程に読み込んで返す"""
    import importlib
    kit.load(BLOCK, "files")
    return {name: importlib.import_module(f"src.{name}") for name in ("files", "judge", "rejudge", "inputs", "exit", "report")}


def unit(key, patterns, counts, total, label="block", disposition="do-now"):
    return {"key": key, "label": label, "disposition": disposition,
            "reason": f"事実: {key}。反証: 意図の取り違えを当たったが、関数名とテストが逆を期待する",
            "origin_analysis": "写し間違いの形",
            "why_chain": ["テストが境界の値を試していない"],
            "class_query": {"how": {"patterns": patterns, "fixed": True, "paths": ["stats.py"], "count": "lines"},
                            "counts": counts, "total": total}}


def judge_ok():
    """良い判定の見本（開いた単位 2 つ・先行例つき）"""
    return {
        "framing": "依頼の 2 件はどちらも stats.py の算術の取り違え",
        "one_shot": "mean の分母を len(xs) に、clamp の上限の枝の戻り値を hi に直す",
        "units": [unit(MEAN, ["(len(xs) - 1)"], "defects", 1), unit(CLAMP, ["return lo"], "population", 2)],
        "questions": [], "materials_missing": [], "carried_r1": [],
        "one_shot_closes": [MEAN, CLAMP],
        "precedents": [
            {"key": MEAN, "problem": "数列の算術平均を求める", "source": "Python の statistics.mean の文書の節",
             "verdict": "adopt", "reason": "分母はデータ点の数 len(xs)"},
            {"key": CLAMP, "problem": "値を下限と上限の間に収める", "source": "numpy.clip の文書の節",
             "verdict": "adopt", "reason": "上限を超えた値は上限に置き換える"}],
    }
