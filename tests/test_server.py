import http.client
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import server


class LocalAPITests(unittest.TestCase):
    def setUp(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
            self.app = server.Server(0)
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join()

    def request(self, method, path, body=None, **headers):
        connection = http.client.HTTPConnection("127.0.0.1", self.app.server_port, timeout=5)
        standard = {"X-Session-Token": self.app.token, "Content-Type": "application/json"}
        standard.update(headers)
        connection.request(method, path, None if body is None else json.dumps(body), standard)
        response = connection.getresponse()
        raw = response.read()
        result = json.loads(raw) if response.getheader("Content-Type") == "application/json" else raw.decode()
        connection.close()
        return response.status, result

    def payload(self, **overrides):
        return dict({"api_key": "fake-key", "model": "test/model", "prompt": "How should voting work?"}, **overrides)

    def test_local_auth_origin_host_and_static_allowlist(self):
        self.assertEqual(self.request("GET", "/api/config", **{"X-Session-Token": ""})[0], 403)
        self.assertEqual(self.request("GET", "/api/config", Origin="https://example.com")[0], 403)
        self.assertEqual(self.request("GET", "/api/config", Host="example.com")[0], 403)
        self.assertEqual(self.request("GET", "/server.py")[0], 404)
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(self.app.token, page)
        self.assertNotIn("__SESSION_TOKEN__", page)

    def test_single_message_and_credential_exclusion(self):
        response = {"model": "test/model-v2", "provider": "Test", "choices": [
            {"message": {"content": "A simulated answer."}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 12}}
        with patch.object(server, "openrouter", return_value=response) as upstream:
            status, result = self.request("POST", "/api/run", self.payload())
        self.assertEqual(status, 200)
        self.assertEqual(result["response"], "A simulated answer.")
        self.assertEqual(result["model"], "test/model-v2")
        args = upstream.call_args.args
        self.assertEqual(args[0:2], ("/chat/completions", "fake-key"))
        self.assertEqual(args[2]["messages"], [{"role": "user", "content": "How should voting work?"}])
        self.assertNotIn("fake-key", json.dumps(result))

    def test_validation_precedes_upstream_calls(self):
        invalid = [self.payload(prompt=" "), self.payload(model="bad\nmodel"),
                   self.payload(prompt="x" * 20001), self.payload(api_key=[]),
                   self.payload(api_key="fake\nkey"), []]
        with patch.object(server, "openrouter") as upstream:
            for body in invalid:
                self.assertEqual(self.request("POST", "/api/run", body)[0], 400)
            upstream.assert_not_called()

    def test_env_key_busy_and_rate_limit(self):
        self.app.key = "fake-env-key"
        response = {"choices": [{"message": {"content": "Answer"}}]}
        with patch.object(server, "openrouter", return_value=response) as upstream:
            self.assertEqual(self.request("POST", "/api/run", self.payload(api_key=""))[0], 200)
            self.assertEqual(upstream.call_args.args[1], "fake-env-key")
            self.app.running.acquire()
            try:
                self.assertEqual(self.request("POST", "/api/run", self.payload())[0], 429)
            finally:
                self.app.running.release()
            for _ in range(9):
                self.assertEqual(self.request("POST", "/api/run", self.payload())[0], 200)
            self.assertEqual(self.request("POST", "/api/run", self.payload())[0], 429)
            self.assertEqual(upstream.call_count, 10)

    def test_model_catalog_cached_and_text_filtered(self):
        catalog = {"data": [{"id": "test/text", "name": "Text"},
                            {"id": "test/text:batch", "name": "Text batch"},
                            {"id": "test/image", "name": "Image", "architecture": {"output_modalities": ["image"]}}]}
        with patch.object(server, "openrouter", return_value=catalog) as upstream:
            self.assertEqual(self.request("GET", "/api/models")[1]["models"], [{"id": "test/text", "name": "Text", "created": 0}])
            self.request("GET", "/api/models")
            upstream.assert_called_once()

    def test_latest_alias_forwarded_without_rewriting(self):
        response = {"model": "openai/gpt-6.1-sol", "choices": [{"message": {"content": "Answer"}}]}
        with patch.object(server, "openrouter", return_value=response) as upstream:
            status, result = self.request("POST", "/api/run", self.payload(model="~openai/gpt-sol-latest"))
            self.assertEqual(status, 200)
            self.assertEqual(upstream.call_args.args[2]["model"], "~openai/gpt-sol-latest")
            self.assertEqual(result["model"], "openai/gpt-6.1-sol")

    def test_empty_text_refusal_and_error_release_run_lock(self):
        with patch.object(server, "openrouter", return_value={"choices": [{"message": {"content": None}}]}):
            self.assertEqual(self.request("POST", "/api/run", self.payload())[0], 502)
        with patch.object(server, "openrouter", return_value={"choices": [{"message": {"refusal": "I cannot answer."}}]}):
            self.assertEqual(self.request("POST", "/api/run", self.payload())[1]["response"], "I cannot answer.")
        self.assertFalse(self.app.running.locked())


class UpstreamErrorTests(unittest.TestCase):
    def test_provider_errors_are_sanitized_and_not_retried(self):
        error = HTTPError("https://openrouter.ai", 401, "sensitive-detail", {}, None)
        with patch.object(server, "build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(server.APIError) as caught:
                server.openrouter("/chat/completions", "fake-key", {})
            self.assertEqual(caught.exception.status, 401)
            self.assertNotIn("sensitive-detail", caught.exception.message)
            opener.return_value.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
