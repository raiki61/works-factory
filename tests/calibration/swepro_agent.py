"""SWE-Bench Pro V2 の Harbor の agent WorksBench（--ak producer=<works-factory|claude>）。命令の形と 1 件の流れは
tests/calibration/swepro.py の頭。harbor を import するのはこのファイルだけで、harbor は pyproject.toml の extra bench に在る。

ホストで動く薄い殻: setup で道具と工場の写しを課題のコンテナの /opt/works-bench に載せ、run で課題の入力とトークンのファイルを
上げて起こし役（swepro.py inside）を 1 回 exec し、/app の差分を model.patch に取り、起こし役の標準出力と予測を <試み>/agent/ に書く。
命令の字は swepro.py が組む。期限を足さない（setup・exec とも上限なし。作業の段の上限は運び役の --agent-timeout-multiplier inf）。
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from harbor.agents.base import BaseAgent  # noqa: E402
from harbor.environments.base import BaseEnvironment  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402

from bin._lib import auth_launch, launcher  # noqa: E402
from tests.calibration import run, swepro  # noqa: E402

TAIL = 5


class WorksBench(BaseAgent):
    DEFAULT_SETUP_TIMEOUT_SEC = math.inf

    def __init__(self, *args, producer: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.producer = swepro.chosen(producer)
        version = run._claude_version(launcher.real_claude(os.environ))
        if not version:
            raise ValueError("ホストの claude --version が読めない（コンテナにはホストと同じ版の Claude Code を入れる）")
        self.claude_version = version.split()[0]

    @staticmethod
    def name() -> str:
        return "works-bench"

    def version(self) -> str:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                              encoding="utf-8", check=True).stdout.strip()

    async def setup(self, environment: BaseEnvironment) -> None:
        for name, command in swepro.setup_commands(self.claude_version):
            if name == swepro.REPO_STEP:
                await self._upload_repo(environment)
            done = await environment.exec(command, user="root", timeout_sec=None)
            if done.return_code != 0:
                tail = "\n".join((done.stderr or done.stdout or "").strip().splitlines()[-TAIL:])
                raise RuntimeError(f"setup の {name} が終了の値 {done.return_code} で落ちた:\n{tail}")

    async def _upload_repo(self, environment: BaseEnvironment):
        """HEAD の写し。commit していない変更は入らないので、測る物と来歴の factory_commit は必ず一致する"""
        with tempfile.TemporaryDirectory(prefix="works-bench-") as tmp:
            tar = Path(tmp) / swepro.REPO_TAR
            subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "-o", str(tar), "HEAD"], check=True)
            await environment.upload_file(tar, f"{swepro.PLACE}/{swepro.REPO_TAR}")

    def _token(self) -> str:
        user = os.environ
        got, source, why = auth_launch.resolve(user, user.get("HOME", ""), user.get("CLAUDE_CONFIG_DIR", ""))
        if got is None:
            raise ValueError(f"認証が無い: {why}")
        if set(got) != {swepro.TOKEN_ENV}:
            raise ValueError(f"SWE-Bench Pro の比べは {swepro.TOKEN_ENV} だけで回す（出どころ: {source}）")
        self.logger.info(f"認証は {source} から拾う（値は出さない）")
        return got[swepro.TOKEN_ENV]

    async def _upload_text(self, environment: BaseEnvironment, text: str, target: str):
        """0600 の一時ファイルで上げ、上げたらすぐ消す"""
        fd, path = tempfile.mkstemp(prefix="works-bench-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            await environment.upload_file(path, target)
        finally:
            os.unlink(path)

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        inputs = swepro.task_inputs(instruction, environment.task_env_config.docker_image)
        token = self._token()
        await self._upload_text(environment, json.dumps(inputs, ensure_ascii=False), f"{swepro.PLACE}/{swepro.TASK}")
        secret = f"{swepro.PLACE}/{swepro.SECRET}"
        await self._upload_text(environment, token, secret)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        code = None
        try:
            done = await environment.exec(swepro.inside_command(self.producer), user="root", timeout_sec=None)
            code = done.return_code
            self._keep_driver_output(done)
        finally:
            seconds = round(time.monotonic() - started, 3)
            await environment.exec(f"rm -f {secret}", user="root", timeout_sec=None)
            predicted = swepro.prediction(inputs["instance_id"], self.producer, await self._patch(environment),
                                          await self._result(environment), seconds, self.version())
            (self.logs_dir / swepro.PREDICTION).write_text(json.dumps(predicted, ensure_ascii=False, indent=1) + "\n",
                                                            encoding="utf-8")
            context.cost_usd = predicted.get("usd")
            context.metadata = {k: predicted.get(k) for k in ("stopped", "failed", "state", "outcome", "pro_limit")}
        if code != 0:
            raise RuntimeError(f"起こし役 swepro.py inside が終了の値 {code} で終わった（予測は {swepro.PREDICTION} に書いた）")

    def _keep_driver_output(self, done):
        for name, text in ((swepro.INSIDE_STDOUT, done.stdout), (swepro.INSIDE_STDERR, done.stderr)):
            (self.logs_dir / name).write_text(text or "", encoding="utf-8")

    @staticmethod
    async def _patch(environment: BaseEnvironment) -> str | None:
        """/app の変更。取れなければ None"""
        captured = await environment.exec(swepro.capture_command(swepro.WORKDIR, swepro.OUT), user="root", timeout_sec=None)
        if captured.return_code != 0:
            return None
        patch = await environment.exec(f"cat {swepro.OUT}/{swepro.PATCH}", user="root", timeout_sec=None)
        return (patch.stdout or "") if patch.return_code == 0 else None

    @staticmethod
    async def _result(environment: BaseEnvironment) -> dict | None:
        got = await environment.exec(f"cat {swepro.OUT}/{swepro.RESULT}", user="root", timeout_sec=None)
        try:
            return json.loads(got.stdout or "") if got.return_code == 0 else None
        except json.JSONDecodeError:
            return None
