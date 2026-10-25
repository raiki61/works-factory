# 直し方の型の段 1・PR B の実装の控え（受付 20261025-095016-54abf0）

- 何の話か: 設計の下書き [2026-10-24-fix-weapons.md](2026-10-24-fix-weapons.md)（以下「下書き」）の 4.4 の作る物 9（修正役の指示を付録 A の行き先どおりに型ごとの書き手へ移す）と、PR A（#869）が PR B に回した物のうち頼みが名指す物を作る PR B の、実装の部署の控え。PR A の控えは [2026-10-25-fix-weapons-stage1-a.md](2026-10-25-fix-weapons-stage1-a.md)。
- この控えに書く物: 下書きが黙っていた所で実装の部署が決めた事（持ち主・窓口が覆せる）と、どの commit で何を閉じたか。会話は納品のたびに空になるので、続きはここと PR の本文から読み直す。済んだ事の記録で、読み手に頼む作業は無い。覆したい物があれば、見出しに「覆せる」とある 1 節・3 節の行を持ち主（この工場の持ち主で、設計の決めを出す人）か窓口（持ち主と会話して工場への頼みを取り次ぐ AI）に伝える。

## 1 形の決め（実装の部署の決め。持ち主が覆せる）

1. 型ごとの書き手の node を置く。組の子（1 回目の段）は `tdd-close`・`pin`・`tidy`・`static`・`variant`・`remove`、親（裁定の後の段）は `pin-ruled`・`tidy-ruled`・`static-ruled`・`variant-ruled`・`remove-ruled`。どれも返答の形は今の修正役の形（`*fix_reply`）に `evidence.kinds` を足した物で、必須の欄と空にできない欄を減らさない。
2. 型を 1 つずつ順に回す: 外の輪 `writers-loop`（`fresh_context: true`。1 周が型 1 つ）の中に、今の修正の輪 `fix-loop`（`fresh_context: false`）を入れ子に置く。外の輪の頭の script `writer-pick` が、注文の在る型を `writers.SEQUENCE`（`workflows/fix/src/writers.py`）の順に 1 つ選んで置き場の `writer.json` に書き、その型の段の頭（段の頭の木・除くパスの姿・注文の `since`）を控え直す。内の輪の中では、書き手の node を 1 本の鎖（どの層も node 1 つ）に並べ、`fix-prep` が返す型の名で `when:` が 1 つだけを起こす。
   - 訳: 書き手を同じ層に並べると Archon が並んだ層として会話を切る（今の `ConversationCase`）。型ごとに別の輪を YAML に 6 本書くと node が 36 増える。入れ子にすると、内の輪の 1 周目はいつも新しい会話で起き（`dag-executor.ts` の「i === 1 ? undefined」）、型の中の出し直しは同じ会話を継ぐ。型どうしは会話を分け合わない。
   - 順: 1 回目の段は tdd の輪の後に `tdd-close` → `pin` → `tidy` → `static` → `variant` → `remove`（PR A の「tdd の輪が先」を保ち、残りは箱の順）。依存の辺での並べ替えはしない（22.6 の残り。守れない対は今の `unsatisfied` が名で書く）。
