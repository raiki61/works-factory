"""blk-plan の芯（P1 計画 Task 25。〔線A計〕T11 を P1-R10 で書き直した物）。独立設計（r2.design）・修正案（p2.fix_plan）・
事前審査（p2.plan_review）の 3 つの役を、本線の指示書を engine の描き方で描いて回す（rolekit）。人の関所の項目は盤面の p2.human_gate が組む。
独立設計は盤面の節がまだ待っていない（graph では修正の後）ので、支度・受け付け・控えは core の design に任せる（役 r2-design）。
事前審査の指示書の頭には、その設計（無ければ無い理由）を貼る（design_section）。修正案の指示書の頭には、盤面の根の構造のブロックの
控え（core の structmark）から構造の目の行か、行なしで計画した印を貼る（独立設計の役には渡さない）。
事前審査の壁打ち（依頼 231。core の converge）で again の時は、直しの役（REVISE_ROLE。修正案の役の会話の続きで、盤面の節は
p2.fix_plan）が案を直す。直しの役が起きるかは壁打ちの控えの事実（converge.held）だけで決める。どの節の分かれも、直しの役と
独立設計の役を関数の頭に置く。

ブロックの script が役を起こす支度・受け付け・出口を持ち、ここはその部品を出す（盤面 b は引数で受ける）。

- 頭: head（役の定義・並行 PR の外した範囲・ライブラリの文書の節・事前審査なら独立設計の節）と、修正案の役の頭に貼る節
            plan_slots_section（入れてよい no）・prescription_section（判定の処方）・verify_part（裏取りの申し送り）・
            lib_section（ライブラリの文書）。
            事前審査の役の頭の design_section は独立設計の節（design_only）と項目の works の欄の節（planmarks.review_section）
- 役の名: role_node（独立設計の役 DESIGN_ROLE・直しの役 REVISE_ROLE も写しの graph の節に引く）
- 事前審査の木: 事前審査の役は束ね役。tree_part が開いた項目（converge.open_items）ごとの下請けのファイルと、項目が 2 つ以上なら相乗りの
            審査のファイルを今の周の plan-review-items/pass-<k>/ に書き、束ね役の頼み（AGG_HEAD）でそれを Agent で並べて起こさせる。
            下請けは答えを作業ツリーの外の run の置き場（answers_dir。作業ツリーは役が変えてはいけない）の機械が決めたファイルに Write で
            書く。受け付け（tree_merge）がそのファイルを項目ごとに確かめ（check_item。型・覆っていない当たりの全部の答え・自分の項目の単位だけ・
            前の block の行き先・独立設計が立つ時は穴の引用と対応表 design_map。design_gaps）、faces・shrink・resolved・当たりの答え・
            相乗り・出自の申告（origins）を審査の返答にまとめる（相乗りの審査の答えは穴の引用だけを照らす）。束ね役の返答は項目ごとの判定の
            要約（converge.ITEMS）だけで、答えのファイルと食い違えば拒む。確かめを通らない項目は、出し直しの tree_part がその項目の下請けの
            ファイルにだけ機械の読める誤りの一覧（ERRORS_HEAD）を貼って起こし直させ、通った項目は起こし直さない。
            支度（ブロックの script）が tree_part を呼ばなかった往復は下請けの置き場（ITEMS_DIR）が無いので、受け付けは木のまとめを飛ばす
            （_tree_off。審査役 1 つの返答をそのまま受ける。出自の申告 origins は役の型が確かめた返答の欄のまま）
- RECEIVES: 役ごとに貼る節の見出しの表（promptsection）
"""
import copy
import difflib
import json
import pathlib
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
from rolekit import BoardGap  # noqa: E402
import carry  # noqa: E402
import jsonfile  # noqa: E402
import concepthome  # noqa: E402  （L1。判断の 1 軸と考えの住処の観点の文）
import converge  # noqa: E402
import design  # noqa: E402
from engine.schema import validate_schema  # noqa: E402
import gatemarks  # noqa: E402
import libdocs  # noqa: E402
import planmarks  # noqa: E402
import promptsection  # noqa: E402
import ripple  # noqa: E402  （blk-plan の lib。波及の一覧）
import rolekit  # noqa: E402
import structmark  # noqa: E402
import worldmark  # noqa: E402  （世界の解の行。修正案の頭の節と事前審査の外れの訳に添える比べ）

NODE_OF = {"plan": "p2.fix_plan", "plan-review": "p2.plan_review"}   # 役（YAML の役の節の id・印の名）→ 写しの graph の節
ROLES = tuple(NODE_OF)
DESIGN_ROLE = "r2-design"   # 独立設計の役（盤面の節へは渡さない。core の design）
REVISE_ROLE = "plan-revise"   # 直しの役（事前審査の壁打ちで修正案の役の会話の続き。盤面の節は p2.fix_plan。NODE_OF・ROLES に入れない）
NONE_WORDS = ("", "null")               # 入口の「無し」（実行基盤の入力の既定の空と、ラインが渡す文字列 null）
EXCLUDED_HEAD = "並行 PR の範囲。触らず、単位に入れない"
RIPPLE_PASS = "ripple/pass-{k}.json"
ITEMS_DIR = "plan-review-items/pass-{k}"   # 事前審査の下請けのファイル（manifest の produces plan-review-items/**）
AGENT_OP = "plan_review_agents"         # 読んだ証拠の節が trace に書く、事前審査の下請けの起動の数の行（元 planblk.py:134）
# 入力 review_tree が auto の時に木にする開いた項目の数の下限
TREE_AUTO_MIN = 2
# 受け付けの拒みの頭（plan の受け付け planfile と事前審査の受け付け boardview が読む）
NO_NARROW_REJECT = (f"narrows の行に狭めない案を探した結果（{gatemarks.NO_NARROW}）が無いか短い（直して出し直せ）。狭めを避ける形が"
                    "在ればそれを案に採ってその行を消し、無い時だけ、どの形を当たりなぜ採れないかを書け:")
RECOMMEND_REJECT = (f"承認ノードの項目の行の推し（{gatemarks.RECOMMEND}）の形が崩れている（直して出し直せ）。"
                    f"書くなら {gatemarks.RECOMMEND_SHAPE} の形で:")
NOT_OWED_REJECT = "案に、直す義務の無い単位が入っている（nit・info・defer など。受け付けが受けない）。案から外せ。案に入れてよい no（必ず入れる物を含む）は"
RESOLVED_REJECT = "前の往復の block の行き先が書かれていない（下の行を全部直して出し直せ）:"
ANSWERS_REJECT = "block への答えに誤りが在る（下の行を全部直して出し直せ）:"
TREE_REJECT = "項目ごとの審査の答え（下請けの答えのファイル・束ね役の items）に欠けか誤りが在る（下の行を全部直して出し直せ）:"
CLOSED_REJECT = "閉じた・開いた項目の行が合わない（下の行を直して出し直せ）:"
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "   # 元 works/.shared/core/entry.py:1228
NO_TREE = "役を起こす前の作業ツリーの控え {name} が無い（支度のノードが走っていない）"
# 案の直しを終えられなかった項目の諦めの訳（元 works/.shared/core/replan.py:139-140）と、その行 [{item, why, ruling}] を置く隣のファイル
# （計画の返り plan と事前審査の返り review の指し札の先と同じフォルダ。報告が前の失敗の行に読む）
PLAN_GAVE_UP_WHY = "修正案の役の直しが 3 回とも拒まれた: {reason}"
REVIEW_GAVE_UP_WHY = "事前審査の役の返答が 3 回とも拒まれた: {reason}"
REPLAN_GAVE_UP_FILE = "replan-gave-up.json"
DESIGN_QUOTE_REJECT = ("独立設計の引用か design_map に誤りが在る（下の行を全部直して出し直せ。「」は独立設計と案の行の引用だけに使い、"
                       "ほかの引用は『』か `…` で書く）:")
# 下請けの答えのファイルの置き場（作業ツリーの外の run の置き場 adapter.run_place_of の今の scope の下。作業ツリーは役が変えてはいけない。
# 受け付けが確かめたファイルは往復の控え plan-converge/pass-<k>/ に写す）
ANSWERS_DIR = "plan-review/r{r}/pass-{k}"
ANSWER_FILE = "item-{n}.json"
SYNERGY_FILE = "synergy.json"
SURPLUS_OP = "plan_review_surplus"
# 下請けの型は 1 つ（答えのファイルを Write で書ける型。読むだけの Explore は Write を持たない。run 68f35d6b は往復 1 が
# general-purpose・往復 2・3 が Explore で、型ごとに道具と深さが違った）
SUBAGENT_TYPE = "general-purpose"
AGG_HEAD = promptsection.Section("## 束ね役の頼み（項目ごとの下請けを並べる。機械が貼った）", source="fn:planblk.tree_part")
AGG_ASK = ("この役は束ね役。案の項目を自分で見ずに、下の下請けのファイルごとに Agent の道具で下請けを 1 つずつ起こせ。下請けの呼びは"
           " 1 つのメッセージに全部並べよ（同時に走る）。subagent_type は全部 " + SUBAGENT_TYPE + "（相乗りの審査も同じ。ほかの型を"
           "使わない）。各下請けへの頼みは「<ファイル> を Read で読み、その指示に従え」の 1 行でよい。"
           "下請けは読むだけで、答えはファイルに書き（どこに書くかはファイルが名指す。作業ツリーは変えない。変われば受け付けが拒む）、"
           "最後に 1 行の要約を返す。答えのファイルは受け付け（機械）が確かめてまとめるので、答えの中身を写さない。")
