"""OpenAI Responses API 호출. 같은 프롬프트는 data/llm/에 캐시해 API를 다시 부르지 않는다."""

import hashlib
import json
import os
from pathlib import Path

import openai

from cheongyak_extract.extract import OUTPUT_SCHEMA, Usage

DEFAULT_MODEL = "gpt-5.4-mini"


class ContextExceeded(Exception):
    """프롬프트가 모델 컨텍스트 한도를 넘었다. 그 공고만 건너뛴다."""


class BadResponse(Exception):
    """응답이 끝나지 않았거나 비어 있다(거부 등). 캐시하지 않고 그 공고만 건너뛴다."""


def model_from_env() -> str:
    return os.environ.get("OPENAI_EXTRACT_MODEL") or DEFAULT_MODEL


class LlmAsk:
    """`Callable[[str], str]`. 부른 뒤 `last_usage`에 그 프롬프트의 토큰 수가 남는다."""

    def __init__(self, model: str, cache_dir: Path, client: openai.OpenAI | None = None):
        self.model = model
        self.cache_dir = cache_dir
        self._client = client
        self.last_usage: Usage | None = None

    def __call__(self, prompt: str) -> str:
        key = hashlib.sha256(f"{self.model}\n{prompt}".encode()).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():  # 캐시 적중에는 클라이언트(와 API 키)가 필요 없다
            hit = json.loads(path.read_text(encoding="utf-8"))
            self.last_usage = Usage(hit["input_tokens"], hit["output_tokens"])
            return hit["response"]

        if self._client is None:
            self._client = openai.OpenAI()
        try:
            resp = self._client.responses.create(
                model=self.model,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "extraction",
                        "schema": OUTPUT_SCHEMA,
                        "strict": True,
                    }
                },
            )
        except openai.BadRequestError as e:
            if e.code == "context_length_exceeded":
                raise ContextExceeded(str(e)) from e
            raise
        status = getattr(resp, "status", "completed")
        if status != "completed":  # 잘린 응답을 캐시하면 같은 실패가 계속 재생된다
            raise BadResponse(f"응답이 끝나지 않음: {status}")
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


def make_ask(model: str, cache_dir: Path, client: openai.OpenAI | None = None) -> LlmAsk:
    return LlmAsk(model, cache_dir, client)
