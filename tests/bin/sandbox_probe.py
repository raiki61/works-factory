"""役の claude の sandbox が立つかを、本物の Claude Code に確かめさせる部品（test_* でないので unittest の発見に拾われない）。

本物の Claude Code を偽の Anthropic API で起こし、sandbox の Bash と Grep を 1 回ずつ踏ませる。立たない台と立つ台を、起こし方の
写しでなく本物の Claude Code の振る舞いで見分けるので、Claude Code の版が変わっても確かめの側を書き直さない。
標準ライブラリだけで動く（課題のコンテナの python3.12 は PyYAML を持たない）。環境は呼び手が引数で渡し、os.environ は読まない。
期限を持たない。claude が偽の API で待ち続けると、この部品も終わらない。

probe の終わりの値は 0（通った）と下の 4 つ。Python の捕まえない例外の 1 と argparse の誤りの 2 とは重ならない。
"""
import http.server
import json
import os
import pathlib
import shlex
import subprocess
import threading
from typing import NamedTuple

START_FAILED = 3   # 偽の API に要求が 1 度も届かなかった（claude の欠け・設定の読みの落ち・起動の時に sandbox を立てられず終わった）
BASH_FAILED = 4    # 要求は届いたが、sandbox の Bash が印を返さなかった
GREP_EMPTY = 5     # Bash は通ったが、Grep が印のファイルを 0 件と返した
UNCONFINED = 6     # Bash は通ったが、拒まれるはずの書き込みが通った（sandbox が閉じ込めていない）

# docker を回す kernel の、利用者の名前空間の制限（1 なら sandbox が立たない）。無い kernel もある
USERNS_LIMIT = "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
GATE = "works-factory-test-gate"   # 確かめに使う役の sandbox を持つ工程
ROLE_NODE = "ci"
MARK = "sandbox-probe-mark"
WROTE, BLOCKED = "WROTE", "BLOCKED"
MODEL = "claude-haiku-4-5-20251001"
PROXY_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")


class Talk(NamedTuple):
    """converse の結果。error は claude を起こせなかった時の例外の文（空なら起こせた）。results は偽の API が受けた tool_result"""
    error: str
    returncode: int | None
    stdout: str
    stderr: str
    results: list
    requests: int


