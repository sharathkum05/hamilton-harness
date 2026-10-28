"""Run a tool that is a call to a company's web API, set up without code.

A tool in tools.yaml can give an `http` call instead of a Python handler:

    - name: lookup_order
      description: Look up one order by its number.
      http:
        method: GET
        url: https://shop.example.com/api/orders/{order_id}
        headers: {Authorization: "Bearer ${TOOL_SHOP_KEY}"}
      input_schema: {...}

Arguments named in the URL go into the path; the rest go in the query string
for GET and the JSON body for POST. Secrets come from the server's environment
and only from variables starting with TOOL_, so the pack never holds a key and
cannot send out the server's other ones.

The call goes only to public addresses. A tool pointed at the server's own
machine or private network (a cloud metadata address, an internal admin page)
is refused, unless HAMILTON_ALLOW_PRIVATE_TOOL_URLS is set for local testing.
Redirects are not followed, so a public address cannot bounce the call inward.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from hamilton_harness.pack.schema import SECRET, HttpCall

ALLOW_PRIVATE_ENV = "HAMILTON_ALLOW_PRIVATE_TOOL_URLS"
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 200_000
# What the model is shown of a refusal from the company's system.
MAX_REASON_CHARS = 300


class ToolCallError(Exception):
    """The tool is set up wrong or its system cannot be reached. Logged, never shown."""


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_opener = urllib.request.build_opener(_NoRedirects)


def _private_allowed() -> bool:
    return os.environ.get(ALLOW_PRIVATE_ENV, "").strip().lower() in {"1", "true", "yes"}


def check_public(url: str) -> None:
    """Refuse a URL whose host is this machine or a private network."""
    host = urllib.parse.urlsplit(url).hostname
    if not host:
        raise ToolCallError(f"no host in {url}")
    if _private_allowed():
        return
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as error:
        raise ToolCallError(f"cannot find {host}: {error}") from error
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global:
            raise ToolCallError(
                f"{host} is a private address ({ip}). Set {ALLOW_PRIVATE_ENV}=1 to allow it "
                "when testing on your own machine."
            )


def _secret(match: Any) -> str:
    name = match.group(1)
    value = os.environ.get(name)
    if value is None:
        raise ToolCallError(f"the secret {name} is not set on this server")
    return value


def build_request(call: HttpCall, arguments: dict[str, Any]) -> urllib.request.Request:
    """The request a call makes with these arguments."""
    rest = dict(arguments)
    url = call.url
    for field in call.path_fields():
        value = rest.pop(field, "")
        # Quoted with nothing safe, so an argument can never add a path segment or a query.
        url = url.replace(f"{{{field}}}", urllib.parse.quote(str(value), safe=""))
    headers = {name: SECRET.sub(_secret, value) for name, value in call.headers.items()}
    headers.setdefault("Accept", "application/json")
    headers.setdefault("User-Agent", "hamilton-harness")
    data = None
    if call.method == "GET":
        if rest:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}{urllib.parse.urlencode(rest)}"
    else:
        data = json.dumps(rest, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers, method=call.method)


def _body(raw: bytes, content_type: str) -> Any:
    text = raw.decode("utf-8", errors="replace")
    if "json" in content_type:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return {"response": text[:4000]}


def run_http(call: HttpCall, arguments: dict[str, Any]) -> Any:
    """Make the call. Returns the response; raises LookupError when the system says no."""
    request = build_request(call, arguments)
    check_public(request.full_url)
    try:
        with _opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ToolCallError("the response was too large")
            return _body(raw, response.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as error:
        if 400 <= error.code < 500:
            # The company's system said no, for a reason the rep can pass on.
            detail = error.read(MAX_REASON_CHARS * 4).decode("utf-8", errors="replace").strip()
            if error.code == 404:
                raise LookupError("Nothing was found for that.") from error
            reason = f" {detail[:MAX_REASON_CHARS]}" if detail else ""
            raise LookupError(f"The system turned that down ({error.code}).{reason}") from error
        raise ToolCallError(f"the system answered {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ToolCallError(f"could not reach {request.host}: {error}") from error
