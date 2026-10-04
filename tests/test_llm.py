from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from hamilton_harness.llm import AnthropicModel, ModelError, ScriptedModel, Usage
from hamilton_harness.pack.schema import ModelSettings


def test_scripted_text_step():
    response = ScriptedModel(["Hi Priya!"]).complete(system="s", messages=[], tools=[])
    assert response.text == "Hi Priya!"
    assert response.stop_reason == "end_turn"
    assert response.tool_calls == []


def test_scripted_tool_step():
    model = ScriptedModel([{"tool": "lookup_order", "args": {"order_id": "LS-4471"}}])
    response = model.complete(system="s", messages=[], tools=[])
    assert response.stop_reason == "tool_use"
    assert response.tool_calls[0].name == "lookup_order"
    assert response.content[0]["id"] == response.tool_calls[0].id


def test_scripted_step_can_depend_on_the_history():
    model = ScriptedModel([lambda messages: f"I see {len(messages)} messages"])
    assert model.complete(system="s", messages=[{}, {}], tools=[]).text == "I see 2 messages"


def test_scripted_model_records_a_snapshot_of_each_call():
    model = ScriptedModel(["one", "two"])
    history = [{"role": "user", "content": "hi"}]
    model.complete(system="s", messages=history, tools=[])
    history.append({"role": "assistant", "content": "one"})
    assert len(model.calls[0]["messages"]) == 1


def test_scripted_model_fails_loudly_when_the_script_ends():
    with pytest.raises(ModelError, match="ran out of steps"):
        ScriptedModel([]).complete(system="s", messages=[], tools=[])


def test_usage_adds_up():
    assert Usage(1, 2, 3, 4) + Usage(10, 20, 30, 40) == Usage(11, 22, 33, 44)


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.requests = response, error, []

    def create(self, **request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response


def fake_client(response=None, error=None):
    plain, beta = FakeMessages(response, error), FakeMessages(response, error)
    return SimpleNamespace(messages=plain, beta=SimpleNamespace(messages=beta)), plain, beta


def api_response(*blocks, stop_reason="end_turn"):
    usage = SimpleNamespace(
        input_tokens=120,
        output_tokens=18,
        cache_read_input_tokens=90,
        cache_creation_input_tokens=None,
    )
    return SimpleNamespace(
        content=list(blocks), stop_reason=stop_reason, usage=usage, model="claude-opus-5-5"
    )


def test_anthropic_model_parses_text_and_tool_calls():
    blocks = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text="Let me check. "),
        SimpleNamespace(
            type="tool_use", id="toolu_1", name="lookup_order", input={"order_id": "X"}
        ),
    ]
    client, _, beta = fake_client(api_response(*blocks, stop_reason="tool_use"))
    response = AnthropicModel(client=client).complete(
        system="You are Maya.", messages=[{"role": "user", "content": "hi"}], tools=[{"name": "t"}]
    )
    assert response.text == "Let me check."
    assert response.tool_calls[0].arguments == {"order_id": "X"}
    assert response.content is not None and len(response.content) == 3
    assert response.usage == Usage(120, 18, 90, 0)
    request = beta.requests[0]
    assert request["fallbacks"] == "default"
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert request["output_config"] == {"effort": "low"}
    assert "thinking" not in request and "tool_choice" not in request


def test_models_without_fallback_support_use_the_plain_endpoint():
    client, plain, beta = fake_client(api_response(SimpleNamespace(type="text", text="hi")))
    model = AnthropicModel(ModelSettings(name="claude-haiku-4-5"), client=client)
    model.complete(system="s", messages=[], tools=[])
    assert len(plain.requests) == 1 and beta.requests == []
    assert "tools" not in plain.requests[0]
    assert model.supports_system_turns is False


def status_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (status_error(anthropic.RateLimitError, 429), True),
        (status_error(anthropic.InternalServerError, 500), True),
        (status_error(anthropic.BadRequestError, 400), False),
        (status_error(anthropic.AuthenticationError, 401), False),
    ],
)
def test_api_errors_become_model_errors(error, retryable):
    client, _, _ = fake_client(error=error)
    with pytest.raises(ModelError) as caught:
        AnthropicModel(client=client).complete(system="s", messages=[], tools=[])
    assert caught.value.retryable is retryable


def test_missing_credentials_become_a_model_error():
    client, _, _ = fake_client(error=TypeError("Could not resolve authentication method."))
    with pytest.raises(ModelError, match="no model credentials"):
        AnthropicModel(client=client).complete(system="s", messages=[], tools=[])


def test_unrelated_type_errors_are_not_swallowed():
    client, _, _ = fake_client(error=TypeError("unexpected keyword argument"))
    with pytest.raises(TypeError):
        AnthropicModel(client=client).complete(system="s", messages=[], tools=[])
