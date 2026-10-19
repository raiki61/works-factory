"""place のファイルの名（docs/design/cold-read.md の 1.4）。名を持つのはこのモジュールだけで、block が消してよいのもこの名のファイルだけ"""

PROMPT_FILE = "cold-prompt-1.md"   # prompt.emit が書く（node の id・回の番号は cold・1）
REPLY_FILE = "reply.json"          # 役の返答の写し（役が飛ばされた・落ちた回は書かない）
READ_FILE = "read.json"            # 出口の返りの写し
OWN_FILES = (PROMPT_FILE, REPLY_FILE, READ_FILE)
