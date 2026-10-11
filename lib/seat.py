"""借りたスキルの座: 借りた superpowers の節（bin/_lib/borrow/seams.json の 1 項目）を、修正のブロックの役の指示書に載せる 1 節の
文を組む。元 works/.shared/core/seat.py（修正役の並べの枝の座と、下請けのファイルを単位の worktree で読む決まりは、枝が無いので外した）。

語:
- 節（seam）: seams.json の 1 項目。use_as が skill（スキル 1 本を Skill の道具で読ませる）か prompt（部品の型の穴を埋めて指示書に置く）
- 座: 節を役に載せる口。SEATS（役の名 → 節の名）が表で持つ
- 読み替え: skill_overlay（bin/_lib/borrow/unattended.md の頭の 1 行と全文）。座の末尾にいつも載る

口:
- carries(node)・SKILL_NODES: 座が載る役・座が skill の役（YAML の skills: と一致）
- pin_problems(src, item)・pinned(): 写しが固定（borrow.json の superpowers.pin）と合うかを照らし (借りる物, 写しの置き場) を返す
  （合わなければ ValueError。照らしは bin/_lib/spseam.pin_problems の写し）
- fill(seam_id, values): 部品の型の穴を埋めた本文（bin/_lib/spseam.py の fill と同じ決まり。試験が同じ文を返すことを縛る）
- section(node, values): 座の文。載らなければ空。頭 → 節の種類ごとの本文 → 読み替え。1 回目の差分の審査役（review）の型の後ろには
  判定の語の欄の表（words_table）、語に conflict.WORD を持つ節（implementer）の後ろには申し出の種類の手引き DIVERGENCE_HINT
- g1_prompt(seam_id, values)・g1_section(rows)・g1_diff_cmd(base, patch): 修正役（fix・fix-ruled）が直す単位の項目ごとに Agent の
  新しい会話で起こす下請け（実装役・審査役）のファイルの中身と、修正役の指示書の節と、審査役に渡す差分のファイルを書くコマンド
- skill_overlay()・query_rule(): 読み替えの段と、下請けのファイルに字のまま載せる検索語の規律の塊（lib/agents/judge.md）

lib/ は bin/ を import しない（lib/AGENTS.md の E3）ので、写しと節の表は置き場 BORROW_DIR のファイルを読む（起動の bin/_lib/toolset.py
が同じ写しを run の隔離した設定へ写す。写しを変えるのは toolset の vendor だけ）。食い違い・型の穴の埋め残りは ValueError で名指す。
"""
import hashlib
import json
import os
import pathlib
import re
import shlex
import sys
import textwrap

sys.dont_write_bytecode = True

import conflict  # noqa: E402  （申し出の種類の語 DIV_KINDS と状態の語の読み替え WORD）
import promptsection  # noqa: E402

BORROW_DIR = pathlib.Path(__file__).resolve().parents[1] / "bin" / "_lib" / "borrow"   # 借りた物の置き場（bin/_lib/spseam.BORROW_DIR）
SEAMS_FILE = "seams.json"
OVERLAY_FILE = "unattended.md"
OVERLAY_HEAD = ("借りたスキル（superpowers）を読む時は、下の読み替えに従え。これは役への直の指示で、スキルの文より勝つ。"
                "Agent で下請けを起こすなら、その prompt に、このファイル {path} を Read せよと書け。")
BRACKETED = re.compile(r"\[[^\[\]]+\]")   # 型の本文の角括弧の語（bin/_lib/spseam.BRACKETED）
FENCE, PROMPT_LINE = "```", "  prompt: |"
QUERY_RULE_SOURCE = pathlib.Path(__file__).resolve().parent / "agents" / "judge.md"   # 検索語の規律の正本（写し）
QUERY_RULE_HEAD = "- **検索語に対象の名前を載せるな。**"

SEATS = {"tdd": "tdd", "fix": "implementer", "fix-ruled": "implementer", "review": "task-review",   # 役の名 → 節の名
         "refix": "receiving-review", "refix2": "receiving-review"}