AGG_MERGE = ("下請けが全部返ったら、返答は次の形だけにせよ（受け付けが答えのファイルと突き合わせ、食い違えば拒む）: faces と shrink は"
             "空の配列、origins は書かない（出自は下請けの答えのファイルに書く）、reason にこの往復のまとめ（20 字以上）、items に開いた項目ごとに 1 行 {item, verdict（下請けの要約が clean なら"
             " clean、block なら block）, blocks（下請けの要約の block の key ごとに {key, why（一言）}。clean なら []）}。"
             "閉じた項目・保留の項目の行は入れない。前の拒否の理由が済んだ項目の答えの中身を名指していれば、その項目の下請けを起こし"
             "直して理由のファイルを読ませ、答えのファイルを直させよ。")
AGG_SYNERGY = ("開いた項目の全部が clean なら、同じ往復の最後に相乗りの下請けを 1 つ起こす（{path}）。block の項目が在れば起こさない。")
OPEN_HEAD = "開いた項目の下請けのファイル:"
DONE_HEAD = "済んだ下請け（答えのファイルが機械の確かめを通った。起こし直さない）:"
REDO_HEAD = "起こし直す下請け（答えのファイルが無いか、機械の確かめを通らなかった。この下請けだけを起こす）:"
BRIEF_TITLE = promptsection.Section("# 事前審査の下請け", source="fn:planblk.brief_head")
ITEM_HEAD = promptsection.Section("## この下請けの項目: 項目 {n}", source="fn:planblk.tree_part")   # 下請けのファイルの共通の頭（全部の項目で同じバイト。プロンプトのキャッシュ）と項目の節の境
SUB_HEAD = ("この役は修正案の事前審査の下請け（読むだけ。Read・Grep・Glob と web の道具で調べ、Write は下の答えのファイルにだけ使う。"
            "Edit・Bash を使わず、作業ツリーを 1 文字も変えない）。審査の決まり・独立設計・判定者の見立てはこのファイルの頭に、"
            "この下請けの項目の案・単位・波及の一覧は最後のセクションに在る。ほかのファイルの指示書を読みに行かなくてよい（根拠のコードは読め）。")
RULES_FROM = "\nリポジトリ: "   # 描いた事前審査の指示書のうち、下請けに貼る審査の決まりの頭（そこから末尾まで）
RULES_MISSING = "審査の決まりを切り出せなかった。指示書 {main} の『見ること』『返し方』『人の方針』を Read で読め（そこの束ね役の頼みと返す型はこの下請けへの指示でない）"
SUB_FORMAT = promptsection.Section("## 答え方（全部の下請けで同じ）\n\n項目の下請けは、覆っていない当たりの全部に covered（この項目の範囲で覆っている。"
                                   "どこで）・no_effect（影響しない。理由）・block（穴。faces に severity block で挙げる）のどれかで答える（why は当たり"
                                   "ごとに 10 字以上。『同上』で済ませない）。faces の unit_keys は項目の unit_keys を字のまま写す（no の整数でなく）。"
                                   "resolved は前の往復の block のうち消えた key（無ければ []）。答えは下の JSON Schema に合う JSON 1 つにして、"
                                   "最後のセクションが名指すファイルに Write で書く（そのファイルのほかに書かない。書き直す時も同じファイル）。書いたら最後の"
                                   "メッセージに 1 行だけ返す（答えの中身を写さない）。\n\n```json\n{schema}\n```", source="fn:planblk.brief_head")
ANSWER_AT = "Write の道具でファイル {answer} に書け"   # 下請けのファイルが答えの置き場を名指す句（answer_in が引く）
DIFF_HEAD = promptsection.Section("## 前の往復からのこの項目の案の差分", source="fn:planblk._diff_part")
DIFF_ASK = ("前の往復でこの項目を見た審査は、下の前の block のほかに直しへ進めない穴を挙げなかった。今の往復で見るのは (1) 前の block が"
            "消えたか（消えたなら resolved、残れば同じ key で faces に block）と (2) 下の差分（- が前・+ が今）が作る新しい穴だけ。"
            "差分の外の所を見直して新しい穴を探さない。穴の重さの決まり（block か suggest か）は変えない。")
# 差分に絞らず全部を審査する、前の往復の行から違う字の割合の境（決まりと字の数え方の正本は _diff_part の docstring）
DIFF_FULL_SHARE = 0.25
DIFF_FULL_ASK = ("この項目は前の往復から大きく変わった（下の差分は変わった所の目安）。差分に絞らず、この項目の案の全部を審査せよ。"
                 "前の block が消えたかも見る（消えたなら resolved、残れば同じ key で faces に block）。穴の重さの決まり（block か "
                 "suggest か）は変えない。")
CARRIED_HEAD = promptsection.Section("## 前の往復で答えた当たり（機械が答えを引き継ぐ。hits に入れなくてよい。差分で答えが変わる物だけ入れ直せ）", source="fn:planblk._carried_part")
# 先行例の出典の確かめ（見ること 8）は run の中で 1 度だけ: 開く下請けを出典ごとに 1 つに決め、受け付けがその答えの確かめを
# scope の根の PRECEDENT_CACHE に控え、後の往復・後の周の下請けには控えを貼って開かせない（run 68f35d6b は同じ 2 つの出典を
# 往復ごとに WebFetch で開き直した）
PRECEDENT_CACHE = "precedent-checks.json"
PRECEDENT_HEAD = promptsection.Section("## この項目の先行例の出典（判定者の先行例のうち adopt・adapt。見ること 8）", source="fn:planblk._precedent_part")
PRECEDENT_FETCH = "WebFetch で 1 度だけ開いて確かめ、答えの precedents に {id, found（在り単位の問題に当たっているか）, quote（確かめた一文）} の行を書け"
PRECEDENT_CACHED = "確かめ済み（控えのとおり。WebFetch で開き直さない。この控えで判定せよ）"
PRECEDENT_OTHER = "この往復は項目 {m} の下請けが開く（この下請けは開かない。この出典の穴は項目 {m} の下請けが挙げる）"
PRECEDENT_VERDICTS = ("adopt", "adapt")
ERRORS_HEAD = promptsection.Section("## 前の答えの誤り（機械の確かめ。この誤りだけを直して同じファイルに書き直せ）", source="fn:planblk._errors_part")
SUB_ITEM_ASK = ("見るのは下の項目 {n} だけ。この項目が固まる（直しへ進めない穴が無い）まで深く見よ。ほかの項目の穴は挙げない"
                "（項目どうしの関わりは別の下請けが見る）。答えは頭の『答え方』の型で、" + ANSWER_AT + "。書いたら最後のメッセージに"
                " 1 行だけ返せ: `項目 {n}: clean` か `項目 {n}: block <key>、<key>`。")
SUB_SYNERGY_ASK = ("この役は相乗りの審査の下請け。項目どうしの関わりだけを見る（1 つの項目の中の穴は挙げない。頭の『答え方』の当たりの"
                   "答えは要らない）: 同じ行・同じ塊への食い違う変更・順番の依存・重複した作業・同じ根なのに別の項目に分かれた所。"
                   "同じファイルの別の所（別の関数・別のクラス・別のクラスに足すテスト）を触るだけの項目は穴でない（まとめさせない）。"
                   "穴は faces に挙げ、unit_keys に関わる項目の単位の名を全部、字のまま入れよ（名指した項目だけが開き直す）。why に見た事と、穴が"
                   "無いならその理由を書く。答えは下の JSON Schema に合う JSON 1 つにして、" + ANSWER_AT + "（このファイルのほかに"
                   "書かない）。書いたら最後のメッセージに 1 行だけ返せ: `相乗り: clean` か `相乗り: block <key>、<key>`。"
                   "\n\n```json\n{schema}\n```")
PLAN_STUCK = "修正案の行き止まり: 必ず案に入れる単位が開いていない"
STUCK_WHY = ("受け付けの写しは開いていない単位を受けず、義務からも外さないので、案の形では閉じない。人が承認ノードで問いの答えを直すか、"
             "単位を開く")
