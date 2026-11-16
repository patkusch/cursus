import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from cursus.read import ReadError, ollama


class Fake(BaseHTTPRequestHandler):
    """A stand-in for the model server, on this machine's loopback address."""

    seen = []
    status = 200
    reply = {"message": {"content": "{}"}}

    def do_POST(self):
        Fake.seen.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
        self.send_response(Fake.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(Fake.reply).encode() if Fake.status == 200 else b"model 'nope' not found")

    def log_message(self, *a):
        pass


class Client(unittest.TestCase):
    def setUp(self):
        Fake.seen, Fake.status, Fake.reply = [], 200, {"message": {"content": '{"ok": true}'}}
        self.server = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_it_sends_the_conversation_with_the_layout_it_wants_back_and_returns_the_reply(self):
        messages = [{"role": "user", "content": "read this"}]
        text = ollama("gemma3:12b", self.host)(messages)
        self.assertEqual(text, '{"ok": true}')
        path, body = Fake.seen[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(body["model"], "gemma3:12b")
        self.assertEqual(body["messages"], messages)
        self.assertIs(body["stream"], False)
        self.assertIsInstance(body["format"], dict, "the model is held to the reading's JSON layout")

    def test_settings_are_steady_by_default_and_capped_so_a_runaway_answer_is_cut_off(self):
        ollama("m", self.host)([{"role": "user", "content": "x"}])
        options = Fake.seen[0][1]["options"]
        self.assertEqual(options["temperature"], 0.0)
        self.assertEqual(options["num_predict"], 3000)
        self.assertEqual(options["num_ctx"], 12288)
        self.assertNotIn("seed", options)

    def test_a_seed_and_temperature_are_passed_through_when_given(self):
        ollama("m", self.host, temperature=0.4, seed=7)([{"role": "user", "content": "x"}])
        options = Fake.seen[0][1]["options"]
        self.assertEqual((options["temperature"], options["seed"]), (0.4, 7))

    def test_a_refusal_is_reported_with_the_models_name_and_what_the_server_said(self):
        Fake.status = 404
        with self.assertRaises(ReadError) as cm:
            ollama("nope", self.host)([{"role": "user", "content": "x"}])
        self.assertIn("Ollama refused the request for 'nope'", str(cm.exception))
        self.assertIn("model 'nope' not found", str(cm.exception))

    def test_a_server_that_is_not_running_says_where_it_looked_and_asks_if_it_is_running(self):
        self.server.shutdown()
        self.server.server_close()
        with self.assertRaises(ReadError) as cm:
            ollama("m", self.host, timeout=2)([{"role": "user", "content": "x"}])
        self.assertIn(f"could not reach Ollama at {self.host}", str(cm.exception))
        self.assertIn("Is it running?", str(cm.exception))
        self.server = HTTPServer(("127.0.0.1", 0), Fake)  # so the cleanups have something to close
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


if __name__ == "__main__":
    unittest.main()