SKILL_NODES = frozenset({"tdd", "refix", "refix2"})   # 座が skill の役（YAML の skills: を持つ節。試験が一致を縛る）
NONE = "（無し）"   # 型の穴に入れる物が無い時の値（人の方針の文書が無い run の [GLOBAL_CONSTRAINTS] など）
# 差分の審査役の型（task-review）の出口の語（216 の works の語）→ 差分の審査の返答の 2 判定の欄（deltamarks.KEYS）と欄の語
# （deltamarks.COMPLIANCE・QUALITY）。審査役の座の型の後ろに words_table の表で載り、役は型の語をこの欄に書く
VERDICT_SEAM = "task-review"
VERDICT_WORDS = {"compliance_pass": ("compliance", "pass"), "compliance_fail": ("compliance", "fail"),
                 "compliance_unverifiable": ("compliance", "unverifiable"),
                 "quality_pass": ("quality", "pass"), "quality_fail": ("quality", "fail")}
WORDS_HEAD = promptsection.Section("### 判定の語の欄（型の語がどの欄のどの値に当たるかを示すだけ。欄の値は commands/delta-review.md の『2 つの判定』の"
                                   "決まりで返答の行から決まり、この表と食い違えば指示書が勝つ）", source="fn:seat.words_table")
# 表の後ろの注の行（型の語に依らずに欄の値が決まる場合。deltamarks.gaps の決まり）: (場合, 欄の値)
NOTE_ROWS = (("材料の plan_items が空", "`compliance.verdict`: `not_applicable`"),
             ("準拠の行に結ばれない穴が faces に 1 つでも在る", "`quality.verdict`: `fail`"))
# 申し出の種類の手引き: 語ごとの場面（conflict.DIV_KINDS と同じ語・同じ順。試験が照らす）。欄と語の決まりの正本は指示書の
# 『食い違いの申し出』の節（writerules/common.md）で、ここは状態の語から kind を引き当てる 1 行ずつ
DIVERGENCE_SCENES = {
    conflict.BRIEF_VS_JUDGMENT: "brief と、判定・依頼・修正の前に人が答えた条件が食い違う（`between` にその単位の brief の行）",
    conflict.UNNAMED_TEST_BROKE: "修正案にも裁定にも名指されていない既存のテストが、直すと落ちる・外すしかない",
    conflict.NOT_RED: "受け入れのテスト・名指しの書き換えが、案どおりに書いても赤にならない・赤の種類が案と違う",
    conflict.SCOPE_NEEDED: ("brief や案の範囲の外を触らないと緑にならない・判定者の問いの数え直しが閉じない（範囲の相談の節が"
                            "在れば、先に返答の consult で相談して許されなかった時。下請けは相談が要ることをまとめ役に報告する）"),
    conflict.QUERY_HITS_FIXED: (f"判定者の問いが直した後の正しい形にも当たる（`{conflict.WHICH_FIELD}` は {conflict.QUERY}・"
                                f"`{conflict.CORRECT}` が要る）"),
    conflict.NEEDS_CONTEXT: (f"方針・依頼の意図・どれが正しいかが材料から決められず、人か依頼の答えが要る"
                             f"（`{conflict.WHICH_FIELD}` は {conflict.UNKNOWN}）"),
}
DIVERGENCE_HINT = "\n".join([
    f"実装役の型の状態の語 NEEDS_CONTEXT・BLOCKED（works の語 {conflict.WORD}）に当たる時は、その単位を直したことにせず、"
    f"食い違いの申し出 conflicts の 1 件で返す。`{conflict.KIND_FIELD}` は起きた場面で次のどれか（欄の決まりは指示書の"
    "『食い違いの申し出』の節）:",
    *(f"- `{k}`: {DIVERGENCE_SCENES[k]}" for k in conflict.DIV_KINDS)])
