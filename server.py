#!/usr/bin/env python3
"""A dependency-free, loopback-only OpenRouter notebook."""

import argparse
import json
import os
import re
import secrets
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

STATIC = Path(__file__).parent / "static"
API = "https://openrouter.ai/api/v1"
MAX_BODY = 128 * 1024
MAX_REPLY = 8 * 1024 * 1024


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward an API key to a redirect target.


def openrouter(path, key=None, payload=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(API + path, data=data, headers=headers)
    try:
        with build_opener(NoRedirects()).open(request, timeout=120) as response:
            raw = response.read(MAX_REPLY + 1)
        if len(raw) > MAX_REPLY:
            raise APIError(502, "OpenRouter returned too much data.")
        result = json.loads(raw)
        if not isinstance(result, dict) or "error" in result:
            raise APIError(502, "OpenRouter could not complete this request.")
        return result
    except HTTPError as error:
        messages = {
            400: "OpenRouter rejected the request. Try another model.",
            401: "OpenRouter rejected the API key. Check your key.",
            402: "Your OpenRouter account needs more credits.",
            403: "OpenRouter denied access to this model or request.",
            404: "This model is unavailable. Refresh the model list.",
            408: "OpenRouter timed out. The request may still have been billed.",
            429: "OpenRouter is rate limiting requests. Wait before running again.",
        }
        raise APIError(error.code if error.code in messages else 502,
                       messages.get(error.code, "OpenRouter is unavailable. Try again later.")) from None
    except (socket.timeout, TimeoutError):
        raise APIError(504, "The request timed out. It may still have been billed; no retry was made.") from None
    except (URLError, OSError):
        raise APIError(502, "Could not reach OpenRouter. Check your connection.") from None
    except (ValueError, UnicodeError):
        raise APIError(502, "OpenRouter returned an unreadable response.") from None


def text_field(body, name, maximum):
    value = body.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise APIError(400, "Invalid " + name.replace("_", " ") + ".")
    return value.strip()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(32)
        self.key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self.origins = {"http://127.0.0.1:" + str(self.server_port),
                        "http://localhost:" + str(self.server_port)}
        self.guard = threading.Lock()
        self.running = threading.Lock()
        self.calls = deque()
        self.models = None
        self.models_at = 0


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log request bodies, keys, or prompts.

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def send(self, status, data, content_type="application/json"):
        raw = json.dumps(data).encode() if content_type == "application/json" else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(raw)

    def authorize(self, api=False):
        host = self.headers.get("Host", "")
        if "http://" + host not in self.server.origins:
            raise APIError(403, "Only localhost requests are allowed.")
        origin = self.headers.get("Origin")
        if origin and origin not in self.server.origins:
            raise APIError(403, "This origin is not allowed.")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise APIError(403, "Cross-site requests are not allowed.")
        if api and not secrets.compare_digest(self.headers.get("X-Session-Token", ""), self.server.token):
            raise APIError(403, "Reload this page to connect to the local server.")

    def do_GET(self):
        try:
            self.authorize(api=self.path.startswith("/api/"))
            if self.path == "/api/config":
                self.send(200, {"has_env_key": bool(self.server.key)})
            elif self.path == "/favicon.ico":
                self.send(204, b"", "image/x-icon")
            elif self.path == "/api/models":
                with self.server.guard:
                    if self.server.models is None or time.monotonic() - self.server.models_at > 300:
                        result = openrouter("/models")
                        rows = result.get("data")
                        if not isinstance(rows, list):
                            raise APIError(502, "OpenRouter returned an invalid model list.")
                        models = []
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            architecture = row.get("architecture") or {}
                            if "text" not in architecture.get("output_modalities", ["text"]):
                                continue
                            if "text" not in architecture.get("input_modalities", ["text"]):
                                continue
                            model_id, name = row.get("id"), row.get("name")
                            if isinstance(model_id, str) and isinstance(name, str):
                                if model_id.endswith(":batch"):
                                    continue  # This UI makes synchronous calls, not batch jobs.
                                created = row.get("created", 0)
                                models.append({"id": model_id, "name": name,
                                               "created": created if isinstance(created, (int, float)) else 0})
                        self.server.models = sorted(models, key=lambda m: m["name"].lower())
                        self.server.models_at = time.monotonic()
                    self.send(200, {"models": self.server.models})
            else:
                files = {"/": ("index.html", "text/html; charset=utf-8"),
                         "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                         "/style.css": ("style.css", "text/css; charset=utf-8")}
                if self.path not in files:
                    raise APIError(404, "Not found.")
                filename, mime = files[self.path]
                raw = (STATIC / filename).read_bytes()
                if filename == "index.html":
                    raw = raw.replace(b"__SESSION_TOKEN__", self.server.token.encode())
                self.send(200, raw, mime)
        except APIError as error:
            self.send(error.status, {"error": error.message})
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass
        except Exception:
            self.send(500, {"error": "The local server could not complete this request."})

    def do_POST(self):
        acquired = False
        try:
            self.authorize(api=True)
            if self.path != "/api/run":
                raise APIError(404, "Not found.")
            if self.headers.get("Content-Type") != "application/json":
                raise APIError(415, "Use a JSON request.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise APIError(400, "Invalid request size.") from None
            if not 0 < length <= MAX_BODY:
                raise APIError(413, "Request is too large or empty.")
            try:
                body = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise APIError(400, "Invalid JSON request.") from None
            if not isinstance(body, dict):
                raise APIError(400, "Invalid request.")
            model = text_field(body, "model", 200)
            if not re.fullmatch(r"~?[A-Za-z0-9_./:+-]+", model):
                raise APIError(400, "Invalid model ID.")
            prompt = text_field(body, "prompt", 20000)
            entered_key = body.get("api_key", "")
            if not isinstance(entered_key, str):
                raise APIError(400, "Invalid API key.")
            key = entered_key or self.server.key
            if not isinstance(key, str) or not re.fullmatch(r"[\x21-\x7e]{1,512}", key):
                raise APIError(400, "Enter a valid OpenRouter API key.")
            acquired = self.server.running.acquire(blocking=False)
            if not acquired:
                raise APIError(429, "A run is already in progress. Wait for it to finish.")
            with self.server.guard:
                now = time.monotonic()
                while self.server.calls and now - self.server.calls[0] >= 60:
                    self.server.calls.popleft()
                if len(self.server.calls) >= 10:
                    raise APIError(429, "Limit: 10 runs per minute. Wait before running again.")
                self.server.calls.append(now)
            result = openrouter("/chat/completions", key, {
                "model": model, "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7, "max_tokens": 2048, "stream": False,
            })
            choices = result.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise APIError(502, "OpenRouter returned no response.")
            choice = choices[0]
            message = choice.get("message") or {}
            content = message.get("content") or message.get("refusal")
            if not isinstance(content, str) or not content.strip():
                raise APIError(502, "The model returned no text. Try another model or a shorter question.")
            returned_model = result.get("model")
            self.send(200, {"response": content,
                            "model": returned_model if isinstance(returned_model, str) else model,
                            "finish_reason": choice.get("finish_reason"),
                            "usage": result.get("usage"), "provider": result.get("provider")})
        except APIError as error:
            self.send(error.status, {"error": error.message})
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass
        except Exception:
            self.send(500, {"error": "The local server could not complete this request."})
        finally:
            if acquired:
                self.server.running.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    server = Server(args.port)
    print("Model Notebook → http://127.0.0.1:" + str(server.server_port), flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
