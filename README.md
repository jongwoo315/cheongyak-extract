# cheongyak-extract

청약 모집공고문 PDF에서 구조화된 필드를 뽑고, 청약홈 상세 페이지 표 값을 정답으로 필드별 eval 리포트를 낸다.

## 판단 기록

구현은 AI 에이전트가 했다. 티켓마다 무엇을 성공으로 볼지는 착수 전에 내가 먼저 한 줄로 썼고,
PR이 그 기준을 맞췄는지는 내가 판정했다. 2026-10-25부터 쌓았다.

티켓 3개 · 판정 4건 · jw 기준으로 통과 2 · 반려 2 · 유보 0

자동 기준과 내 판정이 갈린 티켓:

| 티켓 | 착수 전 기준 (jw) | 결과 | 판정 | 이유 |
| --- | --- | --- | --- | --- |
| #147 LLM 추출 | extract()의 fields에 대한 값들을 llm이 제대로 파싱한다. 파싱하지 못하면 비운다. | 프롬프트 고정 뒤 처음 본 공고에서 40칸 중 25칸(62.5%), 48칸 중 27칸(56.3%) 맞음. 자동 기준은 9개 중 8개 통과 | 반려 | 처음 시도한 40개는 62%의 정답률이었고 그다음 48개로 했을 때에는 56%로 llm이 값들을 맞는 필드에 가져오는 비율이 너무 적었음 |
| #147 LLM 추출 (두 번째 시도) | 앞선 pr #3에서 언급된 사실(근거 문장을 PDF에서 찾지 못해 코드가 비운 18칸 중 16칸은 LLM 값이 맞았다, 신탁 사업 4건에서 LLM은 시행사로 위탁자를 골랐다. 청약홈 정답은 수탁자인 신탁사다, 청약홈 목록에 공고가 10건뿐이라, 처음 본 공고로 잴 수 있는 것은 최대 6건이었다)을 바탕으로 이번에는 extract()가 필드마다 값을 정확히 판정한다 | 프롬프트 고정 뒤 처음 본 공고 20건에서 160칸 중 145칸(90.6%) 맞음, 정답과 다른 값을 채운 칸 14(8.75%). 자동 기준은 7개 모두 통과 | 반려 | 추출 성능은 확연히 개선이 됐음(62.5% → 90.6%), 하지만 다른 값으로 채운게 1.25%p 증가, sort=True 부분 좀 더 개선 필요 |

전체 기록: [docs/decisions.md](docs/decisions.md)

## 실행

```bash
export OPENAI_API_KEY=...   # 모델은 gpt-5.4-mini, OPENAI_EXTRACT_MODEL로 바꾼다
uv run python -m cheongyak_extract run --n 3
```

명령 하나로 아래 흐름이 끝까지 돌고, 필드별 리포트 표가 stdout과 `reports/run.md`에 나온다.
요청은 순서대로 보내고 사이마다 2초 쉰다. 받은 원본은 `data/raw/`에, LLM 응답 캐시는 `data/llm/`에 두며
둘 다 커밋하지 않는다. 같은 프롬프트는 캐시에서 읽어 API를 다시 부르지 않는다.

공고를 미리 받아 두려면(청약홈에 요청한다. LLM은 부르지 않는다):

```bash
uv run python -m cheongyak_extract fetch --start-page 2 --n 20      # 목록 2쪽부터 PDF 있는 공고 20건
```

받아 둔 공고만 다시 재려면(청약홈에 요청하지 않는다):

```bash
uv run python -m cheongyak_extract eval --pbno 2026000518 2026000530 --out reports/x.md
uv run python -m cheongyak_extract eval --pbno 2026000518 --text T0 T1 --out reports/x.md
```

`eval --text`는 PDF 텍스트 방식을 고른다. 기본은 T0다.

| 방식 | 쪽 텍스트 |
| --- | --- |
| T0 | `sort=True` 텍스트 |
| T1 | T0 뒤에 그 쪽 `find_tables()` 표를 markdown으로 붙인다 |

둘 이상 주면 같은 공고를 방식마다 따로 추출해 한 리포트에 나란히 쓰고 방식별 입력 토큰 합계를 적는다.

## 흐름

```
fetch (목록 → 상세 HTML → 공고문 PDF)  →  data/raw/<pbno>/{detail.html, notice.pdf}
pdf_text (쪽마다 텍스트, T0·T1)         →  list[str]
extract (LLM 한 번 → 8필드 JSON → 근거 확인)  →  {field: Extraction(value, evidence, page)}
truth (상세 HTML 표 → 정답 필드)        →  {field: str | None}
normalize + report (필드별 지표 표)     →  stdout + reports/*.md
```

## 현재 상태

- 추출은 LLM이 한다. 8필드마다 값·근거 문장·쪽 번호를 받고, 근거 문장도 값도 그 쪽에 없으면 비운다(값을 남기는 조건 C안)
- 세 번째 시도의 측정: [reports/extract-tune-0.md](reports/extract-tune-0.md)(표를 붙인 T1 대 T0),
  [reports/extract-tune.md](reports/extract-tune.md)(프롬프트 수정 기록, 다듬는 공고 29건),
  [reports/extract-new.md](reports/extract-new.md)(고정 뒤 받은 공고 20건)
- 이후 티켓: 정규식 baseline #150, PDF에만 있는 필드 #152, 정답 수동 대조 #149, 150건 확대 #151

## 테스트

```bash
uv run pytest
```

네트워크와 API 없이 돈다. 수집 코드는 `httpx.MockTransport`로, PDF는 테스트 안에서 pymupdf로 만든다.
프롬프트 고정 시점의 LLM 응답은 `tests/fixtures/llm/`에 녹화해 두었고 가짜 LLM으로 재생한다.
프롬프트를 고치면 `tests/fixtures/llm/prompt.sha256`이 어긋나 재녹화를 요구한다.
