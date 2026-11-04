"""送り先の決め（docs/design/viewer.md の 8.1。viewer/AGENTS.md の E25 の 2）。送りに使う値（送り先の URL・headers・proxy の env を
使うか）を env から読む唯一の所で、送るか拒むかを決める。標準ライブラリだけで、OpenTelemetry の SDK を import しない。網に出ない。

- decide(endpoint, env, remote) -> Send。拒む時は Refused（訳の 1 行）を投げる
  - 送り先の名指しは 引数 --endpoint → OTEL_EXPORTER_OTLP_TRACES_ENDPOINT → OTEL_EXPORTER_OTLP_ENDPOINT の順に先に在る物。前の 2 つは
    字のまま、土台の env は /v1/traces を足して使う（OpenTelemetry の仕様の「Endpoint URLs for OTLP/HTTP」）。空の値は未設定と同じ
  - 番地の部分は [v6 の番地] か英数字と . - の名に任意の :数字 だけを通し、\\・userinfo（@）・空白・制御文字を持つ URL は remote でも
    拒む（requests は番地を \\ でも切るので、urlsplit の host だけで決めると手元と読んだ字が遠くへ繋がる）。urlsplit が ValueError を
    投げる形の崩れた [...] も拒む。query（? の後）と fragment（# の後）を持つ URL も remote でも拒む（どちらも成功の 1 行・送りの
    失敗・SDK の誤りの文に出るので、鍵は headers で渡す）。どの拒みも訳に URL を出さない
  - 既定の送り先を持たない。手元（localhost と loopback の番地。名前は引かない）でない送り先は remote の時だけ送る
  - headers は env で名指した送り先にだけ付ける（OTEL_EXPORTER_OTLP_TRACES_HEADERS が OTEL_EXPORTER_OTLP_HEADERS に勝つ）。値は
    percent-decode し、解いた名か値に制御文字が在れば（端に在っても）値を出さずに番号で拒む。引数で名指した送り先には付けない（shell に在る別の
    受け口の鍵を、引数の宛先へ出さない）
  - 送りの形の env（OTEL_EXPORTER_OTLP_TRACES_PROTOCOL が OTEL_EXPORTER_OTLP_PROTOCOL に勝つ）が http/protobuf でなければ拒む
  - 手元の送り先は利用者の proxy の env を使わない（proxy に切られる）
- dropped(env): 入口が SDK を読む前に自分の過程の env から外す名（OTEL_ で始まる名の全部）。SDK の OTLP/HTTP の exporter は引数を
  渡しても env の headers・圧縮・証明書などを読むので、送りに要る値は全部 Send に入れ、SDK には env を読ませない
"""
import ipaddress
import re
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
UNSAFE = re.compile(r"[\\\s\x00-\x1f\x7f]")   # URL の全体で見る。バックスラッシュ・空白・制御文字。requests（urllib3）は番地の部分をバックスラッシュでも切る
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
OWS = " \t"   # headers の項の前後に許す空白（W3C Baggage の OWS）
AUTHORITY = re.compile(r"(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(:[0-9]+)?")   # [v6 の番地] か名に任意の :数字（userinfo の @ を通さない）


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
    try:
        parts = urlsplit(url)
    except ValueError:   # 形の崩れた [...]（例 http://[::1]x.example.com/）。訳に URL も誤りの文も出さない
        parts = None
    if parts is None or UNSAFE.search(url) or (parts.netloc and not AUTHORITY.fullmatch(parts.netloc)):
        raise Refused(f"{named} の送り先の番地の部分が形でない（[v6 の番地] か英数字と . - の名に任意の :数字 だけを通す。\\・"
                      "userinfo の @・空白・制御文字は使わない。鍵は URL でなく headers の env で渡す）")
    if "?" in url or "#" in url:
        raise Refused(f"{named} の送り先が query（? の後）か fragment（# の後）を持つ。どちらも送りの 1 行と誤りの文に出るので、鍵は URL"
                      "でなく headers の env（OTEL_EXPORTER_OTLP_TRACES_HEADERS など）で渡す（訳に URL を出さない）")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Refused(f"{named} の送り先は http か https の URL でない（訳に URL を出さない。字に鍵が混じりうる）")
    local = _local(parts.hostname)
    if not local and not remote:
        raise Refused(f"{named} の送り先は手元（localhost と loopback の番地）でない。span は会話と道具の中身（対象のリポジトリの字）を持つ"
                      "ので、送るなら --remote を付ける（訳に URL を出さない）")
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
    名と値の percent の符号を解く（SDK の parse_env_headers と同じ）。形の違う項は値を出さずに拒む（鍵を黙って落とさない）。名と値の
    前後の空白とタブ（W3C Baggage の OWS）は解く前に外し、解いた後の制御文字は端に在っても拒む（strip で削って通さない）"""
    got = _first(env, TRACES_HEADERS, BASE_HEADERS)
    if not got:
        return {}
    out = {}
    for n, item in enumerate(env[got[0]].split(","), 1):   # _first の strip の前の字で見る（端の改行を削らない）
        if not item.strip(OWS):
            continue
        name, eq, value = item.partition("=")
        name, value = unquote(name.strip(OWS)), unquote(value.strip(OWS))
        if CONTROL.search(name) or CONTROL.search(value):
            raise Refused(f"{got[0]} の {n} 番目の項が percent の符号を解いた後に制御文字（改行など）を持つ")
        name, value = name.strip().lower(), value.strip()
        if not eq or not name:
            raise Refused(f"{got[0]} の {n} 番目の項が name=value の形でない")
        out[name] = value
    return out


def _local(host: str) -> bool:
    """字だけで見る。localhost と loopback の番地だけが手元で、ほかの名は名前を引かずに手元でないとする（安全な側に倒す）"""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
