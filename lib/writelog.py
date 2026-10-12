"""書き込みの記録（writes.jsonl）の置き場の決め方の 1 か所。作業の場ごとの置き場の決め方（鍵・控え・片付け）は、読んだ証拠の
記録（lib/reads.py の reads.jsonl。根は別の works-reads）も同じ物を使う。

記録のフック（bin/_lib/record-write.py。Claude の設定の PostToolUse:Edit|Write|NotebookEdit）が書き、書く役の受け付け
（writes.check）が読む。フックは道具の呼び出しのたびに起きるので、このモジュールは標準ライブラリだけを読む（重い部品を import しない）。

- ROOT: 記録の根の名（Claude の設定の置き場の下。起動が作り、無ければ記録の無い run）
- root(config_dir) -> Path: Claude の設定の置き場 config_dir の下の記録の根
- log_path(root, cwd, name=LOG) -> Path: 根 root の下の、役の作業の場 cwd（実パス）ごとの記録のファイル name
- open_log(root, cwd, name=LOG) -> Path: log_path の置き場を作り、作業の場の実パスを控え（WHERE）に書いて記録のファイルを返す
- log_here(cwd=None)・open_here(): このプロセスの Claude の設定の置き場（CLAUDE_CONFIG_DIR）の下の、作業の場 cwd（既定は今の cwd）の
  記録のファイルと、その記録を空で作る口。記録の根が無い起動は None・何もしない（記録の無い run）
- sweep(root) -> (list[Path], list[OSError]): 控えの作業の場がもう無い置き場を消し、消した置き場と消せなかった置き場の誤りを返す
  （控えの無い・控えが名と合わない置き場は残す。1 つ消せなくても残りは片付ける）
"""
import hashlib
import os
import pathlib
import shutil

ROOT = "works-writes"
LOG = "writes.jsonl"
KEY_LEN = 16   # cwd の実パスの sha256 の頭の字数（置き場のフォルダの名）
WHERE = "cwd"  # 置き場のフォルダの名は戻せない hash なので、持ち主の作業の場の実パスを横に控える（sweep が読む）


def root(config_dir) -> pathlib.Path:
    return pathlib.Path(config_dir) / ROOT


def _key(cwd) -> str:
    return hashlib.sha256(os.path.realpath(str(cwd)).encode("utf-8", "surrogateescape")).hexdigest()[:KEY_LEN]


def log_path(root, cwd, name: str = LOG) -> pathlib.Path:
    return pathlib.Path(root) / _key(cwd) / name


def open_log(root, cwd, name: str = LOG) -> pathlib.Path:
    log = log_path(root, cwd, name)
    log.parent.mkdir(exist_ok=True)
    where = log.parent / WHERE
    if not where.exists():
        where.write_text(os.path.realpath(str(cwd)), encoding="utf-8", errors="surrogateescape")
    return log


def _here_root() -> pathlib.Path | None:
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    found = root(config) if config else None
    return found if found is not None and found.is_dir() else None


def log_here(cwd=None) -> pathlib.Path | None:
    """書き込みの記録のフックが作業の場 cwd（既定は今の cwd）の Edit・Write を残すファイル。記録の根（起動が隔離した設定
    CLAUDE_CONFIG_DIR の下に作る）が無い起動は None で、受け付けは記録の無い run の道（writes.NO_RECORD）を通る"""
    found = _here_root()
    return None if found is None else log_path(found, os.getcwd() if cwd is None else cwd)


def open_here() -> None:
    """記録の根が在れば、今の作業の場の記録を空で作る（在れば触らない。前の役の記録を残す）。置き場はフックと同じ open_log で作る"""
    found = _here_root()
    if found is not None:
        open_log(found, os.getcwd()).touch()


def sweep(root) -> tuple[list[pathlib.Path], list[OSError]]:
    root = pathlib.Path(root)
    if not root.is_dir():
        return [], []
    gone, failed = [], []
    for entry in root.iterdir():
        if entry.is_symlink() or not entry.is_dir():
            continue
        try:
            owner = (entry / WHERE).read_text(encoding="utf-8", errors="surrogateescape")
        except OSError:
            continue
        if _key(owner) != entry.name or os.path.isdir(owner):
            continue
        try:
            shutil.rmtree(entry)
        except FileNotFoundError:
            continue  # 並んだ起動の sweep が先に消した
        except OSError as error:
            failed.append(error)
            continue
        gone.append(entry)
    return gone, failed
