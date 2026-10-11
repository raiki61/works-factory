"""試験の中で、小さな木を一時のフォルダに書く。"""
import contextlib
import pathlib
import tempfile


@contextlib.contextmanager
def tree(files: dict[str, str | bytes]):
    """`{根からのパス: 中身}` を書いた一時の根を渡す。`bytes` はそのまま書く（UTF-8 で読めない字の試験）"""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for rel, body in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                path.write_bytes(body)
            else:
                path.write_text(body, encoding="utf-8")
        yield root