3. tdd の輪の単位の `changes` の行は、tdd の型の閉じの書き手 `tdd-close` が書く（下書き 3.1 の「輪が自分で changes を書く」を、fix の段の返答に欄を足す形でなく、輪の後の tdd の型の node で受けた）。訳: 周の全体の欄（`plan_faces`・`interactions`・`wrote_refs` など）は返し全体への答えで、段ごとの返答には置き場が無い。tdd の段の返答の形（段で欄が変わる 1 つの形）に必須の欄を足すと、段ごとに必須を変えられない（`anyOf` は形の検査が拒む）。`tdd-close` は今の修正役の、TDD の後に写す役目だけを tdd の型の側に移した物で、起こす AI の数は今と同じ（今の修正役は止めの無い組でいつも起きた）。修正役（variant ほか）からは TDD の要約を読む指示を全部外した（付録 A の F26 前半・F107・G14）。
4. 型ごとの状態: 拒否の控えと回の数え（`fix-accept-<型>`・`fix-ruled-accept-<型>`）・渡した証拠の控え（`<node>-delivered.json`）・段の頭の木は型ごと。受け付けの直す義務は、その型の注文の単位（組の直す義務との積）。受けた返答・単位の結末・閉鎖の表・数え直しの件数は、型ごとに受けた物を単位で重ねる（後の型が前の型の行を消さない）。範囲の相談の枠は段で 1 つ（今のまま）。
5. 指示の文の置き場: 今の `parts/fixer.md` を `parts/writer-top.md`（頭の材料の節）と `parts/writer.md`（決まりの本体）に割り、型ごとの頭（役の定義。付録 A の F21「型ごとの頭に言い直す」）を `parts/<型>.md` に置く。node の md は `{part:<型>}` の 1 行。型だけの文（variant の下請けの節・F123 の壊して赤・F135・変える段の申し出 `not_red` と brief の決まり 4・5）は、本体の中の段落の印で、`src/prompts.py` の型の表 `WRITER_WHEN` が型から引いた真偽で選ぶ（段落の外に出すと文の並びが変わるため）。

## 2 進み（commit ごと）

- [x] 型ごとの書き手（移し）: b2f101d7
- [x] 消す 11（下書きの付録 A は、今の修正役の指示を 1 項目ずつ番号〔F12・W13・BR3 など〕で挙げ、型を分けた後の行き先を付けた表。行き先が「消す」〔型を分けると要らなくなるので指示の文を消す〕の項目が 11 ある。その 11 を項目ごとに commit した。条件と代わりの照らしは各 commit の本文と PR の本文）: 5a16ada0（F12・F13・F26 の前半）・619bf8d4（F107・F108・F148b・G14・G13 の 3 文目・G18）・88226c38（F25）・16eabebc（W13）・1d746211（BR3）。並べた番号は 12 あるが、G13 の 3 文目は 11 に数えない。G13 の行き先は variant で、その中の 3 文目だけが TDD の要約を指す文なので、G14 と一緒に消した（付録 A の G13 の行）。
- [x] アセットの試験: 7acf0fc7（tests/blocks/fix/test_assets.py）
- [x] PR A の残り: 申し出の種類 red_at_base（下ごしらえ pin が今の振る舞いを留めるために足した試験が、修正前の版で落ちる時に出す申し出。下書きの 3.6）の 4 つ（種類の一覧への追加・申し出の欄 which_is_right〔どちらが正しいと見たか〕を test か unknown に限る照らし・裁定を fix_plan_item と ask_human に限る受け付け・指示の文）・pin の 1 文・retry の tdd の試験・この控えの 4 節

## 3 消すの中で決めた事（実装の部署の決め。持ち主・窓口が覆せる）

1. lib/seat.py の表 SEATS（役の名 → その役の会話に載せる、借りた superpowers の型の節）から fix・fix-ruled を外した。F108・F148b で、修正役の会話に借りた implementer の型を直に載せる段落を消したので、この 2 行を読む所が無い。同じファイルの表 OVERLAY_KINDS（役の名 → その役に載せる、借りた型の読み替え lib/borrow/unattended.md の節）の fix の行は残す。書き手の指示に載り、書き手が項目ごとに起こす下請け（実装の子と審査の子）にも同じファイルを読ませるため。
2. W13: 段落の名 where_fixer を where_writer に替え、文を「返答の evidence.kinds に種類ごとに 1 行」にした。返答の closure.verified_how の欄は形に残す（必須を減らさない）。
3. BR3: 修正案の項目の欄の形 lib/plan-item-fields.schema.json に allowed_paths・out_of_scope を required で足した。下書きが名指す fix の入口の形 workflows/fix/schemas/plan-fields.schema.json は今のリポジトリに無い。fix の block の入力 port（YAML の inputs:）の plan は、形を workflows/.shared/schemas/plan-fields.schema.json と名指し、その形の fields の行（項目 1 つの欄）は lib/plan-item-fields.schema.json を名指す。項目の欄の形の住処はここ 1 か所なので、ここに足した。この形を読む plan・line・spec-driven・structure の試験の筋書きに範囲の欄を足した。lib/planrange.py の NO_SCOPE の枝（範囲の欄の無い修正案の控えなら範囲を照らさず、照らさなかった訳だけを返す分岐）は残す: 凍結の控えは planmarks.frozen が port の形の検査を通さずに読むので、範囲の欄の無いファイルが置かれた時に照らさなかった訳を報告に残すため。

