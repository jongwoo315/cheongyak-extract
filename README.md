# cheongyak-extract

청약 모집공고문 PDF에서 구조화된 필드를 뽑고, 청약홈 상세 페이지 표 값을 정답으로 필드별 eval 리포트를 낸다.

## 판단 기록

구현은 AI 에이전트가 했다. 티켓마다 무엇을 성공으로 볼지는 착수 전에 내가 먼저 한 줄로 썼고,
PR이 그 기준을 맞췄는지는 내가 판정했다. 2026-10-25부터 쌓았다.

티켓 3개 · jw 기준으로 통과 2 · 반려 1 · 유보 0

자동 기준과 내 판정이 갈린 티켓:

| 티켓 | 착수 전 기준 (jw) | 결과 | 판정 | 이유 |
| --- | --- | --- | --- | --- |
| #147 LLM 추출 | extract()의 fields에 대한 값들을 llm이 제대로 파싱한다. 파싱하지 못하면 비운다. | 프롬프트 고정 뒤 처음 본 공고에서 40칸 중 25칸(62.5%), 48칸 중 27칸(56.3%) 맞음. 자동 기준은 9개 중 8개 통과 | 반려 | 처음 시도한 40개는 62%의 정답률이었고 그다음 48개로 했을 때에는 56%로 llm이 값들을 맞는 필드에 가져오는 비율이 너무 적었음 |

전체 기록: [docs/decisions.md](docs/decisions.md)

## 실행

LLM 호출에는 `OPENAI_API_KEY` 환경변수가 필요하다. 모델은 `gpt-5.4-mini`이고 `OPENAI_EXTRACT_MODEL`로 바꾼다.
같은 프롬프트의 응답은 `data/llm/`에 캐시되어 다시 부르지 않는다(커밋하지 않는다).

```bash
# 목록 2쪽부터 PDF 있는 공고 20건을 data/raw/에 받는다(LLM 안 부름)
uv run python -m cheongyak_extract fetch --start-page 2 --n 20

# 받아 둔 공고만 읽어 LLM 추출 → 필드별 리포트(청약홈 요청 없음)
uv run python -m cheongyak_extract eval --pbno 2026000518 2026000530 --out reports/x.md

# 수집부터 추출·리포트까지 한 번에
uv run python -m cheongyak_extract run --n 3
```

- 요청은 순서대로 보내고 사이마다 2초 쉰다. `fetch`는 403·429가 3번 연속이면 멈추고 그때까지 받은 공고 번호를 출력한다
- 이미 `notice.pdf`가 있는 공고는 건너뛴다. 받은 원본은 `data/raw/`에 두며 커밋하지 않는다
- `eval --no-sort`는 PDF 텍스트를 pymupdf 기본 순서로 뽑는다(`sort=True`와 비교할 때만 쓴다)

## 흐름

```
fetch (목록 → 상세 HTML → 공고문 PDF)  →  data/raw/<pbno>/{detail.html, notice.pdf}
pdf_text (쪽마다 텍스트, sort=True)      →  list[str]
extract (LLM 한 번 + 값을 남기는 조건)   →  {field: Extraction(value, evidence, page)}
truth (상세 HTML 표 → 정답 필드)        →  {field: str | None}
compare + report (필드별 지표 표)       →  stdout + reports/*.md
```

값을 남기는 조건은 같은 LLM 응답에 A·B·C안을 걸어 비교한다. 리포트 본 표는 `extract.DEFAULT_RULE`(C안)를 따른다.

| 안 | 값을 남기는 조건 |
| --- | --- |
| A안 | 근거 문장이 그 쪽에 있다 |
| B안 | A안 + 값이 근거 문장 안에 있다 |
| C안 | 근거 문장이 그 쪽에 있거나, 값이 그 쪽에 있다 |

## 리포트

- [reports/extract-tune-0.md](reports/extract-tune-0.md): `sort=True` 효과(첫 시도 프롬프트, 다듬는 공고 9건)
- [reports/extract-tune.md](reports/extract-tune.md): 프롬프트 수정마다 한 줄, 다듬는 공고 9건
- [reports/extract-new.md](reports/extract-new.md): 프롬프트 고정 뒤 처음 본 공고 20건
- [reports/normalize.md](reports/normalize.md): 정규화 효과(#148), [reports/skeleton.md](reports/skeleton.md): stub 첫 실행(#146)

## 테스트

```bash
uv run pytest
```

네트워크와 API 없이 돈다. 수집 코드는 `httpx.MockTransport`로, LLM은 가짜 응답과 `tests/fixtures/llm/`에 녹화한 응답으로, PDF는 테스트 안에서 pymupdf로 만든다.