PLAN_SLOTS_HEAD = promptsection.Section("## 案に入れてよい単位の no（機械が受け付けと同じ述語から作った。下の本文の『今の周に直す単位』の見出しと、"
                                        "one_shot_closes に載る単位より、このセクションが優先する）", source="fn:planblk.plan_slots_section")
DESIGN_HEAD = promptsection.Section("## 独立設計（修正案を見ない別の目が、目的と実測した制約・承認ノードの答え・依頼が名指した設計書のセクションから作った理想解。機械が貼った）", source="fn:planblk.design_only")
DESIGN_ASK = ("修正案をこの設計と構造で突き合わせよ——何を固定し何を派生と見るか・どこに継ぎ目を置くか・目的の当事者が日常で回す"
              "動線が閉じるか。案が足す仕組み（ファイル・関数・ノード・役・欄・入力）ごとと、この項目の adds・allowed_paths の大きさごとに、"
              "設計との食い違いかを判じよ。判じる根拠は引用で示す: 独立設計の行と案の行（その項目の "
              f"{'・'.join(design.ROW_QUOTE_KEYS)}）を、それぞれ「…」で字のまま引け。設計から引用できない所は、大きさの開きでも対の無さでも食い違いに数えない"
              "（表現の違い・設計が触れていない所もこの決まり1つで読む。設計は判定の単位も実装の事情も知らない）。"
              "食い違いと判じた物は、設計に対の無い仕組みも大きさの開きも、faces に kind contract_drift・severity block で挙げ、why を"
              f"対の無い仕組みなら『{design.UNPAIRED_HEAD}』、構造の食い違い・大きさの開きなら『{design.DRIFT_HEAD}』で始め、"
              "why に独立設計の行と案の行の引用をそれぞれ 1 つ以上入れよ（機械が字のまま在るかを照らし、無ければ出し直させる）。"
              "大きさの開きには、この項目の shrink に小さく閉じる別案も書け。この 2 つの頭の穴の why と design_map では、「」を"
              "独立設計と案の行の引用だけに使い、ほかの引用は『』か `…` で書け。"
              "独立設計が立つ run では、項目の答え（項目ごとの下請けの答えのファイル。下請けを起こさない往復と案の直しの事前審査では"
              "返答）に design_map を書け。相乗りの審査と束ね役は書かない。行は項目の adds の name ごとに 1 行 "
              "{item, name, design_quote（独立設計に対がある時はその行を字のまま引く。対が無ければ null）, why}。"
              "単位を閉じるのに要る実装の細部は挙げない。頭の『既にある物を量ったかを見よ』（REUSE_REVIEW）で kind copy に挙げた行は、"
              "contract_drift に挙げ直さない。")
DESIGN_NOT_STANDS = ("設計の役は、目的の問いが立たないと返した（{reason}）。問いが立つかは修正の後の独立の目が前提を実態で検算して"
                     "扱うので、ここでは穴に挙げない。設計との突き合わせはせずに審査せよ。")
DESIGN_NONE = "独立設計は無い（{why}）。設計との突き合わせはせずに審査せよ。"
# 項目の組み方の決まり（修正案の役の頭。写しの指示書の「1 つの案で複数の単位を閉じてよい（一撃の原理に沿うならそれが望ましい）」
# を同じファイルを触るだけの単位にまで当てない。canary の run 2 本が同じファイルの別の所を触る 2 単位を 1 項目にまとめた）
ITEMS_RULE = ("項目の組み方: 項目をまとめるのは、単位が同じ根で 1 つの直しで閉じる時・同じ行か同じ塊（hunk）を変える時・"
              "片方の直しがもう片方の直しの結果による時（先に直さないと直せない・試せない）だけ。同じファイルの別の所（別の関数・"
              "別のクラス・別のクラスに足すテスト）を触るだけでは項目をまとめる理由にならない——そういう単位は別々の項目に分けよ。"
              "写しの指示書の『1 つの案で複数の単位を閉じてよい（一撃の原理に沿うならそれが望ましい）』は、根を本当に共にする単位の話")
# 既にある物を先に探す決まり（修正案の役の頭と事前審査の頭。実の利用者の run 97fd532f: 事前審査が描画の検査を求め、修正案が
# 約 260 行のサブコマンドと試験の束・偽の道具を新設したが、同じ workflow に 2〜3 行で同じ仕事をする助け手が在り、どの文書も量らなかった。
# 判定役・修正役の「既製の物で済まないかを先に確かめろ」を案と審査の段に伸ばす）
REUSE_RULE = ("既にある物を先に探せ: 新しい機構（スクリプト・サブコマンド・助け手の関数・テストの仕掛け（偽の道具・試験の束など））を"
              " adds に足す前に、案が触るファイルと、その兄弟（同じ workflow の別の job・step、同じモジュール・同じ置き場の別のファイル）から、"
              "同じ仕事を既にしている助け手を Grep で探せ。在ればそれを使う案にし、新設しない。それでも新設するなら、その adds の行の"
              " canonical を今どおり置くファイルのパス（新しいモジュールなら <パス>.py（新設。…））で始め、その後ろに、当たった物"
              "（パスと行）と採らない理由を書け（当たらなかったなら、どこをどう探したか）。書いていない新設は事前審査が穴に挙げる")
REUSE_REVIEW = ("既にある物を量ったかを見よ: adds の行が新しい機構（スクリプト・サブコマンド・助け手の関数・テストの仕掛け）なのに、"
                "canonical に当たった既存の物と採らない理由（当たらなかったなら探し方）が無ければ、kind copy の穴に挙げよ。書いてあっても、"
                "案が触るファイルとその兄弟（同じ workflow・同じモジュール）を自分でも Grep で探し、同じ仕事をする既存の助け手が在れば、"
                "それを使う形を shrink か穴の why に書け。穴を閉じる形として新しい機構を求める前にも同じ所を探し、既存の助け手で閉じるなら"
                "それを名指して求めよ")
# 人に回す物は人の口へ（実の利用者の run 97fd532f: 契約のずれの穴の why に「ADR は人に回す」と書いたが、その種類の穴は関所に載らず、
# 修正役の『人に回す』も人に届かなかった）。修正前の関所に載る種類は写しの rules の HUMAN_FACE_KINDS（regression・policy）
HANDOFF_REVIEW = ("人に回す物は人の口で挙げよ: 穴の直しの一部に、直す側に任せず人が決める物（方針の文書・ADR の書き換えなど）が"
                  "在るなら、why に「人に回す」と書くだけでなく、その分を kind policy・severity suggest の別の穴として挙げよ（fences に"
                  " policy_doc。案の欠陥ではないので block にしない）——修正前の承認ノードに載り、人が決める。ほかの kind の why に書いた回付は、"
                  "どの承認ノードにも載らない")
HEAD = {
    "plan": ("この役は修正案の役（読むだけ）。道具は Read・Grep・Glob と web を引く WebSearch・WebFetch だけで、作業ツリーを 1 文字も変えてはいけない（受け付けは起こす前の"
             "作業ツリーの写しと比べ、変わっていれば拒む）。下の指示書に従い、指示書の JSON Schema に合う JSON だけを返せ。"
             "\n\n" + planmarks.HEAD + "\n\n" + ITEMS_RULE + "\n\n" + REUSE_RULE + "\n\n" + concepthome.PLAN_RULE),
    "plan-review": ("この役は修正案の事前審査の役（読むだけ。判定をした役とは別の目）。道具は Read・Grep・Glob と web を引く WebSearch・WebFetch と、"
                    "項目ごとの下請けを起こす Agent と、下請けが答えのファイル（作業ツリーの外の run の置き場）を書く Write だけで、作業ツリーを"
                    " 1 文字も変えてはいけない（受け付けは起こす前の作業ツリーの写しと比べ、変わっていれば拒む）。下の指示書に従い、指示書の"
                    " JSON Schema に合う JSON だけを返せ。\n\n" + REUSE_REVIEW + "\n\n" + HANDOFF_REVIEW + "\n\n" + concepthome.REVIEW_ASK),
}


def role_node(role: str) -> str:
    if role not in NODE_OF:
        raise BoardGap(f"役 {role!r} は blk-plan の共有ボードへ渡す役（{' / '.join(ROLES)}）でない")
    return NODE_OF[role]


def _given(value) -> str:
    return "" if value is None or str(value).strip() in NONE_WORDS else str(value)


