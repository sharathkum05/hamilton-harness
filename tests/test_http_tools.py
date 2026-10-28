import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from pydantic import ValidationError

from hamilton_harness.http_tools import ALLOW_PRIVATE_ENV, ToolCallError, check_public, run_http
from hamilton_harness.pack.schema import HttpCall, ToolSpec

SEEN: list[dict] = []


class Shop(BaseHTTPRequestHandler):
    """A pretend company API."""

    def _answer(self, status, body, content_type="application/json", extra=None):
        payload = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def _route(self, body=None):
        SEEN.append(
            {
                "method": self.command,
                "path": self.path,
                "auth": self.headers.get("Authorization"),
                "body": body,
            }
        )
        if self.path.startswith("/orders/LS-4471"):
            return self._answer(200, {"order_id": "LS-4471", "status": "shipped"})
        if self.path.startswith("/orders/"):
            return self._answer(404, {"detail": "no such order"})
        if self.path == "/refunds":
            return self._answer(400, "amount is over the limit", "text/plain")
        if self.path == "/broken":
            return self._answer(500, "boom", "text/plain")
        if self.path == "/moved":
            return self._answer(302, "", extra={"Location": "http://169.254.169.254/"})
        if self.path == "/text":
            return self._answer(200, "plain words", "text/plain")
        return self._answer(201, {"received": body})

    def do_GET(self):
        self._route()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self._route(json.loads(self.rfile.read(length) or b"{}"))

    def log_message(self, *args):
        pass


@pytest.fixture
def shop(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), Shop)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv(ALLOW_PRIVATE_ENV, "1")
    monkeypatch.setenv("TOOL_SHOP_KEY", "sk-test-123")
    SEEN.clear()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def call(url, method="GET", headers=None):
    return HttpCall(method=method, url=url, headers=headers or {})


def test_a_get_fills_the_path_and_the_query_and_reads_json(shop):
    tool = call(f"{shop}/orders/{{order_id}}", headers={"Authorization": "Bearer ${TOOL_SHOP_KEY}"})
    result = run_http(tool, {"order_id": "LS-4471", "expand": "items"})
    assert result == {"order_id": "LS-4471", "status": "shipped"}
    assert SEEN[0]["path"] == "/orders/LS-4471?expand=items"
    assert SEEN[0]["auth"] == "Bearer sk-test-123"


def test_an_argument_cannot_add_to_the_path(shop):
    with pytest.raises(LookupError):
        run_http(call(f"{shop}/orders/{{order_id}}"), {"order_id": "../admin?x=1"})
    assert SEEN[0]["path"] == "/orders/..%2Fadmin%3Fx%3D1"


def test_a_post_sends_the_arguments_as_json(shop):
    result = run_http(call(f"{shop}/quotes", "POST"), {"product": "Drift Runner", "quantity": 40})
    assert result == {"received": {"product": "Drift Runner", "quantity": 40}}


def test_a_plain_text_answer_is_passed_on(shop):
    assert run_http(call(f"{shop}/text"), {}) == {"response": "plain words"}


def test_a_refusal_is_explained_to_the_rep(shop):
    with pytest.raises(LookupError, match="Nothing was found"):
        run_http(call(f"{shop}/orders/{{order_id}}"), {"order_id": "LS-0000"})
    with pytest.raises(LookupError, match=r"turned that down \(400\). amount is over the limit"):
        run_http(call(f"{shop}/refunds", "POST"), {"amount": 9000})


@pytest.mark.parametrize("path", ["/broken", "/moved"])
def test_a_failing_or_redirecting_system_is_not_followed(shop, path):
    with pytest.raises(ToolCallError):
        run_http(call(f"{shop}{path}"), {})


def test_a_missing_secret_stops_the_call(shop, monkeypatch):
    monkeypatch.delenv("TOOL_SHOP_KEY")
    with pytest.raises(ToolCallError, match="TOOL_SHOP_KEY is not set"):
        run_http(call(f"{shop}/text", headers={"X-Key": "${TOOL_SHOP_KEY}"}), {})
    assert SEEN == []


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/admin",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
    ],
)
def test_private_addresses_are_refused(url, monkeypatch):
    monkeypatch.delenv(ALLOW_PRIVATE_ENV, raising=False)
    with pytest.raises(ToolCallError, match="private address"):
        check_public(url)


def tool_spec(**http):
    return {
        "name": "lookup_order",
        "description": "Look up an order.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
        "http": {"url": "https://shop.example.com/orders/{order_id}", **http},
    }


def test_a_tool_is_either_code_or_a_call():
    assert ToolSpec.model_validate(tool_spec()).http.method == "GET"
    with pytest.raises(ValidationError, match="not both"):
        ToolSpec.model_validate({**tool_spec(), "handler": "handlers:lookup"})
    with pytest.raises(ValidationError, match="either a handler or an http call"):
        ToolSpec.model_validate({k: v for k, v in tool_spec().items() if k != "http"})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"url": "ftp://shop.example.com/x"}, "http:// or https://"),
        ({"url": "https://shop.example.com/{customer}"}, "not one of its inputs"),
        ({"headers": {"Authorization": "Bearer ${ANTHROPIC_API_KEY}"}}, "starting with TOOL_"),
        ({"headers": {"Bad Header": "x"}}, "letters, digits and dashes"),
        ({"headers": {"X-Key": "a\r\nInjected: yes"}}, "one line"),
        ({"method": "DELETE"}, "method"),
    ],
)
def test_a_badly_set_up_call_is_refused(change, message):
    with pytest.raises(ValidationError, match=message):
        ToolSpec.model_validate(tool_spec(**change))


def starter_with_tool(tmp_path, url):
    import yaml

    from hamilton_harness.scaffold import write_starter_pack

    root = tmp_path / "acme"
    write_starter_pack(root, company="Acme Tools", rep="Jo")
    spec = tool_spec()
    spec["http"]["url"] = url
    (root / "tools.yaml").write_text(yaml.safe_dump({"tools": [spec]}), encoding="utf-8")
    return root


def test_the_rep_runs_an_api_tool_like_any_other(shop, tmp_path):
    from hamilton_harness.llm import ScriptedModel
    from hamilton_harness.pack import load_pack
    from hamilton_harness.runtime import Agent

    pack = load_pack(starter_with_tool(tmp_path, f"{shop}/orders/{{order_id}}"))
    model = ScriptedModel(
        [{"tool": "lookup_order", "args": {"order_id": "LS-4471"}}, "It has shipped."]
    )
    agent = Agent(pack, model, retry_wait=0)
    turn = agent.respond(agent.start(), "where is LS-4471")
    assert turn.actions[0].outcome == "ok"
    assert '"status": "shipped"' in turn.actions[0].detail
    assert turn.text == "It has shipped."


def test_an_unreachable_api_tool_tells_the_rep_only_that(tmp_path, monkeypatch):
    from hamilton_harness.pack import load_pack
    from hamilton_harness.tools import ToolRegistry

    monkeypatch.delenv(ALLOW_PRIVATE_ENV, raising=False)
    registry = ToolRegistry(load_pack(starter_with_tool(tmp_path, "http://127.0.0.1:9/{order_id}")))
    outcome = registry.call("lookup_order", {"order_id": "LS-4471"})
    assert not outcome.ok
    # The reason (a private address here) goes to the log, not to the customer.
    assert outcome.content == "That system is not responding right now."