HEAD = promptsection.Section("## 借りたスキルの座", source="fn:seat.section")
SCENE = "works の修正の段。流れ・機械の関門・commit は線が持つ。TDD の輪で直した単位は輪の要約に在る"
NO_REPORT_FILE = "ファイルに書かない。返答は指示書の『返答の欄』の JSON"
WINS = "この指示書の段の約束（返す JSON・機械の関門・段の順）と下の読み替えは、借りた文に勝つ"   # どちらの種類の座も同じ 1 段落
# 座のファイルを指示書と別に読む役（座の中の「この指示書」が座のファイルを指して読める）は、勝つ指示書を名指す段落に替える
WINS_OF = {"review": "役の指示書 commands/delta-review.md の約束（返す JSON・読む義務・判定の欄の値の決め方）と下の読み替えは、"
                     "借りた文に勝つ"}
SKILL_LEAD = "Skill の道具で `{skill}` を読み、その手順で進めよ。"   # skill の座だけが WINS の前に足す 1 文
APPLIES, NOT_APPLIES = "効く所:", "効かない所（従わない）:"
PROMPT_HEAD = promptsection.Section("### 下請けの型（superpowers の {file}。works の節で包んだ物）", source="fn:seat.section")
ITEM = "superpowers"   # borrow.json の借りる物の名

# 下請けを回す修正役の節（依頼 243 の 2）
G1_HEAD = promptsection.Section("## 下請けを回す", source="fn:seat.g1_section")
# 2 つ目からの項目の実装役の prompt の後ろに修正役が足す節の見出し（前の項目の会話の履歴の代わりの引き継ぎ。依頼 243 の 2）
G1_HANDOFF_HEAD = promptsection.Section("## 前の項目の引き継ぎ（修正役が前の項目の実装役の報告から書いた物）",
                                        human="修正役が下請けの頼みに自分で足す節の見出し（機械は貼らず、手順の文が名指す）")
# 修正役の節に載る 1 段落（修正役の前に TDD の輪が単位を直す。輪で直した単位は項目に載らない。fixrules.prep）
G1_LOOP_NOTE = ("TDD の輪で直した単位（輪の要約のファイルの「輪で直した単位」）は下の項目に載らない。その単位には下請けを"
                "起こさず、指示書の『読む物』の TDD の輪の結果のとおり changes に 1 行を書く")
G1_REPORT = "実装役の最後のメッセージを、この型の後ろに貼る"   # 審査役の型の [REPORT_FILE]
# 審査役の型の [HEAD_SHA]。works は commit しないので差分は作業ツリーと base の間。型の `git diff [BASE_SHA]..[HEAD_SHA]` は
# g1_prompt が `git diff <base>` に直す（commit の範囲は空になる。コマンドに文を残さない。Preflight F20）。Head の行にだけ残る
G1_HEAD_SHA = "作業ツリー（works は commit しない）"
G1_IMPL_REPORT = "ファイルに書かない。報告の全部を最後のメッセージに書く（修正役が審査役にそのまま渡す）"   # 実装役の型の [REPORT_FILE]
# 審査の前に修正役が走らせる差分のファイルのコマンド。{patch} は支度が決めた置き場（run の成果物の置き場。作業ツリーの外）の
# 絶対パス（shell の字で囲んだ物）で、審査役の型の [DIFF_FILE] も同じパス。リポジトリの根で、作業ツリーと base の差分と、未追跡の新しいファイルごとの全文の差分を書き、最後にそのパスを出す
# （最後の git diff --no-index は差分が在ると 1 を返すので、echo で終えて 0 にする。修正役が Bash の失敗と読まない）。最初の
# git diff が落ちれば（base の版が無いなど）そこで 1 で終える（差分の無いファイルを審査役に渡さない）
G1_PATCH = ('p={patch}; top="$(git rev-parse --show-toplevel)"; '
            'git -C "$top" -c core.quotePath=false diff {base} > "$p" || exit 1; '
            'git -C "$top" -c core.quotePath=false ls-files --others --exclude-standard | while IFS= read -r f; do '
            'git -C "$top" -c core.quotePath=false diff --no-index /dev/null "$f" >> "$p"; done; echo "$p"')