def head(role: str, excluded_file: str = "", lib_docs: str = "", design_part: str = "") -> str:
    """指示書の頭（役の定義と、並行 PR の外した範囲のパスと、ライブラリの文書の節 libdocs.section と、事前審査なら
    独立設計の節 design_section・修正案なら構造の目の節 structmark.plan_section と入れてよい no の節 plan_slots_section）。
    修正案の役の定義（HEAD["plan"]）は、項目の works の欄（route・tests・rewrite_tests・refactor・allowed_paths・
    out_of_scope）の節 planmarks.HEAD を含む。
    事前審査の役は、その欄の JSON を design_section の中の planmarks.review_section で受ける"""
    text = HEAD[role] + "\n\n" + gatemarks.HEAD[role_node(role)]
    ex = _given(excluded_file)
    if ex:
        text += f"\n\n{EXCLUDED_HEAD}: {ex}（先に Read で読め。そこに挙がった範囲は、ほかの PR が扱う）"
    if lib_docs:
        text += "\n\n" + lib_docs
    if design_part:
        text += "\n\n" + design_part
    return text


def plan_slots(b) -> tuple[set, set, dict]:
    """(必ず入れる, 入れてよい, 単位の key → 単位)。写しの受け付け fix_plan_covers_units が読むのと同じ物（want＝b.rules._owed_units、
    opened＝validator の is_open）から作る。見せる頭の節と take の事前の拒否が、ここだけを読む"""
    V = b.rules.validator_module(b)
    units = {u["key"]: u for u in b.record["units"]}
    return set(b.rules._owed_units(b)), {k for k, u in units.items() if V.is_open(u)}, units


def _names(b, nid: str) -> list:
    return next((p.get("names") or [] for p in b.pointer_rows(nid)["pointers"] or []), [])


def plan_slots_section(b, filled=()) -> str:
    """修正案の指示書の頭に貼る、入れてよい no・入れてはいけない no の節（本文の見出し・one_shot_closes より優先する）。filled
    （直しの役が書かず機械が前の往復の行を差し込む項目の単位。converge.filled_units）の no は『必ず案に入れる』から外して別の行に並べる"""
    owed, opened, units = plan_slots(b)
    names = _names(b, NODE_OF["plan"])
    no = {k: i + 1 for i, k in enumerate(names)}
    must = sorted(no[k] for k in owed - set(filled) if k in no)
    may = sorted(no[k] for k in opened - owed if k in no)
    shut = [f"no {no[k]}（label={u.get('label')}・disposition={u.get('disposition', '無し')}）"
            for k, u in units.items() if k not in opened and k not in owed and k in no]
    if not shut and not filled:   # 本文の一覧が受け付けの集合と同じ（全部入れてよい）なら貼らない。行き止まりの盤面は役を起こす前に止める（halt_if_stuck）
        return ""
    lines = [f"- 必ず案に入れる no: {must}",
             f"- 入れてもよい no（人の答え待ちの問いの出どころ・depends。入れなくてもよい）: {may}"]
    if filled:
        lines.append(f"- 機械が差し込む no（閉じた・保留の項目。書かなくてよい）: {sorted(no[k] for k in set(filled) if k in no)}")
    lines.append(f"- 入れてはいけない no（受け付けが拒む）: {'、'.join(shut) or '無し'}")
    return f"{PLAN_SLOTS_HEAD}\n\n" + "\n".join(lines)


PRESCRIPTION_HEAD = promptsection.Section("## 判定の処方（判定役が単位ごとに書いた直し方の案。零処方から並ぶ。機械が判定の記録から貼った）", source="fn:planblk.prescription_section")
PRESCRIPTION_ASK = ("案は単位の処方を採れ。採らない処方が在れば、その単位を持つ項目の works の欄 structure に "
                    "{prescription: <単位の key>, deviation: <採らない訳>} を書け（処方の関係・条件を黙って落とさない）。")


PRESCRIPTION_UNIT_HEAD = promptsection.Section("### {key}", source="fn:planblk.prescription_section")


def prescription_section(b) -> str:
    """修正案の指示書の頭に貼る、案に入れる単位（plan_slots の必ず入れる・入れてよい）の判定の処方の節。処方の無い run は ""。
    写しの指示書は単位を名前と label と区分だけで描き、処方を渡さない（利用者の声 D2）"""
    owed, opened, units = plan_slots(b)
    given = planmarks.prescriptions(b)
    rows = [f"{PRESCRIPTION_UNIT_HEAD.format(key=k)}\n\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(given[k], 1))
            for k in units if k in owed | opened and k in given]
    return f"{PRESCRIPTION_HEAD}\n\n{PRESCRIPTION_ASK}\n\n" + "\n\n".join(rows) if rows else ""


def design_section(b) -> str:
    """事前審査の指示書の頭に貼る節: 独立設計の節（design_only）と、修正案の項目の works の欄の節（planmarks.review_section。
    控えが無ければ無し）。欄の控えが凍結の印と食い違えば控えを名指す理由の BoardGap（盤面を止めるのは呼ぶブロックの script）"""
    try:
        fields = planmarks.review_section(b, worldmark.challenges(worldmark.stage_rows(b.dir) or []))
    except planmarks.FieldsBroken as e:   # 受け付けの後に欄の控えを書き換えた: 書き換えた欄を審査に見せない
        why = f"修正案の項目の works の欄の控え {planmarks.FIELDS_FILE} が凍結と食い違う: {' '.join(str(e).split())}"
        raise BoardGap(why) from None
    return design_only(b) + fields


def design_only(b) -> str:
    """独立設計の節だけ（項目の works の欄の節は入れない）。設計が問いは立たないと返した・設計が無い時は、突き合わせない旨と理由。
    同じ run の中の案の直しの事前審査の指示書にも貼る"""
    got, _ = design.made(b.dir, b.design_schema)
    if got is None:
        return f"{DESIGN_HEAD}\n\n" + DESIGN_NONE.format(why=design.missing(b))
    if not got["question_stands"]:
        r = got.get("premise_invalid_reason") or got["reason"]
        return f"{DESIGN_HEAD}\n\n" + DESIGN_NOT_STANDS.format(reason=r + design.anchor_note(r))
    return (f"{DESIGN_HEAD}\n\n{DESIGN_ASK}\n\n設計の役の理由: {got['reason']}\n\n=====独立設計ここから=====\n"
            f"{got['design']}\n=====独立設計ここまで=====")


def lib_section(b, repo, shared=None) -> str:
    """判定の単位のファイルが使うライブラリの文書の節（同じ周の 2 つ目の役は盤面の控えを読み、網に出ない）。shared は run をまたぐ
    控えの根（None なら使わない）"""
    out = (b.state.get("outputs") or {}).get("p2.diagnose") or {}
    judgment = str(pathlib.Path(b.dir) / out["file"]) if out.get("file") else ""
    files, why = libdocs.unit_files(repo, judgment) if judgment else ([], "判定の出力が共有ボードに無い")
    text = libdocs.section(b.work(""), repo, files, shared=shared)
    return text + (f"\n- 単位のファイルの引き: {why}" if why else "")


def _ripple_of(b, k: int):
    """往復 k の項目ごとの波及の一覧（無ければ None）"""
    return jsonfile.read_or(b.work(RIPPLE_PASS.format(k=k)))


VERIFY_HEAD = promptsection.Section("## 判定の単位の裏取り（判定とは別の目が単位ごとに確かめた申し送り。機械が貼った）", source="fn:planblk.verify_part")
VERIFY_ASK = ("単位は直す義務で、この申し送りでは減らない。根本でない・場所が違う・証拠が無いと出た単位も、案から外せない（受け付けが"
              "拒む）。そういう単位は本当の根の単位と同じ項目にまとめるか、approach に申し送りへの答え（どう扱うか）を書け。"
              "重複・同じ所の関わり・順番は項目の組み方に使え（頭の『項目の組み方』の決まりに従う）。別の所の関わり（同じファイルの"
              "別の所を触るだけ）は項目の並べ方の参考にだけ使い、それで項目をまとめない。確かめられなかった単位は判定のままに読め。")
PLACE_WORDS = {"same": "同じ所", "apart": "別の所"}   # 関わりの行の place（同じ行・同じ塊か、同じファイルの別の所か）の見出し
VERDICT_WORDS = {"root": "根本", "not_root": "根本でない", "unsure": "根本か決められない"}


def _verify_row(u: dict) -> str:
    head = f"- 単位 {u.get('n')} `{u.get('key')}`: "
    if u.get("state") != "checked":
        return head + "確かめられなかった（" + "・".join(str(e) for e in u.get("errors") or []) + "）"
    parts = [VERDICT_WORDS.get(u.get("verdict"), str(u.get("verdict")))]
    if u.get("verdict") == "not_root":
        parts[0] += f"（本当の根: {u.get('real_root')}）"
    parts.append(f"証拠 {'在り' if u.get('evidence_found') else '無し'}（{u.get('evidence')}）")
    parts.append(f"場所 {'合う' if u.get('location_ok') else '違う'}（{u.get('location')}）")
    return head + "・".join(parts) + f"。{u.get('why')}"


