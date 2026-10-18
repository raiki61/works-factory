"""修正の後に run の深さを上げ直す信号の決め（issue #654）。深さの考えのうち、段の表と単位の深さは depth.py、run の頭の深さは
headdepth.py、修正の後の上げ直しの数えはここ。

修正のサブグラフの中の上げ直し（fixboard.redepth。差分の審査を省くかを決める）と、メイングラフの上げ直しのノード（線の redepth）は、
同じ控えをそれぞれの読み口で集めてから signals を呼ぶ。線が fix の書いた上げ直しの控えを読むだけにしないのは、線だけが知る信号
（案の直し・再審・修正の段が止めた単位・修正前の関所の答え）が在り、その控えは fix の出力に載らず、差分の審査の前で止まった
fix は書かないから。

控えの扱いは 1 つの決まり（late の形 {refused, trace, missing, unread}。読み口は lib/fixbeside.py の late_records と late_place）:
範囲の相談の行を運ぶ控えが無い時は上げずに counted に訳を添え（NO_LATE_RECORD）、在るのに読めない・{"error"}・形が違う時は
LATE_UNREAD の信号で上げる側へ倒す。TDD の輪の状態が無い置き場は輪が走っていないので拒否を数えない。

- signals(items, keys, touched, *, origin, head_record, late, declared): (run の信号の並び, counted の 1 行)
- PLAN_ORIGIN: 修正の差分を読めない時の数えの起点の字（呼び手が訳を添えて origin に渡す）
"""
import pathlib
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import consult  # noqa: E402
import depth  # noqa: E402
import headdepth  # noqa: E402

PLAN_ORIGIN = "計画の allowed_paths"   # 元 depth.PLAN_ORIGIN
LATE_UNREAD = "修正の後の信号の控えが読めない（{why}）"
NO_LATE_RECORD = "修正の後の信号の控えが無い（{name}）——範囲の相談を数えていない"


def signals(items, keys, touched, *, origin: str, head_record, late, declared=()) -> tuple:
    """(run の信号の並び, counted の 1 行)。信号は run 全体の広さ（depth.run_wide。計画の欄 items の keys の単位と修正の差分の
    触るファイル touched）・touched が頭の深さの控え head_record（パス。None・無い・読めない控えは where を持たない）の引用した
    where の外に出た（depth.outside_cited）・TDD のループで修正役が拒まれた・範囲の相談をした（consult.consulted_units）・
    直さずに残すと答えた事前審査の block（declared）の理由（depth.late_signals）と、late の unread の LATE_UNREAD。counted は
    数えたファイルの数と起点 origin に、late の missing の NO_LATE_RECORD を「／」で継いだ 1 行。late が None（修正の段が無い）なら
    拒否・相談・控えの訳を数えない"""
    late = late or {"refused": [], "trace": None, "missing": [], "unread": []}
    wide, paths = depth.run_wide(items, keys, touched)
    cited = headdepth.cited_files(headdepth.read_file(head_record)) if head_record is not None else []
    out = [*wide, *depth.late_signals(outside=depth.outside_cited(items, keys, touched, cited), refused=late["refused"],
                                      consulted=consult.consulted_units(late["trace"] or []), declared=declared),
           *(LATE_UNREAD.format(why=why) for why in late["unread"])]
    counted = f"触るファイル {paths} 個（起点: {origin}）" + "".join(f"／{NO_LATE_RECORD.format(name=name)}" for name in late["missing"])
    return out, counted
