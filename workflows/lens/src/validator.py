"""graph が宣言する plugin の中の物（役割 agent の定義 agents/<役>.md など）の探し方（元 lib/graphloops/engine/validator.py の
env_root・_sibling_is・find_plugin_path・agent_def の写し。integration.md の 4.4-J: engine の validator は消え、agent_def は lens の
src へ。使い手は lens の lenses.py だけ）。"""
import glob
import json
import os
import pathlib
import re
import sys

from engine.util import PLUGIN_ROOT, die   # lib/graphloops/engine/util.py（ports が lib/graphloops を読めるようにする）


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


def find_plugin_path(rel, plugin):
    """plugin の中のファイルを順に探す: <PLUGIN>_ROOT → 同じリポジトリに並ぶ plugin → インストール済みキャッシュの最新版。
    **先の候補で見つかれば後の候補は見ない**——キャッシュの曖昧さ（同名 plugin が複数の出所に在る）で落とすのはキャッシュを
    実際に引くときだけ。元の engine の明示のパス（--validator）とディレクトリを探す道は、使い手（agent_def）が渡さないので写さない"""
    env = os.environ.get(env_root(plugin))
    if env and (pathlib.Path(env) / rel).is_file():
        return str((pathlib.Path(env) / rel).resolve())
    if _sibling_is(plugin) and (PLUGIN_ROOT.parent / rel).is_file():
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
            f"（役の定義は同じリポジトリに並べるか {env_root(plugin)} で指す）")
    for h in hits:
        if pathlib.Path(h).is_file():
            return str(pathlib.Path(h).resolve())
    return None


def agent_def(agent_type):
    """役割 agent の定義（<plugin>:<役> の agents/<役>.md）の本文（役の指示。frontmatter を除いた物）を読む。

    None = 定義が見つからない（接頭の無い組み込み agent を含む）。返り {file, body}（元の engine の道具・モデル・effort の欄は、
    使い手の lenses.definition が本文しか読まないので写さない）。
    """
    plugin, _, role = agent_type.rpartition(":")
    if not plugin:
        return None
    f = find_plugin_path(f"agents/{role}.md", plugin)
    if not f:
        return None
    parts = pathlib.Path(f).read_text(encoding="utf-8").split("---")
    body = "---".join(parts[2:]).strip() if len(parts) > 2 else ""
    return {"file": str(f), "body": body}