## 4 PR A の控えの 5 節で後に回した nit と、再レビューの nit の扱い

1. retry の返りの tdd を縛る試験: tests/blocks/fix/test_suite_fix.py の assert_tdd_follows_taken。起動スクリプトの書き直しの後のやり直し（suitefix.retry）が返す tdd（TDD の輪を回すか）を、書き直しが効いた時と結末が取れない時の両方で、base.json の taken（直す前の試験の結果が取れたかの印）と同じことを照らす。taken と、組の頭が tdd-start.json に書く no_suite（試験の実行器が無く止める印）が食い違う組（結果が取れたのに no_suite が立つ組）は筋書きを組めず、照らしていない。
2. 下ごしらえ（pin）を keep の組（振る舞いを変えない型〔tidy など〕だけの組）の前に挟む所（orders.compute）: 直さない。訳: 型の順の表 SEQUENCE（workflows/fix/src/writers.py）は pin を tdd の後・ほかの型の前に回すので、pin の注文の在る組では pin の書き手が先に起きる。keep の組に pin の注文を機械が足す決まりは下書きに無い。下ごしらえを付けるかは、計画の役（AI）が項目の route の語 pin で名指して決める（下書きの 3.6）。機械が足すと、この判断を機械が奪う。今は挟まずに受け付けで止まる（fail closed。pin.tests_only と 0 件の止め）。
3. 消した試験 removed_tests を拾うのが .py だけ: 直さない。訳は PR A の控えの 5 節のとおり（試験の id を引く口 scope._test_ids が Python の構文木で読む。ほかの言語の試験の id を引く口を決める時に直す）。
4. 計画の役の指示 workflows/plan/prompts/plan-writer.md の 156 行目（仕様の道の節。仕様の書き手が「TDD で直す所」を名指す run の道）の「仕様が名指さない項目は static・tidy・pin を取ってよい」の 1 文: 残す。訳: 仕様の道の決まりが縛るのは TDD で直す所だけで、static・tidy・pin は TDD の道ではない。消すと、仕様が名指さない項目は全部 route の語 direct（今の修正役の道。段 1 では型 variant が受ける）になり、下書きの 4.4 の作る物 7 が足した route の語 static・tidy・pin を仕様の道だけが使えなくなる。
5. pin の 1 文（下書きの 4.4 の作る物 6 が名指す、下ごしらえの指示の 1 文）は parts/pin.md の役の頭の前に「Do not rewrite configuration files that exist in the version before the fix.」と置いた。受け付けの照らし（起点の木に在る設定のファイルの書き換えを拒む）は PR A に在る。
6. red_at_base の指示の文は、申し出（書き手が依頼・試験・コードの食い違いなどを見つけた時に、直さずに返答へ積んで裁定を待つ行。not_red・scope_needed などの種類を持つ）の種類を並べる 2 か所（parts/writer.md と共通の断片 writer-rules.md）に同じ字で足した。「only when your role pins current behavior」と書き、書き手ごとに段落で分けてはいない（種類の並びは今もどの書き手にも同じ物が載るため）。
7. PR A の控えが B とした物のうち、ここで手を付けなかった物（`kinds_rows`・`sites_per_test`・`sites_shape`・`unit_red`・change の箱の義務・`na`・`evidence.named`・`unsatisfied`・注文の形の 3 欄 `run`・`asks_answered`・`orders.<weapon>`）は段 2 へ回した。各物の中身は PR A の控えの 3 節と 5 節、行き先と訳は同じ控えの 6 節。