G1_STEPS = (
    "下の項目の順に、Agent の道具で実装役の下請けを 1 つ起こし、prompt に実装役のファイルの中身を全部、字を変えずに渡す。"
    "下請けは項目ごとに新しい会話で起きる（前の項目の会話の履歴は持たない）。2 つ目からの項目では、ファイルの中身の後ろに見出し "
    f"`{G1_HANDOFF_HEAD}` の節を足し、済んだ項目ごとに 1 行（項目の番号・実装役の報告に在る変えたファイルと緑にしたテスト）を"
    "書く。前の項目の直しは作業ツリーに在るので、戻したり作り直したりさせない。",
    "実装役の最後のメッセージを受けたら、その項目の差分のコマンドを Bash で走らせ（run ごとの置き場の絶対パスに書く。未追跡の"
    "新しいファイルも全文の差分で入る）、別の Agent で審査役の下請けを起こす。prompt には審査役のファイルの中身を全部と、その後ろに"
    "実装役の最後のメッセージを貼る。差分は base からの全体で、前の項目の直しも入る（審査役のファイルにもそう書いてある）。",
    "審査の返答が `❌` か `Needs fixes` なら、指摘を添えて同じ項目の実装役を起こし直し、もう 1 度審査を起こす。実装役は項目ごとに"
    "3 回まで。3 回目の審査も通らなくても、その項目の直す義務の単位はどの形とも同じく changes に載せる（直す義務の単位はいつも "
    "changes に 1 行）。残った指摘は、その行の root_or_symptom の kind を symptom にして why に書く。受け付けがその単位を拒めば、"
    "受け付けの最後の回はその単位の直しだけを戻して止める（ほかの単位は通る）。単位をまったく直せない（人の答えが無いと直し方が"
    "決まらない）時と、実装役が NEEDS_CONTEXT か BLOCKED を返した時だけ、直さずに食い違いの申し出（conflicts）で返す（下の"
    "読み替えの ASK）。",
    "受け付けの出し直し（指示書の頭が拒否の理由のファイルを名指す）と裁定の後の 2 回目（裁定の文のファイルを名指す）では、"
    "拒否の理由か裁定が名指す項目だけの下請けを起こし直す（ほかの項目の直しは作業ツリーに残っている）。",
    "全部の項目が済んだら、作業ツリーの差分を自分で確かめ（下請けの報告を信じない。読み替えの DELEGATE）、自分は返答の欄の JSON "
    "だけを返す。下請けが Bash で書いたと報告したファイルは、パスと理由を返答の bash_writes に書く（Edit・Write の書き込みは記録に"
    "載る）。",
    "機械の関門は返答の後に線が当てる: 受け入れのテストの赤→緑と既存のテストの凍結は修正の受け付けの束、変更に当たる試験は"
    "受け付け、test_cmd は線の最後のテストの段。下請けの「commit」「人に聞く」は下請けのファイルの末尾の works の決まりに従う。",
)
G1_OVERRIDES = ("下の読み替えの DISPATCH（下請けを起こさない・ほかの役の道具に Agent は無い）と DELEGATE の「役がほかの"
                "エージェントに仕事を任せることは無い」は、この修正役には効かない: この節の手順のとおり Agent で"
                "下請けを起こす。下請けがさらに下請けを起こすことは無い（どちらの型も禁じる）。読み替えの頭の行の「その prompt に、"
                "このファイル … を Read せよと書け」も下請けには書かない: 下請けのファイルの末尾の works の決まりが、その代わりに"
                "下請けの読み替えを持つ")
