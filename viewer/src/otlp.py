"""span の木（src/trace.py の build の答え）を OTLP/HTTP の protobuf で送る（docs/design/viewer.md の 8.1）。網に出るのは見る道具の中で
この 1 つだけ。送り先・headers・proxy の扱いは src/sendto.py の答え（Send）だけを使い、自分で決めない。

- send(built, where) -> 送った span の数。受け口が受けなければ Failed を投げる
- OpenTelemetry の SDK と OTLP/HTTP の exporter（pyproject.toml の extra trace）を読む。入口 viewer/runtrace.py は sendto の決めの後、
  自分の過程の env から OTEL_ の名を外してから、この部品を関数の中で import する（SDK に利用者の OTEL_ の名を読ませない）
- 答えの URL と headers を exporter に明示して渡し、圧縮は付けない（受け口の読み戻しを割らない）。手元の送り先には env を読まない
  HTTP の session（requests の trust_env を切った物）を渡し、利用者の proxy を通さない。手元でない送り先は利用者の proxy を使う
- span は SDK の ReadableSpan に記録の時刻と決まった id のまま組む（tracer で作ると id が乱数になる）
"""
from datetime import datetime, timezone

import requests
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import SpanContext, TraceFlags

from viewer.src import runread
from viewer.src.sendto import Send

SERVICE = "works-factory"
SCOPE = InstrumentationScope("works-factory.viewer.runtrace")
BATCH = 256   # 1 回の頼みの span の数（1 欄 20,000 字の span を積んでも頼みが exporter の上限に届かない数）
TIMEOUT = 30.0
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class Failed(Exception):
    """受け口が受けなかった"""


def send(built: dict, where: Send) -> int:
    session = requests.Session()
    session.trust_env = where.proxy
    exporter = OTLPSpanExporter(endpoint=where.url, headers=dict(where.headers), timeout=TIMEOUT,
                                compression=Compression.NoCompression, session=session)
    try:
        spans = _spans(built)
        for n in range(0, len(spans), BATCH):
            if exporter.export(spans[n:n + BATCH]) is not SpanExportResult.SUCCESS:
                raise Failed(f"{where.url} が span を受けなかった（{n + 1} 番目からの {len(spans[n:n + BATCH])} 個）")
        return len(spans)
    finally:
        exporter.shutdown()


def _spans(built: dict) -> list[ReadableSpan]:
    trace_id = int(built["trace_id"], 16)
    resource = Resource({"service.name": SERVICE})   # create は env の OTEL_RESOURCE_ATTRIBUTES などを読むので使わない
    flags = TraceFlags(TraceFlags.SAMPLED)

    def context(span_id: str) -> SpanContext:
        return SpanContext(trace_id, int(span_id, 16), is_remote=False, trace_flags=flags)

    return [ReadableSpan(name=span["name"], context=context(span["id"]),
                         parent=context(span["parent"]) if span["parent"] else None, resource=resource,
                         attributes=span["attributes"], start_time=_ns(span["start"]), end_time=_ns(span["end"]),
                         instrumentation_scope=SCOPE)
            for span in built["spans"]]


def _ns(text: str) -> int:
    """記録の時刻（UTC）を 1970 年からのナノ秒に。float を通さない（ミリ秒の字がそのまま残る）"""
    delta = runread.when(text) - EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000
