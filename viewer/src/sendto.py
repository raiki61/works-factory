"""送り先の決め（docs/design/viewer.md の 8.1。viewer/AGENTS.md の E25 の 2）。送りに使う値（送り先の URL・headers・proxy の env を
使うか）を env から読む唯一の所で、送るか拒むかを決める。標準ライブラリだけで、OpenTelemetry の SDK を import しない。網に出ない。

- decide(endpoint, env, remote) -> Send。拒む時は Refused（訳の 1 行）を投げる
  - 送り先の名指しは 引数 --endpoint → OTEL_EXPORTER_OTLP_TRACES_ENDPOINT → OTEL_EXPORTER_OTLP_ENDPOINT の順に先に在る物。前の 2 つは
    字のまま、土台の env は /v1/traces を足して使う（OpenTelemetry の仕様の「Endpoint URLs for OTLP/HTTP」）。空の値は未設定と同じ
  - 既定の送り先を持たない。手元（localhost と loopback の番地。名前は引かない）でない送り先は remote の時だけ送る
  - headers は env で名指した送り先にだけ付ける（OTEL_EXPORTER_OTLP_TRACES_HEADERS が OTEL_EXPORTER_OTLP_HEADERS に勝つ）。値は
    percent-decode する。引数で名指した送り先には付けない（shell に在る別の受け口の鍵を、引数の宛先へ出さない）
  - 送りの形の env（OTEL_EXPORTER_OTLP_TRACES_PROTOCOL が OTEL_EXPORTER_OTLP_PROTOCOL に勝つ）が http/protobuf でなければ拒む
  - 手元の送り先は利用者の proxy の env を使わない（proxy に切られる）
- dropped(env): 入口が SDK を読む前に自分の過程の env から外す名（OTEL_ で始まる名の全部）。SDK の OTLP/HTTP の exporter は引数を
  渡しても env の headers・圧縮・証明書などを読むので、送りに要る値は全部 Send に入れ、SDK には env を読ませない
"""
import ipaddress
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import unquote, urlsplit

PREFIX = "OTEL_"
TRACES_ENDPOINT = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
BASE_ENDPOINT = "OTEL_EXPORTER_OTLP_ENDPOINT"
TRACES_HEADERS = "OTEL_EXPORTER_OTLP_TRACES_HEADERS"
BASE_HEADERS = "OTEL_EXPORTER_OTLP_HEADERS"
TRACES_PROTOCOL = "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"
BASE_PROTOCOL = "OTEL_EXPORTER_OTLP_PROTOCOL"
PROTOCOL = "http/protobuf"
SIGNAL_PATH = "v1/traces"


class Refused(Exception):
    """送らずに止まる訳の 1 行"""


@dataclass(frozen=True)
class Send:
    url: str
    local: bool
    headers: dict = field(default_factory=dict)

    @property
    def proxy(self) -> bool:
        """利用者の proxy の env を使うか（手元へは通さない）"""
        return not self.local


def decide(endpoint: str | None, env: Mapping[str, str], remote: bool) -> Send:
    protocol = _first(env, TRACES_PROTOCOL, BASE_PROTOCOL)
    if protocol and protocol[1] != PROTOCOL:
        raise Refused(f"{protocol[0]}={protocol[1]} は送れない（送るのは OTLP の {PROTOCOL} だけ）。名を外すか {PROTOCOL} にする")
    if endpoint:
        url, named, headers = endpoint, "--endpoint", {}
    elif got := _first(env, TRACES_ENDPOINT):
        url, named, headers = got[1], got[0], _headers(env)
    elif got := _first(env, BASE_ENDPOINT):
        base = got[1]
        url, named, headers = base + (SIGNAL_PATH if base.endswith("/") else "/" + SIGNAL_PATH), got[0], _headers(env)
    else:
        raise Refused(f"送り先が無い。--endpoint か env の {TRACES_ENDPOINT}・{BASE_ENDPOINT} で名指す（既定の送り先は持たない。"
                      "例 http://127.0.0.1:6006/v1/traces）")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Refused(f"{named} の送り先 {url} は http か https の URL でない")
    local = _local(parts.hostname)
    if not local and not remote:
        raise Refused(f"送り先 {parts.hostname} は手元でない。span は会話と道具の中身（対象のリポジトリの字）を持つので、送るなら --remote を付ける")
    return Send(url=url, local=local, headers=headers)


def dropped(env: Mapping[str, str]) -> list[str]:
    return [name for name in env if name.startswith(PREFIX)]


def _first(env: Mapping[str, str], *names: str) -> tuple[str, str] | None:
    """names のうち空でない値を持つ最初の物（空の値は未設定。OpenTelemetry の仕様の「Parsing empty value」）"""
    for name in names:
        value = (env.get(name) or "").strip()
        if value:
            return name, value
    return None


def _headers(env: Mapping[str, str]) -> dict:
    """W3C Baggage の形の name=value,...（OpenTelemetry の仕様の「Specifying headers via environment variables」）。名は小文字にし、
    名と値の percent の符号を解く（SDK の parse_env_headers と同じ）。形の違う項は値を出さずに拒む（鍵を黙って落とさない）"""
    got = _first(env, TRACES_HEADERS, BASE_HEADERS)
    if not got:
        return {}
    out = {}
    for n, item in enumerate(got[1].split(","), 1):
        if not item.strip():
            continue
        name, eq, value = item.partition("=")
        name = unquote(name).strip().lower()
        if not eq or not name:
            raise Refused(f"{got[0]} の {n} 番目の項が name=value の形でない")
        out[name] = unquote(value).strip()
    return out


def _local(host: str) -> bool:
    """字だけで見る。localhost と loopback の番地だけが手元で、ほかの名は名前を引かずに手元でないとする（安全な側に倒す）"""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