def userns_limit() -> str | None:
    """USERNS_LIMIT の値。読めなければ None（この kernel に無い）"""
    try:
        return pathlib.Path(USERNS_LIMIT).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def fake_api(calls: list, results: list) -> http.server.ThreadingHTTPServer:
    """calls（(tool の名, input) の並び）を、messages の要求ごとに 1 つずつ tool_use で返し、受けた tool_result を results に
    足す偽の Anthropic API。calls を使い切れば文で終える。立てた server の requests に、届いた messages の要求を 1 つずつ足す"""
    lock = threading.Lock()
    issued = [0]

    def sse(w, event, data):
        w.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode())

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
            if not self.path.startswith("/v1/messages") or "count_tokens" in self.path:
                return self.reply_json({"input_tokens": 1})
            last = (body.get("messages") or [{}])[-1].get("content")
            got = [c for c in last if isinstance(c, dict) and c.get("type") == "tool_result"] if isinstance(last, list) else []
            tools = [t.get("name") for t in body.get("tools", [])]
            with lock:
                server.requests.append(self.path)
                results.extend(got)
                first = not issued[0] and body.get("stream") and calls and calls[0][0] in tools
                use = calls[issued[0]] if (got or first) and issued[0] < len(calls) else None
                if use is not None:
                    issued[0] += 1
            if use is not None:
                blocks = [{"type": "tool_use", "id": f"toolu_{issued[0]:02d}", "name": use[0], "input": use[1]}]
                stop = "tool_use"
            else:
                blocks, stop = [{"type": "text", "text": "done" if got else "ok"}], "end_turn"
            message = {"id": "msg_x", "type": "message", "role": "assistant", "model": body.get("model"),
                       "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}
            if not body.get("stream"):
                return self.reply_json({**message, "content": blocks, "stop_reason": stop})
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("connection", "close")
            self.end_headers()
            w = self.wfile
            sse(w, "message_start", {"type": "message_start", "message": {**message, "content": [], "stop_reason": None}})
            for i, block in enumerate(blocks):
                if block["type"] == "text":
                    sse(w, "content_block_start", {"type": "content_block_start", "index": i,
                                                   "content_block": {"type": "text", "text": ""}})
                    delta = {"type": "text_delta", "text": block["text"]}
                else:
                    sse(w, "content_block_start", {"type": "content_block_start", "index": i,
                                                   "content_block": {**block, "input": {}}})
                    delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
                sse(w, "content_block_delta", {"type": "content_block_delta", "index": i, "delta": delta})
                sse(w, "content_block_stop", {"type": "content_block_stop", "index": i})
            sse(w, "message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                     "usage": {"output_tokens": 1}})
            sse(w, "message_stop", {"type": "message_stop"})
            w.flush()
            self.close_connection = True

        def reply_json(self, data):
            raw = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.send_response(404)
            self.send_header("content-length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.requests = []
    return server


def converse(claude_argv: list, settings: dict, tools: tuple, calls: list, cwd, env: dict) -> Talk:
    """claude_argv で本物の claude を、偽の API に向けて起こし、calls の tool_use を踏ませる。env の上に ANTHROPIC_API_KEY=dummy・
    ANTHROPIC_BASE_URL・NO_PROXY=* を置き、プロキシの名を外す（網に出ない）。標準入力は閉じ、期限は持たない。
    claude を起こせなかった時（OSError。欠け・権限）は要求が届かなかった扱いで、例外の文（OS が名指す起こせなかったパス）を error に返す"""
    results = []
    server = fake_api(calls, results)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        child = {k: v for k, v in env.items() if k not in PROXY_NAMES}
        child.update(ANTHROPIC_API_KEY="dummy", ANTHROPIC_BASE_URL=f"http://127.0.0.1:{server.server_address[1]}", NO_PROXY="*")
        argv = [*claude_argv, "-p", "hi", "--model", MODEL, "--settings", json.dumps(settings), "--allowedTools", ",".join(tools),
                "--permission-mode", "dontAsk"]
        try:
            done = subprocess.run(argv, cwd=cwd, env=child, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  encoding="utf-8")
        except OSError as e:
            return Talk(str(e), None, "", "", results, len(server.requests))
        return Talk("", done.returncode, done.stdout, done.stderr, results, len(server.requests))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def role_sandbox() -> dict:
    """確かめに使う役の sandbox の設定（works-factory-test-gate の ci の節）。工程の YAML を読む助け stepnames は PyYAML を
    要るので、役の設定を引く時だけ import する（コンテナの中では呼ばない。設定は呼び手がコマンドの引数で渡す）"""
    from tests.bin import stepnames
    return next(n for n in stepnames.walk(stepnames.nodes(GATE)) if n["id"] == ROLE_NODE)["sandbox"]


def text_of(block: dict) -> str:
    """tool_result の中身の文（content は文字列か text の塊の並び）"""
    content = block.get("content")
    if isinstance(content, str):
        return content
    return "".join(c.get("text", "") for c in content or [] if isinstance(c, dict))


def _last(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _clues(*texts: str) -> list[str]:
    return [line for line in map(_last, texts) if line][:2]


def probe(claude: str, settings: dict, place, env: dict) -> tuple[int, list[str]]:
    """(終わりの値, 要の行 2 つまで)。place の下に HOME にする場所と作業の場所を作り、作業の場所に印のファイルを置く。
    settings は役の sandbox の設定で、filesystem.denyWrite の最初の置き場（~ は作った HOME で解く）を、Bash の書き込みの試しの
    先にする（sandbox が閉じ込めていれば BLOCKED）。要の行は、claude を起こせなかった時はその例外の文、ほかは Bash の tool_result
    の最後の行と claude の標準エラーの最後の行"""
    deny = ((settings.get("filesystem") or {}).get("denyWrite") or [None])[0]
    if not deny:
        raise ValueError("settings の filesystem.denyWrite に置き場が無い（書き込みを拒む置き場が無いと閉じ込めを確かめられない）")
    place = pathlib.Path(place)
    home, work = place / "home", place / "work"
    work.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    (work / f"{MARK}.txt").write_text(f"{MARK}\n", encoding="utf-8")
    denied = pathlib.Path(os.path.realpath(str(home) + deny[1:] if deny.startswith("~") else deny))
    denied.mkdir(parents=True, exist_ok=True)
    command = (f"echo {MARK}; if (echo x > {shlex.quote(str(denied / 'probe-write'))}) 2>/dev/null; "
               f"then echo {WROTE}; else echo {BLOCKED}; fi")
    talk = converse([claude], {"sandbox": settings}, ("Bash", "Grep"),
                    [("Bash", {"command": command, "description": "probe"}),
                     ("Grep", {"pattern": MARK, "path": str(work), "output_mode": "files_with_matches"})],
                    work, {**env, "HOME": str(home)})
    if talk.error:
        return START_FAILED, [talk.error]
    if not talk.requests:
        return START_FAILED, _clues(talk.stderr)
    bash = text_of(talk.results[0]) if talk.results else ""
    said = bash.splitlines()
    if WROTE in said:
        return UNCONFINED, _clues(bash, talk.stderr)
    if MARK not in said or BLOCKED not in said:
        return BASH_FAILED, _clues(bash, talk.stderr)
    grep = text_of(talk.results[1]) if len(talk.results) > 1 else ""
    if f"{MARK}.txt" not in grep:
        return GREP_EMPTY, _clues(bash, talk.stderr)
    return 0, []
