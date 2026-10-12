"""書き込みの記録（writes.jsonl）の置き場の決め方の 1 か所。

記録のフック（bin/_lib/record-write.py。Claude の設定の PostToolUse:Edit|Write|NotebookEdit）が書き、書く役の受け付け
（writes.check）が読む。フックは道具の呼び出しのたびに起きるので、このモジュールは標準ライブラリだけを読む（重い部品を import しない）。

- ROOT: 記録の根の名（Claude の設定の置き場の下。起動が作り、無ければ記録の無い run）
- root(config_dir) -> Path: Claude の設定の置き場 config_dir の下の記録の根
- log_path(root, cwd) -> Path: 根 root の下の、役の作業の場 cwd（実パス）ごとの記録のファイル
"""
import hashlib
import os
import pathlib

ROOT = "works-writes"
LOG = "writes.jsonl"
KEY_LEN = 16   # cwd の実パスの sha256 の頭の字数（置き場のフォルダの名）


def root(config_dir) -> pathlib.Path:
    return pathlib.Path(config_dir) / ROOT


def log_path(root, cwd) -> pathlib.Path:
    key = hashlib.sha256(os.path.realpath(str(cwd)).encode("utf-8", "surrogateescape")).hexdigest()[:KEY_LEN]
    return pathlib.Path(root) / key / LOG