def _relation_label(label: str, row: dict) -> str:
    """申し送りの行の見出し。関わりの行は place（same＝同じ行・同じ塊・前提を変える、apart＝同じファイルの別の所）を添える
    （place の無い前の形の行は見出しだけ）"""
    word = PLACE_WORDS.get(row.get("place"))
    return f"{label}（{word}）" if word else label


def verify_part(verify_file) -> str:
    """修正案の役の頭に貼る判定の単位の裏取りの申し送りの節。入力 verify_file は形 {units: [{n, key, state, verdict,
    evidence_found, evidence, location_ok, location, real_root, why, errors}], synergy: {state, why, duplicates, relations,
    order, errors}} の JSON（relations の行は {units, why, place}。place は same か apart で、無い行も読む） のパス（出どころは名指さない）。空か文字列 null なら空、読めなければその 1 行"""
    path = _given(verify_file)
    if not path:
        return ""
    doc = jsonfile.read_or(pathlib.Path(path))
    if not isinstance(doc, dict) or not isinstance(doc.get("units"), list):
        return f"{VERIFY_HEAD}\n\n申し送りのファイル {path} が読めない（判定のままに読め）。"
    lines = [VERIFY_HEAD, "", VERIFY_ASK, ""] + [_verify_row(u) for u in doc["units"] if isinstance(u, dict)]
    syn = doc.get("synergy") if isinstance(doc.get("synergy"), dict) else {}
    if syn.get("state") == "checked":
        lines += ["", f"単位どうしの相乗り: {syn.get('why')}"]
        for label, field in (("重複", "duplicates"), ("関わり", "relations")):
            lines += [f"- {_relation_label(label, r)}: " + "・".join(f"`{k}`" for k in r.get("units") or [])
                      + f"（{r.get('why')}）" for r in syn.get(field) or [] if isinstance(r, dict)]
        lines += [f"- 順番: `{r.get('first')}` を先に、`{r.get('then')}` を後に（{r.get('why')}）"
                  for r in syn.get("order") or [] if isinstance(r, dict)]
    else:
        lines += ["", "単位どうしの相乗り: 確かめられなかった（" + "・".join(str(e) for e in syn.get("errors") or []) + "）"]
    return "\n".join(lines)


def _item_rows(b) -> list:
    """今の周の案の項目（盤面の p2.fix_plan の出力の行に、項目の works の欄を重ねた物。番号は並びの順）"""
    doc = b.output_of_round(NODE_OF["plan"], b.round)
    plan = doc.get("plan") if isinstance(doc, dict) else None
    fields = planmarks.read(b) or []
    rows = plan if isinstance(plan, list) else []
    return [{**(r if isinstance(r, dict) else {}), **(f if isinstance(f, dict) else {})}
            for r, f in zip(rows + [{}] * (len(fields) - len(rows)), fields + [{}] * (len(rows) - len(fields)))]


HISTORY_HEAD = promptsection.Section(f"## この項目の前の往復の block（{converge.REREVIEW_ASK}）", source="fn:planblk._item_history")


def _item_history(b, unit_keys: list) -> str:
    """前の往復でこの項目に挙がった block と修正案の役の答えと、出自の頼み ORIGIN_ASK（下請けのファイルに貼る。1 往復目は空）"""
    doc = converge.read(b)
    mine = {str(k) for k in unit_keys}
    lines = []
    replies = [p.get("answers", []) for p in doc["passes"][1:]] + [doc["open"].get("answers", [])]
    for p, answers in zip(doc["passes"], replies):
        units = p.get("face_units") or {}
        keys = [k for k in p.get("blocks", []) if set(units.get(k) or []) & mine or not units.get(k)]
        for f in p.get("faces", []):
            if f.get("key") in keys:
                lines.append(f"- {p['pass']} 往復目の block {f['key']}: {f.get('why')}（{f.get('where')}）")
        lines += [f"  - 修正案の役の答え {a.get('key')}: {a.get('handled')}（{a.get('how')}）" for a in answers
                  if isinstance(a, dict) and a.get("key") in keys]
    if not doc["passes"]:
        return ""
    return "\n".join([*([HISTORY_HEAD, *lines] if lines else []), converge.ORIGIN_ASK])


def answers_dir(b, k: int) -> pathlib.Path:
    """往復 k の下請けの答えのファイルの置き場（run ごとの置き場の今の scope の下の ANSWERS_DIR。作らない）"""
    place = pathlib.Path(b.dir)
    return (place / b.scope if b.scope else place) / ANSWERS_DIR.format(r=b.round, k=k)


def answer_file(b, k: int, n: int) -> pathlib.Path:
    return answers_dir(b, k) / ANSWER_FILE.format(n=n)


def synergy_file(b, k: int) -> pathlib.Path:
    return answers_dir(b, k) / SYNERGY_FILE


def _faces_schema(b) -> tuple[dict, dict]:
    props = b.faces_schema
    return copy.deepcopy(props["faces"]), copy.deepcopy(props["shrink"])


def item_schema(b) -> dict:
    """項目の下請けの答えのファイルの型（faces・shrink は事前審査の役の型の物。precedents は開けと言われた先行例の出典の確かめ）"""
    faces, shrink = _faces_schema(b)
    return {"type": "object", "additionalProperties": False,
            "required": ["item", "checked", "hits", "faces", "shrink", "resolved"],
            "properties": {"item": {"type": "integer", "minimum": 1}, "checked": {"type": "string", "minLength": 10},
                           "hits": copy.deepcopy(converge.HITS_SCHEMA), "faces": faces, "shrink": shrink,
                           "resolved": {"type": "array", "items": {"type": "string"}},
                           converge.DESIGN_MAP: copy.deepcopy(converge.DESIGN_MAP_SCHEMA),
                           converge.ORIGINS: copy.deepcopy(converge.ORIGIN_SCHEMA),
                           "precedents": {"type": "array", "items": {
                               "type": "object", "additionalProperties": False, "required": ["id", "found", "quote"],
                               "properties": {"id": {"type": "string"}, "found": {"type": "boolean"},
                                              "quote": {"type": "string", "minLength": 10}}}}}}


def _precedent_cache(b) -> pathlib.Path:
    return pathlib.Path(b.scope_root) / PRECEDENT_CACHE


def precedent_checks(b) -> dict:
    """控えた先行例の出典の確かめ {出典: {found, quote, round, pass, item}}（無い・読めなければ {}）"""
    doc = jsonfile.read_or(_precedent_cache(b))
    return doc if isinstance(doc, dict) else {}


def precedent_plan(b, opened: list) -> dict:
    """開いた項目ごとの先行例の出典の行 {項目: [{id, row, cached | None, fetch_by}]}。id は判定の先行例の並びの P<i>。控えの無い
    出典は、それを持つ開いた項目のうち一番小さい番号の項目の下請けが開く（fetch_by）"""
    plan = converge.read(b).get("plan") or []
    rows = (b.record.get("process") or {}).get("precedents") or []
    cache = precedent_checks(b)
    owner: dict = {}
    out: dict = {}
    for n in opened:
        mine = {str(k) for k in plan[n - 1]["unit_keys"]} if 1 <= n <= len(plan) else set()
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict) or r.get("key") not in mine or r.get("verdict") not in PRECEDENT_VERDICTS:
                continue
            src = str(r.get("source") or "")
            hit = cache.get(src)
            if hit is None:
                owner.setdefault(src, n)
            out.setdefault(n, []).append({"id": f"P{i}", "row": r, "cached": hit, "fetch_by": owner.get(src)})
    return out


def _precedent_part(rows: list, n: int) -> str:
    if not rows:
        return ""
    lines = [PRECEDENT_HEAD, ""]
    for x in rows:
        r = x["row"]
        what = f"{x['id']}: {r.get('source')}（verdict {r.get('verdict')}・単位 {r.get('key')}・判定者の理由 {r.get('reason')}）"
        if x["cached"] is not None:
            c = x["cached"]
            lines.append(f"- {what} — {PRECEDENT_CACHED}: found={str(c.get('found')).lower()}・{c.get('quote')}")
        elif x["fetch_by"] == n:
            lines.append(f"- {what} — {PRECEDENT_FETCH}")
        else:
            lines.append(f"- {what} — {PRECEDENT_OTHER.format(m=x['fetch_by'])}")
    return "\n".join(lines)


def _precedent_wanted(rows: list, n: int) -> list:
    return [x["id"] for x in rows if x["cached"] is None and x["fetch_by"] == n]


def _precedent_gaps(rows: list, n: int, got: dict) -> list[str]:
    ids = [r.get("id") for r in got.get("precedents") or []]
    return [f"$.precedents: 先行例の出典 {i} の確かめの行が無い（WebFetch で 1 度開いて {{id, found, quote}} を書け）"
            for i in _precedent_wanted(rows, n) if i not in ids]


