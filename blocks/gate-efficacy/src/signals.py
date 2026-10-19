"""ゲートの印（docs/design/gate-efficacy.md の 1.5）: 差分に機械が見る「ゲートに触れた」印。

ゲートの定義のファイル（テスト・CI・pre-commit・フック・lint・試験の設定・変異の腕の一覧の宣言など）と、assert を足す・消す行。
印が 1 つも無い差分でだけ、役の『条件に当たらない』を受ける（viewpoint.judged_na）。機械には差分の分岐がゲートかを決められないので、
印が在れば役に測らせる側に倒す。元 lib/judge_accept.py の gate_signals と GATE_FILE_PATTERNS（元 works/.shared/core/entry.py）。
"""
import re

import checkscope  # lib/

# 検証ゲートの定義のファイル（テスト・CI・pre-commit・フック・lint・試験の設定・変異の腕の一覧）。広めに当てる——当たり過ぎは
# 役に測らせるだけで、当たり漏れが役の『条件外』を通す。試験の実行器の名の 2 つの設定ファイル（.ini）は言語の中立の語の表に当たるので、
# *.ini と *.cfg を全部当てる形に広げた
GATE_FILE_PATTERNS = (
    r"(^|/)tests?/", r"(^|/)__tests__/", r"(^|/)spec/", r"(^|/)test_[^/]*$", r"_test\.[^/]+$", r"\.(test|spec)\.[^/]+$",
    r"(^|/)conftest\.py$", r"^\.github/", r"(^|/)\.gitlab-ci\.ya?ml$", r"^\.circleci/", r"(^|/)Jenkinsfile$",
    r"(^|/)\.travis\.ya?ml$", r"(^|/)azure-pipelines\.ya?ml$", r"^\.buildkite/", r"(^|/)\.pre-commit-config\.ya?ml$",
    r"^\.husky/", r"(^|/)lefthook\.ya?ml$", r"(^|/)\.?githooks/", r"(^|/)hooks/", r"(^|/)\.review-checks\.json$",
    r"(^|/)[^/]+\.(ini|cfg)$", r"(^|/)(noxfile\.py|pyproject\.toml|Makefile|justfile|package\.json)$",
    r"(^|/)(\.flake8|\.?ruff\.toml|\.pylintrc|\.eslintrc[^/]*|eslint\.config\.[^/]+|\.shellcheckrc|\.golangci\.ya?ml)$",
    rf"(^|/){re.escape(checkscope.SCOPE_DECL)}$",   # works の範囲の宣言（宣言の段を外す所を決める）
)
GATE_FILES = tuple(re.compile(p) for p in GATE_FILE_PATTERNS)
ASSERT_LINE = re.compile(r"^[+-](?![+-]{2} ).*\bassert", re.M)   # 足す・消す行（ファイルの頭の +++ / --- を除く）


def gate_signals(changed_files, diff_text: str) -> list:
    """差分に機械が見るゲートの印の一覧（空なら印が無い）: ゲートの定義のファイルと、assert を足す・消す行"""
    hits = [f"ゲートの定義のファイル {f}" for f in changed_files if any(p.search(f) for p in GATE_FILES)]
    hits += [f"assert の行 {m.group(0)[:80]!r}" for m in ASSERT_LINE.finditer(diff_text or "")]
    return hits


def signals_of(view):
    """view の差分から gate_signals。差分を読めなければ None（印の有無を言えない。役の『条件外』を受けない側に倒す）"""
    try:
        with open(view.diff_file, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except (TypeError, OSError):
        return None
    return gate_signals(list(view.changed_files), text)
