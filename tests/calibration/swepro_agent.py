"""SWE-Bench Pro V2 の Harbor の agent WorksBench（--ak producer=<works-factory|claude>）。命令の形と 1 件の流れは
tests/calibration/swepro.py の頭。harbor を import するのはこのファイルだけで、harbor は pyproject.toml の extra bench に在る。

ホストで動く薄い殻: setup で swepro.py prepare が課題のイメージに焼いた焼き印と bwrap を確かめ（網を使わない）、run で
課題の入力と認証のファイルを上げて起こし役（swepro.py inside）を 1 回 exec し、/app の差分を model.patch に取り、
起こし役の標準出力と予測を <試み>/agent/ に書く。
命令の字は swepro.py が組む。期限を足さない（setup・exec とも上限なし。作業の段の上限は --agent-timeout-multiplier inf で外し、
付け忘れた起動は殻を作る時に断る）。
環境は WorksBenchDocker（-e tests.calibration.swepro_agent:WorksBenchDocker）。他の環境を渡した起動は、殻が setup で exec の
前に断る（訳は swepro.py の頭の「台に要る物」と「プロキシの要る網」）。
"""
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from harbor.agents.base import BaseAgent  # noqa: E402
from harbor.environments.base import BaseEnvironment  # noqa: E402
from harbor.environments.docker.docker import DockerEnvironment  # noqa: E402
from harbor.models.agent.context import AgentContext  # noqa: E402

from bin._lib import auth_launch  # noqa: E402
from tests.calibration import swepro  # noqa: E402

TAIL = 5


class WorksBenchDocker(DockerEnvironment):
    """Harbor の docker の環境。課題の主のコンテナに Claude Code の sandbox の要る緩め（swepro.SANDBOX の compose の重ねと
    seccomp の写し）を渡す。上流のプロキシ（swepro.upstream）が在れば egress の付き添いを swepro.EGRESS の写しで立て、gost の
    設定（swepro.gost_config）を compose の子の環境の swepro.GOST_CONFIG_ENV で渡す。設定はイメージ・harbor run の字・Harbor の
    記録に入らない。ただし付き添いのコンテナが在る間は、設定がその env（docker inspect で見える）と、書き込める層の
    /opt/egress-sidecar/gost.yaml に残る（keep_containers なら試行の後も長く残る）。無ければ付き添いは Harbor 同梱のまま"""

    def __init__(self, *args, **kwargs):
        self._gost_config = swepro.gost_config(os.environ)
        super().__init__(*args, **kwargs)
        if self._gost_config is not None:
            self._DOCKER_COMPOSE_EGRESS_CONTROL_PATH = swepro.EGRESS / "docker-compose-egress-control.yaml"
            self._EGRESS_CONTROL_SIDECAR_CONTEXT_PATH = swepro.EGRESS / "harbor-docker-egress-control-sidecar"

    @classmethod
    def preflight(cls) -> None:
        super().preflight()
        swepro.gost_config(os.environ)

    def _egress_control_sidecar_dockerfile_path(self) -> Path:
        # 基は classmethod でクラス属性を読むので、__init__ で替えたインスタンスの属性を読ませる
        return self._EGRESS_CONTROL_SIDECAR_CONTEXT_PATH / "Dockerfile"

    @property
    def _docker_compose_paths(self) -> list[Path]:
        return [*super()._docker_compose_paths, swepro.SANDBOX / "docker-compose-sandbox.yaml"]

    def _compose_infra_env_vars(self) -> dict[str, str]:
        env_vars = super()._compose_infra_env_vars()
        env_vars[swepro.SECCOMP_ENV] = str(swepro.SANDBOX / "seccomp.json")
        if self._gost_config is not None:
            env_vars[swepro.GOST_CONFIG_ENV] = self._gost_config
        return env_vars


