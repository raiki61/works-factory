"""script が Archon から受けた入力の字を値に戻す読み（元の pack の共通の部品 boundary の text・value・items と埋め skip_value の後継の
うち、ports に無い部分）。飛ばされた節の出力は字の "null" か空の字で届く。子の run の札の先のファイルは、止めた Archon の命令
workflow artifacts で読む（child_file）。"""
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import ports

SKIPPED = "null"
DECISION = re.compile(r"INPUTS_D[1-9][0-9]*")   # 周 k の決めの入力 d<k>（round-k-decide の出力）。周の数はグラフの with: が持つ
# 止めた Archon の、run の成果物を一覧し 1 つを読む命令（上流 #4653。packages/cli/src/commands/workflow-artifacts.ts）と、その --json の
# 出力の鍵（一覧の置き場・読んだ中身。拒む時は ok: false と error）。本物の Archon での読みと拒みは tests/blocks/chain/test_chain.py の
# ChildFileArchonCase が見る
ARTIFACTS = ("workflow", "artifacts")
FILES_DIR = "artifactsDir"
CONTENT = "content"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")   # 命令の旗に読まれない run の id


def child_file(ptr, env: Mapping[str, str] | None = None, cwd: str | None = None, at: Path | None = None,
               run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> tuple[str, Path]:
    """子の run の札 {type, run_id, path} の先のファイルの (中身の字, 人が見直すパス)。読むのは止めた Archon の workflow artifacts で、
    run の id の解き・置き場の外へ出るパス（.. も symlink も）・無いファイル・フォルダの拒みは Archon が持つ。Archon の頭（埋め
    childsweep の CLI_ENV）は env（既定は os.environ）から読み、Archon は git の木の中でしか動かないので --cwd に cwd（既定は node の
    cwd の run の作業ツリー）を渡す。打つ場所 at（既定は ports.place()）は作業ツリーの外にする（Archon は打った場所の .archon/.env を
    読む。childsweep と同じ訳）。読めなければ ValueError"""
    env = os.environ if env is None else env
    if not isinstance(ptr, dict) or ptr.get("type") != ports.POINTER_TYPE:
        raise ValueError(f"{ports.POINTER_TYPE} のポインタでない: {ptr!r}")
    run_id, rel = ptr.get("run_id"), ptr.get("path")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError(f"子の run の id の形でない: {run_id!r}")
    if not isinstance(rel, str) or not rel or rel.startswith(("-", "/")):
        raise ValueError(f"子の run の置き場の中の相対のパスでない: {rel!r}")
    cli = ports.polyfill("childsweep")
    head = cli.command_head(env)
    if head is None:
        raise ValueError(f"{cli.CLI_ENV} が無いか、文字列の list の JSON でない（入口の殻 bin/works-factory から起こした run でない）")

    def archon(*args: str) -> dict:
        done = run([*head, *ARTIFACTS, *args, "--json", "--cwd", cwd or os.getcwd()], env=dict(env), cwd=at or ports.place(),
                   capture_output=True, text=True, encoding="utf-8")
        got = cli.last_json(done.stdout)
        if not isinstance(got, dict) or got.get("ok") is False:
            why = got.get("error") if isinstance(got, dict) else got
            raise ValueError(f"Archon の {' '.join((*ARTIFACTS, *args))} が読めない（{why}。終了の値 {done.returncode}）")
        return got

    place, got = archon(run_id).get(FILES_DIR), archon(run_id, rel).get(CONTENT)
    if not isinstance(place, str) or not isinstance(got, str):
        raise ValueError(f"Archon の {' '.join(ARTIFACTS)} の出力に {FILES_DIR}・{CONTENT} の字が無い")
    return got, Path(place) / rel


def text(raw) -> str:
    """字の入力。飛ばされた節（null）と無い入力は空の字"""
    return "" if raw is None or raw == SKIPPED else ports.text(raw)


def value(raw):
    """JSON の値。null・空の字・無い入力は None。JSON でなければ字のまま（字の欄 r2_status など）"""
    try:
        return ports.parsed(raw)
    except ValueError:
        return raw


def items(raw) -> list:
    got = value(raw)
    return got if isinstance(got, list) else []


def decisions() -> list:
    """周の決めの入力 d<k> を周の番号の順に値で読む（final-diff と result が読む）。飛ばされた周（null）と dict でない物は外す"""
    names = sorted(filter(DECISION.fullmatch, os.environ), key=lambda name: int(name[len("INPUTS_D"):]))
    return [d for d in (value(os.environ[name]) for name in names) if isinstance(d, dict)]


def work_tree() -> Path:
    """run の作業ツリーの根（script の node は run の作業ツリーで起きる）"""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(top.stdout.strip())


def head() -> str:
    """作業ツリーの今の HEAD。commit の無い木なら空"""
    done = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True, encoding="utf-8")
    return done.stdout.strip() if done.returncode == 0 else ""
