"""OpenAI Responses API 호출. 같은 프롬프트는 data/llm/에 캐시해 API를 다시 부르지 않는다."""

import hashlib
import json
import os
from pathlib import Path

import openai

from cheongyak_extract.extract import OUTPUT_SCHEMA, Usage

DEFAULT_MODEL = "gpt-5.4-mini"
# API가 입력을 거의 읽지 않고 completed를 돌려주는 일이 있다(25만 자 프롬프트에 입력 토큰 590,
# 8필드 전부 null). 토큰 하나에 글자가 20자를 넘으면 비정상이다(한국어는 1~2자).
# 그 응답은 캐시하지 않고 다시 부른다.
MAX_CHARS_PER_TOKEN = 20
MAX_ATTEMPTS = 3


class ContextExceeded(Exception):
    """프롬프트가 모델 컨텍스트 한도를 넘었다. 그 공고만 건너뛴다."""


class BadResponse(Exception):
    """응답이 끝나지 않았거나 비어 있다(거부 등). 캐시하지 않고 그 공고만 건너뛴다."""


def model_from_env() -> str:
    return os.environ.get("OPENAI_EXTRACT_MODEL") or DEFAULT_MODEL


class LlmAsk:
    """`Callable[[str], str]`. 부른 뒤 `last_usage`에 그 프롬프트의 토큰 수가 남는다."""

    def __init__(
        self,
        model: str,
        cache_dir: Path,
        client: openai.OpenAI | None = None,
        schema: dict = OUTPUT_SCHEMA,
    ):
        self.model = model
        self.cache_dir = cache_dir
        self._client = client
        self.schema = schema
        self.last_usage: Usage | None = None

    def __call__(self, prompt: str) -> str:
        key = hashlib.sha256(f"{self.model}\n{prompt}".encode()).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():  # 캐시 적중에는 클라이언트(와 API 키)가 필요 없다
            try:
                hit = json.loads(path.read_text(encoding="utf-8"))
                usage = Usage(hit["input_tokens"], hit["output_tokens"])
                response = hit["response"]
                if not isinstance(response, str):
                    raise TypeError("response가 문자열이 아님")
                if usage.input_tokens * MAX_CHARS_PER_TOKEN < len(prompt):
                    # 입력을 읽지 않은 응답(2578542 전에 캐시된 것)은 재생하지 않는다
                    raise ValueError("입력 토큰이 프롬프트 길이에 비해 너무 적음")
            except (ValueError, KeyError, TypeError):  # 깨진 캐시는 미스로 보고 다시 부른다
                pass
            else:
                self.last_usage = usage
                return response

        if self._client is None:
            self._client = openai.OpenAI()
        resp = self._call_until_input_is_read(prompt)
        if not (resp.output_text or "").strip():  # 거부(refusal)는 completed인데 본문이 비어 있다
            raise BadResponse("응답 본문이 비어 있음")
        self.last_usage = Usage(resp.usage.input_tokens, resp.usage.output_tokens)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")  # 쓰다 끊겨도 잘린 캐시가 남지 않게 한다
        tmp.write_text(
            json.dumps(
                {
                    "response": resp.output_text,
                    "input_tokens": self.last_usage.input_tokens,
                    "output_tokens": self.last_usage.output_tokens,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.replace(tmp, path)
        return resp.output_text

    def _create(self, prompt: str):
        try:
            return self._client.responses.create(
                model=self.model,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "extraction",
                        "schema": self.schema,
                        "strict": True,
                    }
                },
            )
        except openai.BadRequestError as e:
            if e.code == "context_length_exceeded":
                raise ContextExceeded(str(e)) from e
            raise

    def _call_until_input_is_read(self, prompt: str):
        for _ in range(MAX_ATTEMPTS):
            resp = self._create(prompt)
            status = getattr(resp, "status", "completed")
            if status != "completed":  # 잘린 응답을 캐시하면 같은 실패가 계속 재생된다
                why = getattr(resp, "error", None) or getattr(resp, "incomplete_details", None)
                raise BadResponse(f"응답이 끝나지 않음: {status}" + (f" ({why})" if why else ""))
            if resp.usage.input_tokens * MAX_CHARS_PER_TOKEN >= len(prompt):
                return resp
        raise BadResponse(
            f"입력 토큰이 {resp.usage.input_tokens}개뿐이다(프롬프트 {len(prompt)}자): "
            f"{MAX_ATTEMPTS}번 불렀지만 입력을 읽지 않은 응답이다"
        )


def make_ask(
    model: str, cache_dir: Path, client: openai.OpenAI | None = None, schema: dict = OUTPUT_SCHEMA
) -> LlmAsk:
    return LlmAsk(model, cache_dir, client, schema)
