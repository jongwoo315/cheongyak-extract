# cheongyak-extract

청약 모집공고문 PDF에서 구조화된 필드를 뽑고, 청약홈 상세 페이지 표 값을 정답으로 필드별 eval 리포트를 낸다.

## 판단 기록

구현은 AI 에이전트가 했다. 티켓마다 무엇을 성공으로 볼지는 착수 전에 내가 먼저 한 줄로 썼고,
PR이 그 기준을 맞췄는지는 내가 판정했다. 2026-10-25부터 쌓았다.

티켓 2개 · jw 기준으로 통과 2 · 반려 0 · 유보 0

기준과 결과가 갈린 티켓은 아직 없다. 전체 기록: [docs/decisions.md](docs/decisions.md)

## 실행

```bash
uv run python -m cheongyak_extract run --n 3                     # 수집 + LLM 추출 + 리포트
uv run python -m cheongyak_extract eval --pbno 2026000518 --out reports/x.md   # 받아 둔 공고만
```

- `run`은 명령 하나로 아래 흐름이 끝까지 돌고, 필드별 리포트 표가 stdout과 `reports/run.md`에 나온다.
  요청은 순서대로 보내고 사이마다 2초 쉰다. 받은 원본은 `data/raw/`에 두며 커밋하지 않는다
- `eval`은 `data/raw/<pbno>/`만 읽는다. 청약홈에 요청하지 않는다. `detail.html`이나 `notice.pdf`가 없는 공고는
  건너뛰고 이유를 리포트에 적는다
- `OPENAI_API_KEY`가 필요하다. 모델은 `OPENAI_EXTRACT_MODEL`(기본 `gpt-5.4-mini`)
- 같은 프롬프트는 `data/llm/`에 캐시한다(커밋하지 않는다). 캐시가 있으면 API를 부르지 않고 키도 필요 없다

## 흐름

```
fetch (목록 → 상세 HTML → 공고문 PDF)  →  data/raw/<pbno>/{detail.html, notice.pdf}
pdf_text (쪽마다 텍스트)                →  list[str]
extract (LLM 한 번 + 코드가 거른다)     →  {field: Extraction(value, evidence, page)}
truth (상세 HTML 표 → 정답 필드)        →  {field: str | None}
compare + report (필드별 지표 표)       →  stdout + 리포트 파일
```

extract는 문서 전체를 `<page n>` 표시와 함께 LLM에 넣고 8개 필드의 값·근거 문장·쪽 번호를 받는다.
근거 문장이 그 쪽 텍스트에 없거나, 값·근거·쪽 중 하나라도 없거나, 쪽 번호가 범위 밖이면 그 칸을 비운다.
리포트의 「근거 확인 못해 비움」 열은 그중 근거 문장이 그 쪽에 없어 비운 칸(정답 있는 칸만)을 센다.
응답 모양이 깨져 비운 칸은 따로 절로 나온다. 설계: [docs/plans/147-1026-design-llm-extract.md](docs/plans/147-1026-design-llm-extract.md)

## 현재 상태

- 추출은 LLM이다. 정답은 청약홈 상세 표 값이고 비교 전에 `normalize()`를 건다
- 설계에 쓴 공고 3건 결과: [reports/extract-design.md](reports/extract-design.md)
- 프롬프트를 고정한 뒤 받은 새 공고 결과: [reports/extract-new.md](reports/extract-new.md) (5건),
  [reports/extract-new2.md](reports/extract-new2.md) (청약홈 목록에 남은 PDF 있는 공고 1건)
- 첫 실행(stub) 결과: [reports/skeleton.md](reports/skeleton.md)
- 이후 티켓: 정규식 baseline 비교(#150), 공고 150건 확대(#151)

## 테스트

```bash
uv run pytest
```

네트워크와 OpenAI API 없이 돈다. 수집 코드는 `httpx.MockTransport`로, PDF는 테스트 안에서 pymupdf로 만든다.
LLM은 가짜 `ask`로 대신하고, 설계에 쓴 공고 3건의 실제 응답은 `tests/fixtures/llm/`에 녹화해 재생한다.
