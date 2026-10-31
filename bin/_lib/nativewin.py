"""素の Windows（WSL2 を使わない Windows）で、入口を部品の読み込みの前に 1 行の訳で止める。入口（bin/works-factory・bin/apply）は
Python の版を照らした後、ほかの部品を読む前に stop(<入口の名>) を呼ぶ。この部品は標準の sys だけを読む。

止める訳は 2 つ。
- 素の Windows では Claude Code の sandbox が効かず、コマンドは sandbox の外で走る（https://code.claude.com/docs/en/sandboxing の
  「On native Windows, Claude Code runs commands unsandboxed.」）。workflows/.shared/fence.py の書き込みの制限が黙って外れる。
- Archon も、git worktree とシェルの段には WSL2 が要ると書いている（Archon の docs の deployment/windows.md）。
WSL2 の中は Linux（sys.platform が linux）なので止めない。Cygwin・MSYS2 の Python も、上で走る Claude Code は素の Windows の物なので止める。
"""
import sys

NATIVE = ("win32", "cygwin", "msys")   # 素の Windows の上の Python が名乗る sys.platform
CODE = 2
MESSAGE = ("{name}: 素の Windows では動かない（Claude Code の sandbox が効かず書き込みの制限が外れる・Archon が git worktree とシェルの段に"
           " WSL2 を要る）。WSL2 を入れ（wsl --install）、WSL の中の Linux に工場を clone してそこから打つ")


def stop(name: str) -> None:
    """素の Windows なら訳を標準エラーに 1 行出して、終わりのコード CODE で終える。それ以外では何もしない"""
    if sys.platform in NATIVE:
        print(MESSAGE.format(name=name), file=sys.stderr)
        sys.exit(CODE)