G1_SUB_HEAD = promptsection.Section("## works の決まり（下請け。上の型の文にも、読み替え unattended.md にも勝つ）", source="fn:seat.g1_prompt")
G1_SUB_RULES = (
    "読み替え（unattended.md）を読んでも、ぶつかる所はこの決まりが勝つ。審査役も Bash で git の差分を読んでよい"
    "（読み替えの GIT-RANGE の「審査役は Bash を持たない」はこの下請けに当たらない）。",
    "commit・stash・reset・checkout をしない。HEAD・index・枝を動かさず、差分は作業ツリーに残す（型の「Commit your work」は"
    "読み替える）。",
    "人に聞かない（聞いても答えは来ない）。分からない所は止まらずに、最後のメッセージに NEEDS_CONTEXT か BLOCKED と何が"
    "分からないかを書く。",
    "報告はファイルに書かず、最後のメッセージに書く。",
    "作業ツリーへの書き込みは Edit・Write の道具で（書き込みの記録に載る）。Bash で書いたファイルは、パスと Bash で書いた理由を"
    "最後のメッセージに書く。",
    "一式は回さない（一式と test_cmd は線が回す）。回すのは変えたファイルに当たる試験だけ。",
    "下請けを起こさない。",
)
G1_EXTRA = {   # 節ごとに G1_SUB_RULES の後ろへ足す決まり（審査役だけ）
    "task-review": (
        "差分の主の材料は、修正役が書いた差分のファイル（上の Diff file の絶対パス）。先にそれを読む。"
        "無い・読めない時だけ、上の Base の版で `git diff <Base の版>` を走らせ（作業ツリーと base の差分。works は commit しないので、"
        "commit の範囲には差分が出ない）、`git ls-files --others --exclude-standard` で未追跡の新しいファイルの名を引いて、それぞれを"
        "Read で読む。",
        "差分は base からの全体で、前の項目の直しも入る。審査するのは今の項目の brief に当たる所で、前の項目の直しそのものは"
        "審査しない（今の項目の直しがそれを壊していれば指摘する）。",
    ),
}
G1_QUERY_LEAD = "外のサービスへ問い合わせる時の決まり（works の包みより。この決まりは型の文に勝つ）:"


def carries(node: str) -> bool:
    """役 node に座が載るか"""
    return node in SEATS


def skill_of(seam: dict) -> str:
    """use_as が skill の節の files[0]（skills/<名>/…）の <名>。skill の節でなければ ValueError"""
    files = seam.get("files") or []
    parts = pathlib.PurePosixPath(files[0]).parts if files else ()
    if seam.get("use_as") != "skill" or len(parts) < 3 or parts[0] != "skills":
        raise ValueError(f"スキルの節でない（use_as {seam.get('use_as')!r}・files {files}）")
    return parts[1]


def _bullets(rows) -> str:
    return "\n".join(f"- {r}" for r in rows)


def load_seams() -> dict:
    return json.loads((BORROW_DIR / SEAMS_FILE).read_text(encoding="utf-8"))


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


OUTSIDE = "版のフォルダの外を指す（絶対のパスか ..）"   # 以下 pin_problems まで bin/_lib/spseam.py の写し（試験が同じ行を返すことを縛る）
LINKED = "symlink が在る（たどらない）"
MARKERS = frozenset({".in_use", ".orphaned_at"})   # Claude Code がプラグインのキャッシュの版の置き場に置く印
IGNORED = frozenset({".DS_Store"})


def _bad_path(src: pathlib.Path, rel: str) -> str | None:
    """rel が版のフォルダの外を指す・途中か先が symlink なら理由（OUTSIDE・LINKED）。読んでよければ None"""
    pure = pathlib.PurePosixPath(rel)
    if not rel or pure.is_absolute() or pathlib.PureWindowsPath(rel).is_absolute() or ".." in pure.parts:
        return OUTSIDE
    at = src
    for part in pure.parts:
        at = at / part
        if at.is_symlink():
            return LINKED
    return None