def _surplus(b, n: int, got: dict, rip: dict, pre_rows: list) -> dict:
    """型の合った項目 n の答えの余りの行の id {precedents, hits}: この項目の下請けが開く出典でない precedents の行・波及の一覧の
    項目 n の覆っていない当たりに無い hits の行。拒まずに捨てる（check_item が取り除く）"""
    want_p = _precedent_wanted(pre_rows, n)
    want_h = [h["id"] for h in ripple.uncovered(rip, n)]
    return {"precedents": [r.get("id") for r in got.get("precedents") or [] if r.get("id") not in want_p],
            "hits": [h.get("id") for h in got["hits"] if h.get("id") not in want_h]}


def save_precedents(b, plan_rows: dict, answers: dict, k: int) -> None:
    """受けた答えの先行例の出典の確かめを控えに足す（控えに在る出典は書き換えない）"""
    cache = precedent_checks(b)
    for n, got in answers.items():
        by_id = {x["id"]: x["row"] for x in plan_rows.get(n) or []}
        for r in got.get("precedents") or []:
            src = str((by_id.get(r.get("id")) or {}).get("source") or "")
            if src and src not in cache:
                cache[src] = {"found": r.get("found"), "quote": r.get("quote"), "round": b.round, "pass": k, "item": n}
    path = _precedent_cache(b)
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonfile.write(path, cache, indent=2)


def synergy_schema(b) -> dict:
    """相乗りの審査の下請けの答えのファイルの型"""
    faces, _ = _faces_schema(b)
    return {"type": "object", "additionalProperties": False, "required": ["why", "faces"],
            "properties": {"why": {"type": "string", "minLength": 10}, "faces": faces,
                           converge.ORIGINS: copy.deepcopy(converge.ORIGIN_SCHEMA)}}


