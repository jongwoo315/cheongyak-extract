import hashlib
from types import SimpleNamespace

import httpx
import openai
import pytest

from cheongyak_extract import llm
from cheongyak_extract.extract import OUTPUT_SCHEMA, Usage


class FakeClient:
    """openai.OpenAI 대신 넣는 가짜. responses.create 호출만 기록한다."""

    def __init__(self, text='{"ok": 1}', usage=(120, 7), status="completed", error=None):
        self.calls: list[dict] = []
        self._reply = (text, usage, status, error)
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        text, (i, o), status, error = self._reply
        if error:
            raise error
        return SimpleNamespace(
            output_text=text,
            status=status,
            usage=SimpleNamespace(input_tokens=i, output_tokens=o),
        )


def bad_request(code: str) -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "http://x"))
    message = "Input tokens exceed the limit: 450000"
    return openai.BadRequestError(message, response=response, body={"code": code})


def test_ask_sends_prompt_with_strict_json_schema(tmp_path):
    client = FakeClient()
    ask = llm.make_ask("m1", tmp_path, client)
    assert ask("프롬프트") == '{"ok": 1}'
    (call,) = client.calls
    assert call["model"] == "m1" and call["input"] == "프롬프트"
    fmt = call["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert fmt["schema"] == OUTPUT_SCHEMA


def test_second_call_with_same_prompt_hits_cache_and_skips_api(tmp_path):
    client = FakeClient()
    ask = llm.make_ask("m1", tmp_path, client)
    first = ask("p")
    second = ask("p")
    assert first == second and len(client.calls) == 1
    key = hashlib.sha256(b"m1\np").hexdigest()
    assert (tmp_path / f"{key}.json").exists()


def test_cache_survives_a_new_ask_and_needs_no_api_key(tmp_path, monkeypatch):
    llm.make_ask("m1", tmp_path, FakeClient())("p")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm.make_ask("m1", tmp_path)("p") == '{"ok": 1}'  # 클라이언트를 만들지 않는다


def test_different_prompt_or_model_calls_api_again(tmp_path):
    client = FakeClient()
    llm.make_ask("m1", tmp_path, client)("p")
    llm.make_ask("m1", tmp_path, client)("q")
    llm.make_ask("m2", tmp_path, client)("p")
    assert len(client.calls) == 3


def test_usage_is_recorded_on_miss_and_on_hit(tmp_path):
    ask = llm.make_ask("m1", tmp_path, FakeClient(usage=(120, 7)))
    assert ask.last_usage is None
    ask("p")
    assert ask.last_usage == Usage(120, 7)
    ask.last_usage = None
    ask("p")  # 캐시 적중에도 처음 잰 토큰 수를 돌려준다
    assert ask.last_usage == Usage(120, 7)


def test_context_length_error_becomes_context_exceeded(tmp_path):
    ask = llm.make_ask("m1", tmp_path, FakeClient(error=bad_request("context_length_exceeded")))
    with pytest.raises(llm.ContextExceeded, match="450000"):
        ask("p")


def test_other_api_errors_propagate(tmp_path):
    ask = llm.make_ask("m1", tmp_path, FakeClient(error=bad_request("invalid_request_error")))
    with pytest.raises(openai.BadRequestError):
        ask("p")


def test_unfinished_response_is_not_cached(tmp_path):
    client = FakeClient(status="incomplete")
    ask = llm.make_ask("m1", tmp_path, client)
    with pytest.raises(llm.BadResponse, match="incomplete"):
        ask("p")
    assert not list(tmp_path.glob("*.json"))


def test_empty_output_text_is_not_cached(tmp_path):
    # 거부(refusal) 응답은 status가 completed인데 output_text가 비어 있다
    client = FakeClient(text="")
    ask = llm.make_ask("m1", tmp_path, client)
    with pytest.raises(llm.BadResponse, match="비어"):
        ask("p")
    assert not list(tmp_path.glob("*"))


def test_model_comes_from_env_with_default(monkeypatch):
    monkeypatch.delenv("OPENAI_EXTRACT_MODEL", raising=False)
    assert llm.model_from_env() == "gpt-5.4-mini"
    monkeypatch.setenv("OPENAI_EXTRACT_MODEL", "gpt-5.5")
    assert llm.model_from_env() == "gpt-5.5"


@pytest.mark.parametrize(
    "broken",
    [
        "{trunc",
        "{}",
        '{"response": 1, "input_tokens": "x"}',
        '{"response": 1, "input_tokens": 1, "output_tokens": 1}',  # response만 문자열이 아니다
        "[]",
    ],
)
def test_broken_cache_file_is_a_miss_and_is_rewritten(tmp_path, broken):
    key = hashlib.sha256(b"m1\np").hexdigest()
    (tmp_path / f"{key}.json").write_text(broken, encoding="utf-8")
    client = FakeClient(usage=(120, 7))
    ask = llm.make_ask("m1", tmp_path, client)
    assert ask("p") == '{"ok": 1}' and len(client.calls) == 1
    assert ask.last_usage == Usage(120, 7)
    assert llm.make_ask("m1", tmp_path)("p") == '{"ok": 1}'  # 다시 쓴 캐시는 읽힌다


def test_unfinished_response_message_carries_the_reason(tmp_path):
    reply = SimpleNamespace(
        output_text="", status="failed", error=SimpleNamespace(code="rate_limit_exceeded")
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: reply))
    with pytest.raises(llm.BadResponse, match="failed.*rate_limit_exceeded"):
        llm.make_ask("m1", tmp_path, client)("p")