class WorksBench(BaseAgent):
    DEFAULT_SETUP_TIMEOUT_SEC = math.inf

    def __init__(self, *args, producer: str, **kwargs):
        super().__init__(*args, **kwargs)
        # Harbor は倍率を agent に渡さず、trial を同じプロセスで回すので、起動の字そのものを見る
        if not swepro.unbounded(sys.argv):
            raise ValueError("harbor run に --agent-timeout-multiplier inf（または --timeout-multiplier inf）が無い。"
                             f"無いと Harbor が作業の段を {swepro.PRO_SECONDS} 秒×倍率で切る"
                             "（harbor job resume・-c の設定のファイルからの起動も旗が字に無いので断る）")
        self.producer = swepro.chosen(producer)
        version = swepro.host_claude_version(os.environ)
        if not version:
            raise ValueError("ホストの claude --version が読めない（コンテナにはホストと同じ版の Claude Code を入れる）")
        self.claude_version = version

    @staticmethod
    def name() -> str:
        return "works-bench"

    def version(self) -> str:
        return swepro.head_commit()

    async def setup(self, environment: BaseEnvironment) -> None:
        if not isinstance(environment, WorksBenchDocker):
            raise ValueError(f"harbor run に -e {swepro.ENVIRONMENT} を渡す（他の環境は課題のコンテナに Claude Code の sandbox の"
                             "要る緩めを渡さず、上流のプロキシも通さない）")
        for name, command in swepro.setup_commands(self.version(), self.claude_version):
            done = await environment.exec(command, user="root", timeout_sec=None)
            if done.return_code != 0:
                tail = "\n".join((done.stderr or done.stdout or "").strip().splitlines()[-TAIL:])
                raise RuntimeError(f"setup の {name} が終了の値 {done.return_code} で落ちた:\n{tail}")

    def _auth(self) -> tuple[dict, str]:
        """(コンテナへ運ぶ認証の変数, 断った訳)。断らなければ訳は空"""
        user = os.environ
        got, source, why = auth_launch.resolve(user, user.get("HOME", ""), user.get("CLAUDE_CONFIG_DIR", ""))
        refused = swepro.auth_refused(got, why, user)
        if refused:
            return {}, f"{refused}（出どころ: {source}）" if source else refused
        self.logger.info(f"認証は {source} から拾う（値は出さない）")
        return {k: got[k] for k in swepro.ACCEPTED_AUTH if k in got}, ""

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
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        auth, refused = self._auth()
        if refused:
            self._predict(context, swepro.prediction(inputs["instance_id"], self.producer, "",
                                                     {"state": swepro.AUTH_REFUSED, "error": refused}, None, self.version()))
            raise ValueError(refused)
        await self._upload_text(environment, json.dumps(inputs, ensure_ascii=False), f"{swepro.PLACE}/{swepro.TASK}")
        secret = f"{swepro.PLACE}/{swepro.SECRET}"
        await self._upload_text(environment, json.dumps(auth), secret)
        started = time.monotonic()
        code = None
        try:
            done = await environment.exec(swepro.inside_command(self.producer), user="root", timeout_sec=None)
            code = done.return_code
            self._keep_driver_output(done)
        finally:
            seconds = round(time.monotonic() - started, 3)
            await environment.exec(f"rm -f {secret}", user="root", timeout_sec=None)
            self._predict(context, swepro.prediction(inputs["instance_id"], self.producer, await self._patch(environment),
                                                     await self._result(environment), seconds, self.version()))
        if code != 0:
            raise RuntimeError(f"起こし役 swepro.py inside が終了の値 {code} で終わった（予測は {swepro.PREDICTION} に書いた）")

    def _predict(self, context: AgentContext, predicted: dict):
        (self.logs_dir / swepro.PREDICTION).write_text(json.dumps(predicted, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        context.cost_usd = predicted.get("usd")
        context.metadata = {k: predicted.get(k) for k in ("stopped", "failed", "state", "outcome", "pro_limit")}

    def _keep_driver_output(self, done):
        for name, text in ((swepro.INSIDE_STDOUT, done.stdout), (swepro.INSIDE_STDERR, done.stderr)):
            (self.logs_dir / name).write_text(text or "", encoding="utf-8")

    @staticmethod
    async def _download(environment: BaseEnvironment, path: str) -> bytes | None:
        """コンテナのファイルの中身。exec の標準出力で読まない（Harbor の docker の環境は標準エラーを混ぜる）。
        取れなければ None。投げる型は環境ごとに違う（docker は RuntimeError）ので Exception で受ける"""
        with tempfile.TemporaryDirectory(prefix="works-bench-") as tmp:
            target = Path(tmp) / Path(path).name
            try:
                await environment.download_file(path, target)
                return target.read_bytes()
            except Exception:
                return None

    @classmethod
    async def _patch(cls, environment: BaseEnvironment) -> str | None:
        """/app の変更。取れなければ None"""
        captured = await environment.exec(swepro.capture_command(swepro.WORKDIR, swepro.OUT), user="root", timeout_sec=None)
        if captured.return_code != 0:
            return None
        patch = await cls._download(environment, f"{swepro.OUT}/{swepro.PATCH}")
        return None if patch is None else patch.decode("utf-8", errors="replace")

    @classmethod
    async def _result(cls, environment: BaseEnvironment) -> dict | None:
        got = await cls._download(environment, f"{swepro.OUT}/{swepro.RESULT}")
        try:
            return json.loads(got) if got is not None else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