def _scan(src: pathlib.Path, item: dict) -> tuple[dict[str, str], dict[str, str]]:
    """包むファイルの ({相対パス: sha256}, {読まなかったパス: 理由})。symlink はたどらず、外を指すパスは読まない"""
    files, bad = {}, {}
    for name in item["skills"]:
        rel = f"skills/{name}"
        why = _bad_path(src, rel)
        if why:
            bad[rel] = why
            continue
        root = src / rel
        if not root.is_dir():
            continue
        for here, dirs, names in os.walk(root, followlinks=False):
            for n in [*dirs, *names]:
                p = pathlib.Path(here) / n
                r = p.relative_to(src)
                if MARKERS & set(r.parts) or n in IGNORED:
                    continue
                if p.is_symlink():
                    bad[r.as_posix()] = LINKED
                elif n in names and p.is_file():
                    files[r.as_posix()] = _sha(p)
            dirs[:] = [d for d in dirs if not (pathlib.Path(here) / d).is_symlink() and d not in MARKERS]
    for rel in [*item.get("parts", []), *([item["licence_file"]] if item.get("licence_file") else [])]:
        why = _bad_path(src, rel)
        if why:
            bad[rel] = why
        elif (src / rel).is_file():
            files[rel] = _sha(src / rel)
    return dict(sorted(files.items())), bad


def pin_problems(src: pathlib.Path, item: dict) -> list[str]:
    """固定の files と版のフォルダ src の包むファイルの食い違いの行（パスの順）。借りる一覧と部品が固定に無ければ、それも名指す。
    空なら写しは固定と同じ"""
    pin = item.get("pin")
    if not pin:
        return ["borrow.json の superpowers に pin が無い"]
    want = pin.get("files", {})
    have, bad = _scan(src, item)
    for rel in want:
        why = rel not in bad and _bad_path(src, rel)
        if why:
            bad[rel] = why
    unpinned = {rel for rel in [*(f"skills/{s}/SKILL.md" for s in item["skills"]), *item.get("parts", [])] if rel not in want}
    out = []
    for rel in sorted(set(want) | set(have) | set(bad) | unpinned):
        if rel in bad:
            out.append(f"{rel}: {bad[rel]}")
        elif rel in unpinned:
            out.append(f"{rel}: 借りる一覧（borrow.json の skills・parts）が名指すのに、固定（pin.files）にその sha256 が無い"
                       "（bin/_lib/toolset.py vendor で写し直す）")
        elif rel not in have:
            out.append(f"{rel}: 固定に在るのに手元に無い")
        elif rel not in want:
            out.append(f"{rel}: 固定に無いファイルが手元に在る")
        elif want[rel] != have[rel]:
            out.append(f"{rel}: 中身が固定と違う（固定 {want[rel][:12]} / 手元 {have[rel][:12]}）")
    return out


def pinned() -> tuple[dict, pathlib.Path]:
    """借りる物（borrow.json の superpowers）と写しの置き場（superpowers/<pin の版>）。写しが固定と合わなければ ValueError
    （pin_problems を名指す）。支度は書き込みの前にこれを呼ぶ"""
    item = json.loads((BORROW_DIR / "borrow.json").read_text(encoding="utf-8"))[ITEM]
    src = BORROW_DIR / ITEM / str((item.get("pin") or {}).get("version") or "")
    bad = pin_problems(src, item)
    if bad:
        raise ValueError(f"借りた写し {src} が固定（borrow.json の pin）と合わない: {'; '.join(bad)}")
    return item, src


def _prompt_body(text: str) -> str:
    """型の最初の ``` の囲みの中の「  prompt: |」の次の行から囲みの終わりまでを dedent した物。無ければ ValueError"""
    lines = text.split("\n")
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith(FENCE))
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(FENCE))
    except StopIteration:
        raise ValueError("``` の囲みが無い（開きか閉じが欠けている）") from None
    head = [i for i in range(start + 1, end) if lines[i].rstrip() == PROMPT_LINE]
    if not head:
        raise ValueError(f"最初の ``` の囲みに「{PROMPT_LINE.strip()}」の行が無い")
    return textwrap.dedent("\n".join(lines[head[0] + 1:end]) + "\n")


