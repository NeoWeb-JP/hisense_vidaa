"""Isolated authentication probe regressions; no network or Home Assistant."""
import ast
import asyncio
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import sys

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/hisense_vidaa/protocol/auth.py"

class ProbeTests(unittest.TestCase):
    def test_brand_clock_and_rejection(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_probe_tv_auth_methods")
        calls = []
        class Rejected(Exception):
            rc = 135
        class Client:
            def __init__(self, **kwargs):
                calls.append(kwargs)
            async def __aenter__(self):
                raise Rejected()
            async def __aexit__(self, *args):
                pass
        credentials = []
        def generate(**kwargs):
            credentials.append(kwargs)
            return "cid", "user", "secret"
        module = types.ModuleType("aiomqtt")
        module.Client = Client
        module.ProtocolVersion = types.SimpleNamespace(V311=4)
        errors = types.ModuleType("aiomqtt.exceptions")
        errors.MqttConnectError = Rejected
        errors.MqttError = RuntimeError
        import os, time, logging
        ns = dict(Any=object, asyncio=asyncio, os=os, time=time,
                  _LOGGER=logging.getLogger(__name__),
                  build_mqtt_ssl_context=lambda *a: None,
                  generate_initial_credentials=generate,
                  extract_connect_rc=lambda err: err.rc)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), ns)
        class Loop:
            async def run_in_executor(self, executor, fn, *args):
                return fn(*args)
        with patch("asyncio.get_running_loop", return_value=Loop()), patch.dict(sys.modules, {"aiomqtt": module, "aiomqtt.exceptions": errors}):
            result = asyncio.run(ns[node.name]("test", brand=" TPO ", timestamp=123))
            self.assertEqual([c["brand"] for c in credentials], ["tpo"] * 3)
            self.assertEqual([c["timestamp"] for c in credentials], [123] * 3)
            self.assertEqual(len(calls), 4)
            self.assertEqual(result["modern_dynamic"]["diagnostic"], "not_authorized")
            self.assertNotIn("secret", str(result))
            credentials.clear()
            asyncio.run(ns[node.name]("test", timestamp=123))
            self.assertEqual([c["brand"] for c in credentials], ["his"] * 3)

if __name__ == "__main__":
    unittest.main()
