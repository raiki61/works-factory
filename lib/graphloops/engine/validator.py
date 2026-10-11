"""graph が宣言する plugin の中の物（記録の検証器 scripts/<loop>-record.py・役割 agent の定義 agents/<役>.md）の探し方と、検証器の呼び方、報告前の仕上げ。"""
import glob
import json
import os
import pathlib
import re
import sys

from .util import PLUGIN_ROOT, die


def env_root(plugin):
    """plugin の置き場を指す環境変数の名前（convergence-loops → CONVERGENCE_LOOPS_ROOT）。"""
    return plugin.upper().replace("-", "_") + "_ROOT"


def _sibling_is(plugin):
    """この plugin と同じリポジトリに並ぶ plugin か（親の plugin.json の name で見る）。"""
    p = PLUGIN_ROOT.parent / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("name") == plugin
    except OSError:
        return False  # 無い＝並んでいない
    except ValueError as e:
        # 壊れている≠無い。黙って False にすると同じリポジトリの検証器を飛ばしてキャッシュの別版を読む
        print(f"警告: {p} が読めない（{e}）——同梱の plugin として扱えず、キャッシュから探す", file=sys.stderr)
        return False


def find_plugin_path(rel, plugin, explicit=None, kind="file"):
    """plugin の中のファイルかディレクトリを順に探す: 明示 → <PLUGIN>_ROOT → 同じリポジトリに並ぶ plugin → インストール済みキャッシュの最新版。
    plugin が無ければ明示だけ。**先の候補で見つかれば後の候補は見ない**——キャッシュの曖昧さ（同名 plugin が複数の
    出所に在る）で落とすのはキャッシュを実際に引くときだけ。以前は明示や同梱が在っても先に die して、案内した
    --validator がその場で効かず、agents/<役>.md の経路には回避策自体が無かった（実測 2026-09-12: 2 出所を置くと
    実在する --validator を渡しても exit 2）。"""
    def ok(p):
        return p.is_file() if kind == "file" else p.is_dir()

    if explicit:
        if ok(pathlib.Path(explicit)):
            return str(pathlib.Path(explicit).resolve())
        # 明示は「これを使え」であって候補の 1 つではない——無ければ黙って別の物に倒さない
        # （実測 2026-09-12: --validator /nonexistent/x.py でも init は exit 0 で同梱の検証器に倒れ、警告も出なかった）
        die(f"明示された {explicit} が無い（{kind}）——パスを確かめよ。明示を外せば同梱・キャッシュから探す")
    if not plugin:
        return None
    env = os.environ.get(env_root(plugin))
    if env and ok(pathlib.Path(env) / rel):
        return str((pathlib.Path(env) / rel).resolve())
    if _sibling_is(plugin) and ok(PLUGIN_ROOT.parent / rel):
        return str((PLUGIN_ROOT.parent / rel).resolve())
    # キャッシュは**実行中のプロファイル 1 つ**だけ見る（CLAUDE_CONFIG_DIR、既定は ~/.claude）。
    # 以前は ~/.claude* を横断していたので、別プロファイル・別マーケットプレイスの同名プラグインが
    # 版の大小だけで選ばれ、動いている出所と無関係なコードが importlib でこのプロセスに読み込まれた。
    cfg = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR") or (pathlib.Path.home() / ".claude"))
    hits = glob.glob(str(cfg / "plugins" / "cache" / "*" / plugin / "*" / rel))
    depth = len(pathlib.Path(rel).parts)

    def _ver(p):
        # 版ディレクトリ名。数値でない部分が混ざっても TypeError で落とさない（比較できる形に揃える）
        name = pathlib.Path(p).parents[depth - 1].name
        return [(0, int(x)) if x.isdigit() else (1, x) for x in re.split(r"[.\-]", name)]

    hits.sort(key=_ver, reverse=True)
    # 出所（マーケットプレイス）が複数に跨がったら選ばない——明示を求める
    origins = {pathlib.Path(h).parents[depth].parent.name for h in hits}
    if len(origins) > 1:
        die(f"{plugin} の {rel} が複数の出所に在る（{sorted(origins)}）——どれを使うか明示しろ"
            f"（検証器は --validator。役の定義は同じリポジトリに並べるか {env_root(plugin)} で指す）")
    for h in hits:
        if ok(pathlib.Path(h)):
            return str(pathlib.Path(h).resolve())
    return None


def agent_def(agent_type):
    """役割 agent の定義（<plugin>:<役> の agents/<役>.md）を読む——道具・モデル・effort と本文（役の指示）。

    None = 定義が見つからない（接頭の無い組み込み agent を含む）。tools の行が無い定義は全部を継承する（[] は道具なし）。
    本文が要るのは、役を別プロセスの CLI で起こすときに system prompt として渡すため（advance.launch_spec。道具ゼロの役も道具つきの役も）。
    """
    plugin, _, role = agent_type.rpartition(":")
    if not plugin:
        return None
    f = find_plugin_path(f"agents/{role}.md", plugin)
    if not f:
        return None
    parts = pathlib.Path(f).read_text(encoding="utf-8").split("---")
    fm = parts[1] if len(parts) > 2 else ""
    body = "---".join(parts[2:]).strip() if len(parts) > 2 else ""

    def field(name):
        m = re.search(rf"^{name}:\s*(.*)$", fm, re.M)
        return m.group(1).strip() if m else None

    tools = field("tools")
    return {
        "file": str(f),
        "tools": ["*"] if tools is None else [t.strip() for t in tools.strip("[] ").split(",") if t.strip()],
        "model": field("model"),
        "effort": field("effort"),
        "body": body,
    }