def _stray(text: str, sec: dict) -> list:
    known = {" ".join(t.split()) for t in [*sec.get("placeholders", []), *sec.get("literals", [])]}
    return sorted({" ".join(t.split()) for t in BRACKETED.findall(text)} - known)


def fill(seam_id: str, values: dict[str, str]) -> str:
    """部品の節（use_as が prompt）の型の穴を全部 values で置き換えた本文（bin/_lib/spseam.fill と同じ決まり）。写しが固定と違う・
    値の鍵が穴と違う・置き換えの後に穴でも埋めない語でもない角括弧の語が残れば ValueError"""
    _, src = pinned()
    sec = load_seams().get(seam_id)
    if not sec or sec.get("use_as") != "prompt":
        raise ValueError(f"{seam_id}: 部品の節でない")
    holes = list(sec.get("placeholders", []))
    lack, extra = sorted(set(holes) - set(values)), sorted(set(values) - set(holes))
    if lack or extra:
        raise ValueError(f"{seam_id}: 値の鍵が穴と違う（足りない {lack} / 余る {extra}）")
    body = _prompt_body((src / sec["files"][0]).read_text(encoding="utf-8"))
    pat = re.compile("|".join(re.escape(h) for h in sorted(holes, key=len, reverse=True))) if holes else None
    left = _stray(pat.sub("", body) if pat else body, sec)
    if left:
        raise ValueError(f"{seam_id}: 埋めていない穴 {' '.join(left)} が {sec['files'][0]} の prompt の本文に残る")
    return pat.sub(lambda m: values[m.group(0)], body) if pat else body


def skill_overlay() -> str:
    """借りたスキルを読める役の指示書に足す段: 頭の 1 行と、読み替えの正本の全文（字のまま。写しを持たない）。superpowers の
    using-superpowers は、直の指示がスキルに勝つと定める。元 works/.shared/core/rolekit.py:74"""
    path = BORROW_DIR / OVERLAY_FILE
    return OVERLAY_HEAD.format(path=path) + "\n\n" + path.read_text(encoding="utf-8")


def query_rule() -> str:
    """写しの agents/judge.md から検索語の規律の塊（頭の行 QUERY_RULE_HEAD と、続く 2 字下げの下位の箇条）を字のまま切り出す。
    読めない・頭の行が無ければ ValueError。元 works/.shared/core/adapter.py:1476"""
    try:
        lines = QUERY_RULE_SOURCE.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"検索語の規律の正本 {QUERY_RULE_SOURCE} が読めない（{type(e).__name__}）") from None
    start = next((i for i, ln in enumerate(lines) if ln.startswith(QUERY_RULE_HEAD)), None)
    if start is None:
        raise ValueError(f"検索語の規律の正本 {QUERY_RULE_SOURCE} に頭の行が無い")
    end = start + 1
    while end < len(lines) and lines[end].startswith("  - "):
        end += 1
    return "\n".join(lines[start:end])


def words_table(seam_id: str) -> str:
    """節 seam_id の出口の語の表（型の語・works の語・欄の値の 3 列の Markdown。見出し WORDS_HEAD つき）。works の語が
    VERDICT_WORDS に無ければ ValueError（推して埋めない）"""
    words = load_seams()[seam_id].get("words") or {}
    lack = sorted(w for w in words.values() if w not in VERDICT_WORDS)
    if lack:
        raise ValueError(f"節 {seam_id} の語 {lack} が判定の欄の語の対応（seat.VERDICT_WORDS）に無い")
    rows = [f"| {said} | {w} | `{VERDICT_WORDS[w][0]}.verdict`: `{VERDICT_WORDS[w][1]}` |" for said, w in words.items()]
    notes = [f"| （{case}） | — | {value}（型の語に依らない） |" for case, value in NOTE_ROWS]
    return "\n".join([WORDS_HEAD, "", "| 型の語 | works の語 | 欄の値 |", "| --- | --- | --- |", *rows, *notes])


