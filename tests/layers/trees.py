"""試験の中で、小さな木を一時のフォルダに書き、木の中の `AGENTS.md` を git の一覧から集める。

`tree(files, git_init=True)` は、書く前に一時の根を git のリポジトリにする。そこでは利用者の大域の無視の表
（`~/.config/git/ignore` など）を切る（`core.excludesFile` を空の場所へ向ける）ので、走らせた人の設定で `AGENTS.md` が
隠れて結果が変わることがない。本物の木 `ROOT` を読む呼びは、利用者の設定を効かせたまま git の一覧を引く
（手元の clone が無視している物を、CI の新しい clone と同じく読まない）。
"""
import contextlib
import os
import pathlib
import tempfile

from tests.bin import gitkit


@contextlib.contextmanager
def tree(files: dict[str, str | bytes], git_init: bool = False):
    """`{根からのパス: 中身}` を書いた一時の根を渡す。`bytes` はそのまま書く（UTF-8 で読めない字の試験）。
    `git_init` が真なら、ファイルを書く前に根を git のリポジトリにする（書いたファイルは未追跡のまま `agents_files` に出る）"""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        if git_init:
            gitkit.git(root, "init", "-q")
            gitkit.git(root, "config", "core.excludesFile", os.devnull)
        for rel, body in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                path.write_bytes(body)
            else:
                path.write_text(body, encoding="utf-8")
        yield root


def agents_files(root: pathlib.Path) -> list[pathlib.Path]:
    """git が知る（追跡中と、無視されない未追跡の）どの階層の `AGENTS.md` も、名の順に `root` からのパスで返す。
    `.git` の中と、無視される追跡外のフォルダの写しは含まない。追跡して作業木から消した物は返さない。
    根が git のリポジトリでない時は `CalledProcessError` が上がる（根から歩く形には戻さない）"""
    root = pathlib.Path(root)
    return sorted(p for p in (root / rel for rel in gitkit.known_files(root))
                  if p.name == "AGENTS.md" and p.is_file())