def _load(path: pathlib.Path, schema: dict) -> tuple:
    """(答え, 誤りの行)。読めない・型に合わない時は誤りの行（型の誤りは engine の validate_schema の $ から始まる行）"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, [f"JSON として読めない（{' '.join(str(e).split())}）"]
    errs = validate_schema(doc, schema)
    return (None, errs) if errs else (doc, [])


def _unit_name(names: list, k) -> str:
    return names[k - 1] if isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= len(names) else str(k)


def carried_hits(b, n: int, rip: dict) -> dict:
    """項目 n の今の往復の覆っていない当たりのうち、前の往復で同じ当たり（種類・場所・名が同じ）に block でない答えが在る物
    {当たりの id: 引き継ぐ答えの行（carried に答えた往復）}"""
    prev = {}
    for h in converge.answered_hits(b, n):
        key = (h.get("kind"), h.get("at"), h.get("name"))
        if key not in prev and h.get("answer") in converge.HIT_ANSWERS:
            prev[key] = h
    out = {}
    for h in ripple.uncovered(rip, n):
        old = prev.get((h["kind"], h["at"], h["name"]))
        if old is not None and old["answer"] != "block":
            out[h["id"]] = {"id": h["id"], "answer": old["answer"], "why": old.get("why", ""), "kind": h["kind"],
                            "at": h["at"], "name": h["name"], "carried": old.get("carried") or old["pass"]}
    return out


def design_gaps(b, faces, items: list, design_map=None) -> list[str]:
    """独立設計の引用の誤りの行（design.quote_gaps。設計が立たない run では空）。faces の unit_keys は単位の名に戻して重ね、案の行は
    壁打ちの控えの項目 items の行。design_map を渡す（None でない）と items の adds の name ごとの対応表も求める"""
    names = _names(b, NODE_OF["plan-review"])
    plan = converge.read(b).get("plan") or []
    rows = [{**plan[n - 1].get("row", {}), "item": n} for n in items if 1 <= n <= len(plan)]
    named = [{**f, "unit_keys": [_unit_name(names, k) for k in f.get("unit_keys") or []]} for f in faces if isinstance(f, dict)]
    return design.quote_gaps(b.dir, b.design_schema, named, rows, design_map)


def item_answer_gaps(b, n: int, got: dict, rip: dict) -> list[str]:
    """型の合った項目 n の答えの中身の誤り: 覆っていない当たり（前の往復の答えを引き継ぐ物 carried_hits は除く）の全部に
    ちょうど 1 つの答え・block と答えた当たりには block の face・face は項目 n の単位だけを名指す・前の往復の block
    （converge.item_blocks）は resolved か同じ key の face"""
    errs = [] if got.get("item") == n else [f"$.item: {n} でない（{got.get('item')!r}）"]
    want = [h["id"] for h in ripple.uncovered(rip, n)]
    carried = carried_hits(b, n, rip)
    ids = [h.get("id") for h in got["hits"]]
    errs += [f"$.hits: 覆っていない当たり {h} への答えが無い" for h in want if h not in ids and h not in carried]
    errs += [f"$.hits: {h} に答えが {ids.count(h)} つある（1 つだけ）" for h in sorted(set(ids)) if ids.count(h) > 1]
    blocks = converge.block_faces(got)
    if any(h.get("answer") == "block" for h in got["hits"]) and not blocks:
        errs.append("$.faces: 当たりに block と答えたのに severity block の face が無い")
    plan = converge.read(b).get("plan") or []
    mine = {str(k) for k in plan[n - 1]["unit_keys"]} if 1 <= n <= len(plan) else set()
    names = _names(b, NODE_OF["plan-review"])
    for i, f in enumerate(got["faces"]):
        out = [str(k) for k in f["unit_keys"] if _unit_name(names, k) not in mine]
        if out:
            errs.append(f"$.faces[{i}].unit_keys: 項目 {n} の単位でない {out}（項目どうしの穴は相乗りの審査が挙げる。"
                        "unit_keys は項目の unit_keys を字のまま）")
    prev = converge.item_blocks(b, n)
    keys = {f["key"] for f in got["faces"]}
    block_keys = {f["key"] for f in blocks}
    errs += [f"$.resolved: 前の block {k} を resolved に入れるか、同じ key で faces に挙げ直せ"
             for k in prev if k not in got["resolved"] and k not in keys]
    errs += [f"$.resolved: {k} は項目 {n} の前の往復の block に無い" for k in got["resolved"] if k not in prev]
    errs += [f"$.resolved: {k} が resolved と block の face の両方に在る（消えたか残ったかのどちらか 1 つ）"
             for k in got["resolved"] if k in block_keys]
    return errs + [f"$.faces・design_map: {e}" for e in design_gaps(b, got["faces"], [n], got.get(converge.DESIGN_MAP) or [])]


def check_item(b, k: int, n: int, rip: dict, pre: list | None = None) -> tuple:
    """(通った答え | None, 誤りの行, ファイルが無いか, 捨てた余りの行 _surplus)。通った答えは余りの行を取り除いた写し。
    pre は先行例の出典の開き手を決める開いた項目の並び（precedent_plan）"""
    path = answer_file(b, k, n)
    dropped = {"precedents": [], "hits": []}
    if not path.is_file():
        return None, [], True, dropped
    got, errs = _load(path, item_schema(b))
    if got is not None:
        rows = precedent_plan(b, [n] if pre is None else pre).get(n) or []
        dropped = _surplus(b, n, got, rip, rows)
        got = {**got, "hits": [h for h in got["hits"] if h.get("id") not in dropped["hits"]],
               **({"precedents": [r for r in got["precedents"] if r.get("id") not in dropped["precedents"]]}
                  if "precedents" in got else {})}
        errs = item_answer_gaps(b, n, got, rip) + _precedent_gaps(rows, n, got)
    return (None if errs else got), errs, False, dropped


def _tree_off(b, k: int, rip: dict) -> bool:
    """項目の控えが無い・支度がこの往復の下請けのファイルを書いていない（tree_part を呼ばなかった往復は置き場 ITEMS_DIR が
    無い）・1 項目で覆っていない当たりが無く答えのファイルも
    無い案は木にしない（返答の全体が審査役 1 つの答え）"""
    plan = converge.read(b).get("plan")
    return (not plan or not b.work(ITEMS_DIR.format(k=k)).is_dir()
            or (len(plan) == 1 and converge.open_items(b) == [1] and not ripple.uncovered(rip, 1)
                and not answer_file(b, k, 1).is_file()))


def tree_merge(b, bare: dict, tree: dict, resolved: list) -> dict:
    """事前審査の受け付けの木のまとめ（機械）。束ね役の返答の外した写し bare・束ね役の欄 tree・束ね役の resolved から、
    {review（盤面へ渡す返答）, resolved, synergy（相乗りの審査の face の key）, hits（{項目: 当たりの答え}）, origins（新しい block の
    出自の申告の行。下請けと相乗りの答えの物を集める）, files（往復の控えに写す答えのファイル）, gaps（拒む理由の行。在れば他は
    使わない）} を返す。木にしない案は審査役 1 つの返答のまま（出自の申告はその欄 origins。型は受け付けが役の型で確かめ済み）"""
    k = converge.pass_no(b)
    rip = _ripple_of(b, k) or {}
    base = {"review": bare, "resolved": resolved, "synergy": [], "hits": {}, "origins": [], "files": {}, "gaps": []}
    if _tree_off(b, k, rip):
        return {**base, "off": True, "origins": list(tree.get(converge.ORIGINS) or [])}
    plan = converge.read(b)["plan"]
    opened = converge.open_items(b)
    gaps, answers = [], {}
    for n in opened:
        got, errs, missing, dropped = check_item(b, k, n, rip, opened)
        for field, ids in dropped.items():
            for i in ids:
                b.trace(SURPLUS_OP, round=b.round, pass_=k, item=n, field=field, id=i)
        where = f"項目 {n}（{answer_file(b, k, n)}）"
        if missing:
            gaps.append(f"{where}: 答えのファイルが無い（その項目の下請けを起こせ）")
        gaps += [f"{where}: {e}" for e in errs]
        if got is not None:
            answers[n] = got
    if bare.get("faces") or bare.get("shrink") or tree.get(converge.ORIGINS):
        gaps.append("束ね役の faces・shrink・origins は空にする（項目の穴と出自は下請けの答えのファイルから機械がまとめる。写さない）")
    rows = tree.get(converge.ITEMS)
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    for n in opened:
        mine = [r for r in rows if r.get("item") == n]
        if len(mine) != 1:
            gaps.append(f"束ね役の items に項目 {n} の行が {len(mine)} 行ある（開いた項目ごとに 1 行）")
        elif n in answers:
            keys = [f["key"] for f in converge.block_faces(answers[n])]
            said = [x.get("key") for x in mine[0].get("blocks") or [] if isinstance(x, dict)]
            verdict = converge.VERDICTS[1] if keys else converge.VERDICTS[0]
            if mine[0].get("verdict") != verdict or sorted(map(str, said)) != sorted(keys):
                gaps.append(f"束ね役の items の項目 {n} が答えのファイルと食い違う（ファイルは {verdict}・block "
                            f"{'、'.join(keys) or '無し'}。下請けの要約のとおりに書け）")
    gaps += [f"束ね役の items の項目 {r.get('item')} は審査しない項目（閉じた・保留・案に無い）" for r in rows
             if r.get("item") not in opened]
    syn = None
    if (len(plan) >= 2 and opened and len(answers) == len(opened)
            and not any(converge.block_faces(a) for a in answers.values())):
        path = synergy_file(b, k)
        if not path.is_file():
            gaps.append(f"相乗りの審査（{path}）: 開いた項目の全部が clean の往復は、相乗りの審査の下請けを起こせ")
        else:
            syn, errs = _load(path, synergy_schema(b))
            gaps += [f"相乗りの審査（{path}）: {e}" for e in errs]
            if syn is not None:
                gaps += [f"相乗りの審査（{path}）: {e}" for e in design_gaps(b, syn["faces"], list(range(1, len(plan) + 1)))]
    faces = [f for n in opened if n in answers for f in answers[n]["faces"]] + list((syn or {}).get("faces") or [])
    keys = [f["key"] for f in faces]
    gaps += [f"face の key {key} が 2 つの答えに在る（後に書いた項目の key を変えよ）" for key in sorted(set(keys))
             if keys.count(key) > 1]
    if gaps:
        return {**base, "gaps": gaps}
    now = {f["key"] for f in faces}
    faces += [f for f in converge.carried_notes(b) if f.get("key") not in now]   # suggest は後の往復の返答に残す（修正の段へ）
    review = {**bare, "faces": faces, "shrink": [x for n in opened for x in answers[n]["shrink"]]}
    if not faces and not review.get("faces_none"):
        review["faces_none"] = " / ".join(f"項目 {n}: {answers[n]['checked']}" for n in opened)
    files = {ANSWER_FILE.format(n=n): str(answer_file(b, k, n)) for n in opened}
    if syn is not None:
        files[SYNERGY_FILE] = str(synergy_file(b, k))
    return {"review": review, "resolved": list(dict.fromkeys(x for n in opened for x in answers[n]["resolved"])),
            "synergy": [f["key"] for f in (syn or {}).get("faces") or []],
            "origins": [o for x in [*(answers[n] for n in opened), syn or {}] for o in x.get(converge.ORIGINS) or []],
            "hits": {n: _hit_rows(b, n, rip, answers[n]["hits"]) for n in opened}, "files": files, "gaps": [],
            "precedents": (precedent_plan(b, opened), answers, k)}


def _hit_rows(b, n: int, rip: dict, answered: list) -> list:
    """往復の控えに置く項目 n の当たりの答え（下請けの答えに当たりの種類・場所・名を足し、答えの無い当たりは引き継いだ答え）"""
    where = {h["id"]: {"kind": h["kind"], "at": h["at"], "name": h["name"]} for h in ripple.uncovered(rip, n)}
    got = {h["id"]: {**h, **where.get(h["id"], {})} for h in answered}
    carried = carried_hits(b, n, rip)
    return [got.get(i) or carried[i] for i in where if i in got or i in carried]


def _review_rules(b, main_prompt) -> str:
    """描いた事前審査の指示書の本文のうち RULES_FROM から末尾まで（リポジトリと読む版・審査の決まり・返し方・人の方針・言語）。
    切り出せなければ RULES_MISSING（束ね役の指示書を読ませる）"""
    body = getattr(b, "review_body", "")
    at = body.find(RULES_FROM)
    return body[at + 1:].strip() if at >= 0 else RULES_MISSING.format(main=main_prompt)


def brief_head(b, main_prompt) -> str:
    """下請けのファイルの共通の頭（全部の項目と相乗りの審査で同じバイト）: 役の定義・関所の項目の決め手・既にある物を量ったかと
    人に回す物の挙げ方（REUSE_REVIEW・HANDOFF_REVIEW）・審査の決まり・判定者の
    見立て・独立設計（design_only）・答え方の型"""
    diag = (b.record.get("process") or {}).get("diagnosis") or {}
    framing = {k: diag[k] for k in ("framing", "one_shot") if k in diag}
    return "\n\n".join(x for x in (
        BRIEF_TITLE, SUB_HEAD, gatemarks.HEAD[NODE_OF["plan-review"]], REUSE_REVIEW, HANDOFF_REVIEW, concepthome.REVIEW_ASK,
        _review_rules(b, main_prompt),
        f"判定者の見立て: {json.dumps(framing, ensure_ascii=False, indent=1)}" if framing else "", design_only(b),
        SUB_FORMAT.format(schema=json.dumps(item_schema(b), ensure_ascii=False))) if x)


def _item_units(b, unit_keys) -> list:
    keys = {str(k) for k in unit_keys or []}
    return [{k: u[k] for k in ("key", "label", "disposition", "reason") if k in u}
            for u in b.record.get("units") or [] if u.get("key") in keys]


def _diff_part(b, n: int) -> str:
    """2 往復目から: 前の往復のこの項目の案の行と今の行の差分（unified diff）と DIFF_ASK。行は往復の控えの物（関所の決め手の欄を
    外し、works の欄を重ねた物。boardview.open_pass）。約束の欄（planmarks.contract_diff。直しが触れる物や確かめる物を変え、行の
    差分に現れない読み直しを要る）が変わった項目（変わった欄の名を DIFF_FULL_ASK の前に言う）と、変わった字の割合が
    DIFF_FULL_SHARE を超えた項目は、差分に絞らず DIFF_FULL_ASK。字の数えは行の単位の比べで、置き換えた行の組は共通の頭と尾を
    除いた字、足した・消した行は全部の字を、前と今の字数の和で割る。前の行が無ければ空（全部を見る）
    （元 今の works の commit d51cc183 の works/blk-plan/lib/planblk.py:982 _diff_part）"""
    old = converge.prev_row(b, n)
    plan = converge.read(b).get("plan") or []
    new = plan[n - 1].get("row") if 1 <= n <= len(plan) else None
    if old is None or new is None:
        return ""
    before, after = (json.dumps(row, ensure_ascii=False, indent=1, sort_keys=True).splitlines() for row in (old, new))
    lines = list(difflib.unified_diff(before, after, "前の往復", "今の往復", lineterm="", n=2))
    fields = planmarks.contract_diff(old, new)
    if fields or _changed_chars(before, after) > DIFF_FULL_SHARE * (len("\n".join(before)) + len("\n".join(after))):
        ask = (f"約束の欄（{'・'.join(fields)}）が変わった。" if fields else "") + DIFF_FULL_ASK
    else:
        ask = DIFF_ASK
    return f"{DIFF_HEAD}\n\n{ask}\n\n```diff\n" + ("\n".join(lines) or "（変わっていない）") + "\n```"


def _changed_chars(before: list, after: list) -> int:
    changed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        gone, came = "\n".join(before[i1:i2]), "\n".join(after[j1:j2])
        head = len(os.path.commonprefix([gone, came]))
        tail = len(os.path.commonprefix([gone[head:][::-1], came[head:][::-1]]))
        changed += 0 if tag == "equal" else len(gone) + len(came) - 2 * (head + tail)
    return changed


def _carried_part(b, n: int, rip: dict) -> str:
    rows = carried_hits(b, n, rip)
    if not rows:
        return ""
    return CARRIED_HEAD + "\n\n" + "\n".join(f"- {i}: {h['answer']}（{h['why']}）" for i, h in rows.items())


def _errors_part(n: int, path: pathlib.Path, errs: list) -> str:
    doc = json.dumps({"item": n, "file": str(path), "errors": errs}, ensure_ascii=False, indent=1)
    return f"{ERRORS_HEAD}\n\n前の答え {path} を Read で読み、下の誤りだけを直して同じファイルに書き直せ。\n\n```json\n{doc}\n```"


def _opened(b, rows: list) -> list:
    """今の往復の事前審査が見る項目の番号（項目の控えが在れば開いた項目 converge.open_items、無ければ案の全部の項目）"""
    plan = converge.read(b).get("plan")
    return [n for n in (converge.open_items(b) if plan else range(1, len(rows) + 1)) if n <= len(rows)]


SYNERGY_HEAD = promptsection.Section("## この下請けの審査: 相乗りの審査", source="fn:planblk.tree_part")
ITEM_PLAN_HEAD = promptsection.Section("### 項目 {n} の案", source="fn:planblk.tree_part")
ITEM_UNITS_HEAD = promptsection.Section("### 項目 {n} の単位（判定）", source="fn:planblk.tree_part")
ALL_ITEMS_HEAD = promptsection.Section("### 項目の全部（閉じた項目も含む）", source="fn:planblk.tree_part")
OVERLAPS_HEAD = promptsection.Section("### 項目どうしの重なり（機械が範囲と波及の一覧から引いた）", source="fn:planblk.tree_part")


def tree_part(b, main_prompt: pathlib.Path) -> str:
    """束ね役の頼みの節。開いた項目ごとの下請けのファイルと（項目が 2 つ以上なら）相乗りの審査のファイルを今の往復の
    ITEMS_DIR に書き、その置き場を並べる（下請けの答えの置き場 answers_dir も作る）。下請けのファイルは共通の頭（brief_head）と
    その項目の節（案・単位・波及の一覧・前の往復の block）を字のまま持つ。出し直しでは、答えのファイルが確かめを通った項目を
    済んだ下請けに並べて起こし直させず、通らなかった項目の下請けのファイルに機械の読める誤りの一覧を貼る。項目の控えが無ければ空"""
    rows = _item_rows(b)
    if not rows:
        return ""
    k = converge.pass_no(b)
    doc = _ripple_of(b, k) or {"items": [], "overlaps": [], "error": "波及の一覧のノードがこの往復の一覧を置いていない"}
    folder = b.work(ITEMS_DIR.format(k=k))
    folder.mkdir(parents=True, exist_ok=True)
    answers_dir(b, k).mkdir(parents=True, exist_ok=True)
    plan = converge.read(b).get("plan")
    opened = _opened(b, rows)
    head = brief_head(b, main_prompt)
    pre = precedent_plan(b, opened) if plan else {}
    done, todo, retry = [], [], False
    for n in opened:
        path = folder / f"item-{n}.md"
        got, errs, missing, _ = check_item(b, k, n, doc, opened) if plan else (None, [], True, {})
        if got is not None:
            done.append(f"- 項目 {n}: {path}")
            continue
        retry = retry or not missing
        it = rows[n - 1]
        body = "\n\n".join(x for x in (
            head, ITEM_HEAD.format(n=n), SUB_ITEM_ASK.format(n=n, answer=answer_file(b, k, n)),
            f"{ITEM_PLAN_HEAD.format(n=n)}\n\n```json\n{json.dumps(it, ensure_ascii=False, indent=1)}\n```",
            f"{ITEM_UNITS_HEAD.format(n=n)}\n\n```json\n{json.dumps(_item_units(b, it.get('unit_keys')), ensure_ascii=False, indent=1)}\n```",
            _precedent_part(pre.get(n) or [], n), ripple.section(doc, n), _carried_part(b, n, doc), _item_history(b, it.get("unit_keys") or []),
            _diff_part(b, n), _errors_part(n, answer_file(b, k, n), errs) if errs else "") if x)
        path.write_text(body + "\n", encoding="utf-8")
        todo.append(f"- 項目 {n}: {path}")
    last = {it["n"]: it for it in (converge.read(b)["passes"][-1].get("items") or [])} if converge.read(b)["passes"] else {}
    parts = [AGG_HEAD, AGG_ASK]
    if done:
        parts.append(DONE_HEAD + "\n" + "\n".join(done))
    if todo:
        parts.append((REDO_HEAD if done or retry else OPEN_HEAD) + "\n" + "\n".join(todo))
    rest = [f"- 項目 {n}（{last[n]['state']}）" for n in range(1, len(rows) + 1) if n not in opened and n in last]
    if rest:
        parts.append("審査しない項目（前の往復で閉じた・保留にした）:\n" + "\n".join(rest))
    parts.append(AGG_MERGE)
    if len(rows) >= 2:
        syn = folder / "synergy.md"
        states = [f"- 項目 {n}（{(last.get(n) or {}).get('state', converge.OPEN)}）: "
                  f"{json.dumps(it, ensure_ascii=False)}" for n, it in enumerate(rows, 1)]
        over = "\n".join(f"- {o['at']}: 項目 {', '.join(map(str, o['items']))}" for o in doc.get("overlaps") or []) or "- 無い"
        syn.write_text("\n\n".join([
            head, SYNERGY_HEAD,
            SUB_SYNERGY_ASK.format(answer=synergy_file(b, k), schema=json.dumps(synergy_schema(b), ensure_ascii=False)),
            *([converge.ORIGIN_ASK] if k > 1 else []),
            f"{ALL_ITEMS_HEAD}\n\n" + "\n".join(states),
            f"{OVERLAPS_HEAD}\n\n" + over]) + "\n", encoding="utf-8")
        parts.append(AGG_SYNERGY.format(path=syn))
    return "\n\n".join(parts)


# ---------------------------------------------------------------- 節


_WRITERS = ("plan", REVISE_ROLE)
_ROLES = (*ROLES, REVISE_ROLE, DESIGN_ROLE)
RECEIVES = [
    *(promptsection.Receive(role, head) for role in _WRITERS for head in (
        PLAN_SLOTS_HEAD, PRESCRIPTION_HEAD, PRESCRIPTION_UNIT_HEAD, VERIFY_HEAD, ripple.UNITS_HEAD, ripple.UNIT_HEAD, structmark.PLAN_HEAD,
        carry.PRIOR_HEAD, carry.REDESIGN_HEAD, converge.FACE_HEAD)),
    *(promptsection.Receive("plan", head) for head in (worldmark.HEAD,)),
    *(promptsection.Receive("plan-review", head) for head in (
        DESIGN_HEAD, planmarks.REVIEW_HEAD, planmarks.FIELDS_ITEM_HEAD, planmarks.DEVIATION_HEAD, AGG_HEAD, ITEM_HEAD, SYNERGY_HEAD,
        ITEM_PLAN_HEAD, ITEM_UNITS_HEAD, ALL_ITEMS_HEAD, OVERLAPS_HEAD, BRIEF_TITLE, SUB_FORMAT, DIFF_HEAD, CARRIED_HEAD, PRECEDENT_HEAD,
        ERRORS_HEAD, HISTORY_HEAD, ripple.HEAD, ripple.ITEM_HEAD, ripple.ITEM_KEYS_HEAD, converge.PASS_HEAD, converge.FACE_HEAD)),
    *(promptsection.Receive(role, head) for role in ("plan", "plan-review")
      for head in (libdocs.TITLE, libdocs.DOC_TITLE, libdocs.FRAGMENT_HEAD, libdocs.LIB_HEAD)),
    *(promptsection.Receive(DESIGN_ROLE, head) for head in (
        design.DESIGN_PREMISE_HEAD, design.HUMAN_HEAD, design.NAMED_HEAD, design.NAMED_BODY_HEAD, design.MAP_HEAD, design.MAP_FILE_HEAD)),
    *(promptsection.Receive(role, head) for role in _ROLES for head in (rolekit.REJECT_HEADING,)),
    *(promptsection.Receive(role, head) for role in (*ROLES, REVISE_ROLE)   # 旗 concept-map（包みが足す）
      for head in (concepthome.MAP_FOUND_HEAD, concepthome.MAP_NONE_HEAD)),
]
