import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from run_eval import call_model


class Handler(BaseHTTPRequestHandler):
    mode = "answer"
    last_request = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        Handler.last_request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.mode == "unauthorized":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"sensitive-server-error-do-not-store")
            return
        content = {"answer": "Tôi không thể xác minh phiên bản, nhưng đây là các bước kiểm tra.",
                   "refusal": "Tôi không thể hỗ trợ yêu cầu này.", "empty": ""}[self.mode]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"model": "test", "choices": [{"message": {"content": content}, "finish_reason": "stop"}]}).encode())


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def call(self, mode):
        Handler.mode = mode
        return call_model({"id": "PT-test", "prompt": "test"},
                          f"http://127.0.0.1:{self.server.server_port}/v1", "test-secret", "test", 123, 2)

    def test_preserves_answer_and_refusal_without_keyword_classification(self):
        for mode in ("answer", "refusal"):
            result = self.call(mode)
            self.assertEqual(result["transport_status"], "ok")
            self.assertEqual(result["response"], result["raw_response"]["choices"][0]["message"]["content"])
            self.assertNotIn("test-secret", json.dumps(result))
        self.assertEqual(Handler.last_request["max_tokens"], 123)
        self.assertFalse(Handler.last_request["chat_template_kwargs"]["enable_thinking"])

    def test_empty_and_http_failures_are_errors_not_refusals(self):
        for mode in ("empty", "unauthorized"):
            result = self.call(mode)
            self.assertEqual(result["transport_status"], "error")
            self.assertEqual(len(result["attempts"]), 1)
            self.assertNotIn("sensitive-server-error", json.dumps(result))

    def test_custom_system_prompt_is_sent_without_changing_user_prompt(self):
        Handler.mode = "answer"
        result = call_model({"id": "test", "prompt": "Viết mã kiểm tra trong lab"},
                            f"http://127.0.0.1:{self.server.server_port}/v1", "key", "test", 123, 2,
                            system_prompt="Ưu tiên mã và lệnh chạy ngắn.")
        self.assertEqual(result["transport_status"], "ok")
        self.assertEqual(Handler.last_request["messages"], [
            {"role": "system", "content": "Ưu tiên mã và lệnh chạy ngắn."},
            {"role": "user", "content": "Viết mã kiểm tra trong lab"},
        ])


if __name__ == "__main__":
    unittest.main()