def section(node: str, values: dict[str, str] | None = None) -> str:
    """役 node の座の文。載らなければ（carries が偽）空。prompt の節は values で型の穴を埋め、values が None なら ValueError。
    写しが固定と違う・穴が埋まらなければ ValueError（名指す）"""
    if not carries(node):
        return ""
    seams = load_seams()
    sid = SEATS[node]
    if sid not in seams:
        raise ValueError(f"座 {node} の節 {sid} が {SEAMS_FILE} に無い")
    sec = seams[sid]
    if sec.get("use_as") == "prompt" and values is None:
        raise ValueError(f"座 {node}（節 {sid}）の型の穴の値が無い")
    pinned()
    if sec.get("use_as") == "skill":
        body = [SKILL_LEAD.format(skill=skill_of(sec)) + WINS_OF.get(node, WINS),
                APPLIES + "\n\n" + _bullets(sec.get("applies") or []),
                NOT_APPLIES + "\n\n" + _bullets(sec.get("not_applies") or [])]
    else:
        body = [WINS_OF.get(node, WINS), PROMPT_HEAD.format(file=sec["files"][0]), fill(sid, values).rstrip("\n"),
                *([words_table(sid)] if sid == VERDICT_SEAM else []),
                *([DIVERGENCE_HINT] if conflict.WORD in (sec.get("words") or {}).values() else [])]
    return "\n\n".join([HEAD, *body, skill_overlay().rstrip("\n")]) + "\n"


def g1_prompt(seam_id: str, values: dict[str, str]) -> str:
    """修正役が起こす下請けに渡すファイルの中身: 部品の節 seam_id の型を values で埋めた本文、下請けへの works の決まり
    （G1_SUB_HEAD・G1_SUB_RULES と G1_EXTRA の節の行）、検索語の規律の塊（query_rule を字のまま）。型の範囲
    `<[BASE_SHA]>..<[HEAD_SHA]>` は `<[BASE_SHA]>` に直す（作業ツリーとの差分。G1_HEAD_SHA）。写しが固定と違う・穴が埋まらない・
    規律の正本が読めなければ ValueError（名指す）"""
    filled = fill(seam_id, values)
    if "[BASE_SHA]" in values and "[HEAD_SHA]" in values:
        filled = filled.replace(f"{values['[BASE_SHA]']}..{values['[HEAD_SHA]']}", values["[BASE_SHA]"])
    rules = _bullets((*G1_SUB_RULES, *G1_EXTRA.get(seam_id, ())))
    return "\n\n".join([filled.rstrip("\n"), G1_SUB_HEAD, rules, G1_QUERY_LEAD + "\n" + query_rule()]) + "\n"


def g1_section(rows: list[dict]) -> str:
    """下請けを回す修正役の指示書の節。rows は項目の順の {item, impl_file, review_file, base, patch}（fixrules.g1_values）。
    G1_HEAD → 手順（G1_STEPS）→ G1_LOOP_NOTE → 項目ごとの実装役と審査役のファイル → 申し出の種類の手引き（DIVERGENCE_HINT）→
    読み替えの上書き（G1_OVERRIDES）→ 読み替え"""
    steps = "\n".join(f"{n}. {t}" for n, t in enumerate(G1_STEPS, 1))
    files = _bullets(_g1_row(r) for r in rows)
    return "\n\n".join([G1_HEAD, steps, G1_LOOP_NOTE, files, DIVERGENCE_HINT, G1_OVERRIDES,
                        skill_overlay().rstrip("\n")]) + "\n"


def g1_diff_cmd(base: str, patch: str) -> str:
    """審査役に渡す差分のファイルを書くコマンド（G1_PATCH）"""
    return G1_PATCH.format(base=base, patch=shlex.quote(patch))


def _g1_row(r: dict) -> str:
    """g1_section の項目の 1 行"""
    return f"項目 {r['item']}: 実装役 {r['impl_file']}・審査役 {r['review_file']}・差分のコマンド `{g1_diff_cmd(r['base'], r['patch'])}`"
