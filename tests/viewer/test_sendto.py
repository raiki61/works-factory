"""送り先の決め（viewer/src/sendto.py。viewer/AGENTS.md の E25 の 2・docs/design/viewer.md の 8.1）。

- 送り先の無い起動は拒む（既定の送り先を持たない）。空の値の env は未設定と同じ
- 名指しの順: 引数 --endpoint → OTEL_EXPORTER_OTLP_TRACES_ENDPOINT → OTEL_EXPORTER_OTLP_ENDPOINT。答えの URL は前の 2 つでは字のまま、
  土台の env では /v1/traces を足した物（土台が / で終わる時も / を重ねない）
- 手元でない送り先は --remote 無しで拒み、在れば通す。手元は localhost と loopback の番地（v4 と v6）だけで、ほかの名は手元でない
- 手元の送り先の答えは利用者の proxy の env を使わない（env に proxy が在っても）。手元でない送り先は使う
- headers は env で名指した送り先にだけ付く（信号ごとの名が勝つ）。引数 --endpoint の時は env に headers が在っても付かない。
  値の percent の符号を解く
- 送りの形の env が grpc・http/json なら拒み、http/protobuf と空と未設定は通す（信号ごとの名が勝つ）
- 外す名の選びは OTEL_ で始まる名を全部選び、ほかの名を選ばない

試験は env を dict で渡し、過程の env を読まない。
"""
import unittest

from viewer.src import sendto

LOCAL = "http://127.0.0.1:6006/v1/traces"
FAR = "https://collector.example.com/v1/traces"
TRACES = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
BASE = "OTEL_EXPORTER_OTLP_ENDPOINT"


def decide(endpoint=None, env=None, remote=False):
    return sendto.decide(endpoint, env or {}, remote)


class WhereTest(unittest.TestCase):
    def refused(self, *args, **kw) -> str:
        with self.assertRaises(sendto.Refused) as caught:
            decide(*args, **kw)
        return str(caught.exception)

    def test_no_endpoint_is_refused(self):
        self.assertIn("--endpoint", self.refused())

    def test_empty_values_are_unset(self):
        self.assertEqual(decide(env={TRACES: "", BASE: "http://localhost:4318"}).url, "http://localhost:4318/v1/traces")
        self.refused(env={TRACES: "", BASE: ""})

    def test_the_argument_wins_over_the_env_and_the_signal_env_over_the_base(self):
        env = {TRACES: "http://127.0.0.1:1/x", BASE: "http://127.0.0.1:2"}
        self.assertEqual(decide(LOCAL, env).url, LOCAL)
        self.assertEqual(decide(env=env).url, "http://127.0.0.1:1/x")

    def test_only_the_base_env_gets_the_signal_path(self):
        self.assertEqual(decide("http://127.0.0.1:6006").url, "http://127.0.0.1:6006")
        self.assertEqual(decide(env={TRACES: "http://127.0.0.1:6006"}).url, "http://127.0.0.1:6006")
        self.assertEqual(decide(env={BASE: "http://127.0.0.1:6006"}).url, "http://127.0.0.1:6006/v1/traces")
        self.assertEqual(decide(env={BASE: "http://127.0.0.1:6006/"}).url, "http://127.0.0.1:6006/v1/traces")

    def test_a_far_endpoint_needs_remote(self):
        self.assertIn("--remote", self.refused(FAR))
        self.assertIn("--remote", self.refused(env={BASE: "http://10.0.0.5:4318"}))
        self.assertEqual(decide(FAR, remote=True).url, FAR)

    def test_local_is_localhost_and_loopback_only(self):
        for url in ("http://localhost:6006/v1/traces", "http://LOCALHOST:6006", "http://127.0.0.1:6006", "http://127.8.9.1",
                    "http://[::1]:6006/v1/traces"):
            self.assertTrue(decide(url).local, url)
        for url in ("http://phoenix.local:6006", "http://localhost.example.com", "http://192.168.1.2:6006", "http://[::2]:6006",
                    "http://0.0.0.0:6006"):
            self.assertFalse(decide(url, remote=True).local, url)
            self.refused(url)

    def test_a_url_without_a_host_is_refused(self):
        self.refused("127.0.0.1:6006")
        self.refused("ftp://127.0.0.1/v1/traces")

    def test_local_ignores_the_proxy_env_and_far_uses_it(self):
        env = {"HTTP_PROXY": "http://proxy.example.com:8080", "https_proxy": "http://proxy.example.com:8080", "ALL_PROXY": "x"}
        self.assertFalse(decide(LOCAL, env).proxy)
        self.assertTrue(decide(FAR, env, remote=True).proxy)


class HeadersTest(unittest.TestCase):
    def test_headers_come_only_with_an_env_endpoint(self):
        env = {BASE: "http://127.0.0.1:6006", "OTEL_EXPORTER_OTLP_HEADERS": "authorization=key"}
        self.assertEqual(decide(env=env).headers, {"authorization": "key"})
        self.assertEqual(decide(LOCAL, env).headers, {})

    def test_the_signal_headers_win(self):
        env = {TRACES: LOCAL, "OTEL_EXPORTER_OTLP_HEADERS": "a=base", "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "b=signal"}
        self.assertEqual(decide(env=env).headers, {"b": "signal"})
        env["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = ""
        self.assertEqual(decide(env=env).headers, {"a": "base"})

    def test_header_values_are_percent_decoded(self):
        env = {TRACES: LOCAL, "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer%20key, x-team = a%2Cb"}
        self.assertEqual(decide(env=env).headers, {"authorization": "Bearer key", "x-team": "a,b"})

    def test_a_broken_header_is_refused_without_its_value(self):
        env = {TRACES: LOCAL, "OTEL_EXPORTER_OTLP_HEADERS": "a=1,secretvalue"}
        with self.assertRaises(sendto.Refused) as caught:
            decide(env=env)
        self.assertNotIn("secretvalue", str(caught.exception))


class ProtocolTest(unittest.TestCase):
    def test_other_protocols_are_refused(self):
        for name in ("OTEL_EXPORTER_OTLP_PROTOCOL", "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"):
            for protocol in ("grpc", "http/json"):
                with self.assertRaises(sendto.Refused, msg=f"{name}={protocol}"):
                    decide(LOCAL, {name: protocol})

    def test_protobuf_empty_and_unset_pass(self):
        for env in ({}, {"OTEL_EXPORTER_OTLP_PROTOCOL": ""}, {"OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf"},
                    {"OTEL_EXPORTER_OTLP_PROTOCOL": "grpc", "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf"}):
            self.assertEqual(decide(LOCAL, env).url, LOCAL)
        with self.assertRaises(sendto.Refused):
            decide(LOCAL, {"OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf", "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "grpc"})


class DroppedTest(unittest.TestCase):
    def test_every_otel_name_and_nothing_else(self):
        env = {"OTEL_EXPORTER_OTLP_COMPRESSION": "gzip", "OTEL_SERVICE_NAME": "x", "OTEL_": "", "HTTP_PROXY": "p", "MY_OTEL_X": "y",
               "otel_lower": "z"}
        self.assertEqual(sorted(sendto.dropped(env)), ["OTEL_", "OTEL_EXPORTER_OTLP_COMPRESSION", "OTEL_SERVICE_NAME"])


if __name__ == "__main__":
    unittest.main()