class SequenceClient:
    """호출마다 (출력, 입력 토큰)을 차례로 돌려주는 가짜 클라이언트."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        text, tokens = self.replies[self.calls]
        self.calls += 1
        return SimpleNamespace(
            output_text=text,
            status="completed",
            usage=SimpleNamespace(input_tokens=tokens, output_tokens=7),
        )


LONG = "가" * 100_000  # 정상이면 입력 토큰이 수만 개다


def test_response_that_read_almost_none_of_the_prompt_is_retried_and_never_cached(tmp_path):
    # 2026000491: 25만 자 프롬프트인데 입력 토큰 590으로 completed가 왔고 8칸이 전부 null이었다
    client = SequenceClient([("null만", 590), ('{"ok": 1}', 60_000)])
    ask = llm.make_ask("m1", tmp_path, client)
    assert ask(LONG) == '{"ok": 1}' and client.calls == 2
    assert ask.last_usage == Usage(60_000, 7)
    again = llm.make_ask("m1", tmp_path, SequenceClient([]))  # 캐시에는 정상 응답만 있다
    assert again(LONG) == '{"ok": 1}'


def test_cached_response_that_read_almost_none_of_the_prompt_is_not_replayed(tmp_path):
    # 2578542 전에 캐시된 590토큰 응답이 남아 있으면 같은 8칸 null이 계속 재생된다
    key = hashlib.sha256(f"m1\n{LONG}".encode()).hexdigest()
    (tmp_path / f"{key}.json").write_text(
        '{"response": "{}", "input_tokens": 590, "output_tokens": 9}', encoding="utf-8"
    )
    client = SequenceClient([('{"ok": 1}', 60_000)])
    ask = llm.make_ask("m1", tmp_path, client)
    assert ask(LONG) == '{"ok": 1}' and client.calls == 1
    assert ask.last_usage == Usage(60_000, 7)


def test_response_that_keeps_reading_almost_none_of_the_prompt_ends_as_bad_response(tmp_path):
    client = SequenceClient([("x", 590)] * llm.MAX_ATTEMPTS)
    with pytest.raises(llm.BadResponse, match="입력 토큰"):
        llm.make_ask("m1", tmp_path, client)(LONG)
    assert client.calls == llm.MAX_ATTEMPTS and list(tmp_path.glob("*.json")) == []


def test_short_prompt_with_few_tokens_is_normal(tmp_path):
    client = SequenceClient([('{"ok": 1}', 3)])
    assert llm.make_ask("m1", tmp_path, client)("p") == '{"ok": 1}' and client.calls == 1


def test_ask_sends_the_schema_it_was_made_with(tmp_path):
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    client = FakeClient()
    llm.make_ask("m1", tmp_path, client, schema)("p")
    assert client.calls[0]["text"]["format"]["schema"] == schema
