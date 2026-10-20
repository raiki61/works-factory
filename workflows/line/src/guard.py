"""line の script の止めの語（docs/design/line.md の 9 節: line の script は落ちない）。

- LINE_SCRIPT: 例外の時に fallback が返す止めの語。lib/stopby.py の LINE_SCRIPT の写し（lib の import が落ちた時の fallback も引くので、
  lib から読まない。tests/blocks/line/ が lib の字と突き合わせる）
"""
LINE_SCRIPT = "works:line-script"
