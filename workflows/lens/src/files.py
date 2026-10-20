"""lens の block のファイルの名（docs/design/lens.md の 1.4）。名はこのモジュールだけが持つ。

place は ports.place()（単独の run では run の根、line から include された時は lens/ の下）。入口が名で引いて消してよいのは、
ここの名と <レンズ>-prompt-*.md、<レンズ>の返答 reply-<key>.json だけ。
"""
import ports

INTAKE = "intake.json"
DIFF = "lens.diff"
ERRORS = "errors.json"
SKIP = (ports.RUNTIME_COPY_PREFIX,)   # 差分に数えない（Archon が run の作業ツリーに写す置き場）


def reply(key: str) -> str:
    return f"reply-{key}.json"


def prompts(lens: str) -> str:
    return f"{lens}-prompt-*.md"
