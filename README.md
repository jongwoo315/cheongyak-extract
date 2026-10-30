# cheongyak-extract

청약 모집공고문 PDF에서 구조화된 필드를 뽑고, 청약홈 상세 페이지 표 값을 정답으로 필드별 eval 리포트를 낸다.

## 판단 기록

구현은 AI 에이전트가 했다. 티켓마다 무엇을 성공으로 볼지는 착수 전에 내가 먼저 한 줄로 썼고,
PR이 그 기준을 맞췄는지는 내가 판정했다. 2026-10-25부터 쌓았다.

티켓 5개 · 판정 7건 · jw 기준으로 통과 5 · 반려 2 · 유보 0

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
uv run python -m cheongyak_extract check-raw                         # data/raw/만 읽어 reports/raw.md를 쓴다
```

`fetch`의 `--n`은 이번에 새로 받을 공고 수다. 열리는 `notice.pdf`가 이미 있는 공고는 요청 없이 건너뛰므로
`data/raw/` 전체를 150건으로 채우려면 `150 - (지금 수집된 공고 수)`를 준다. PDF는 `notice.pdf.part`에 받아
pymupdf로 열리는 것을 확인한 뒤 `notice.pdf`로 이름을 바꾼다. 5xx·타임아웃·연결 끊김은 요청마다
두 번까지(5초, 15초 쉰 뒤) 다시 보내고, 403·429는 다시 보내지 않고 3번 연속이면 멈춘다. 다시 보낸 횟수는
`fetch` 출력에 찍힌다.

`check-raw`는 청약홈에 요청하지 않는다. `data/raw/`를 읽어 공고 디렉터리 수, 수집된 공고 수,
열리지 않는 PDF, PDF가 없는 공고를 [reports/raw.md](reports/raw.md)에 쓴다.

**「수집됐다」와 「오류」의 뜻**은 jw 기준(「150건의 공고가 오류없이 수집된다」)이 정하지 않아 Claude가
정했다. 설계: [docs/plans/151-1029-design-fetch-150.md](docs/plans/151-1029-design-fetch-150.md) §「수집됐다」와 「오류」의 뜻.

- 수집된 공고: `detail.html`이 있고 `notice.pdf`가 pymupdf로 열린다(쪽 수 1 이상, 마지막 쪽 텍스트가 읽힌다)
- 오류: 요청이 다시 시도한 뒤에도 실패했다 / 열리지 않는 `notice.pdf`가 있다 / `fetch`가 n건을 못 채우고 멈췄다
- 오류가 아닌 것: 상세에 공고문 링크가 없는 공고, 첨부가 PDF가 아닌 공고. 수집 대상이 아니라 건너뛰고 이유를 센다

받아 둔 공고만 다시 재려면(청약홈에 요청하지 않는다):

```bash
uv run python -m cheongyak_extract eval --pbno 2026000518 2026000530 --out reports/x.md
uv run python -m cheongyak_extract eval --pbno 2026000518 --text T0 T1 --out reports/x.md
```

`eval --text`는 PDF 텍스트 방식을 고른다. 기본은 T0다.

정규식 baseline으로 재려면(OpenAI를 부르지 않고 `OPENAI_API_KEY`도 필요 없다):

```bash
uv run python -m cheongyak_extract eval --extractor regex --pbno 2026000494 2026000448 --out reports/x.md
uv run python -m cheongyak_extract.compare    # reports/regex-vs-llm.md를 다시 만든다(LLM 숫자는 커밋된 리포트에서 읽는다)
```

`--extractor`는 `llm`(기본)이나 `regex`다. 정규식은 필드 8개마다 라벨 뒤의 값을 줍는 단순한 패턴이다
([src/cheongyak_extract/regex_extract.py](src/cheongyak_extract/regex_extract.py)). 공고별 예외는 없다. 시행사·시공사만 상호 줄을 칸으로 나눠 읽는다.

| 방식 | 쪽 텍스트 |
| --- | --- |
| T0 | `sort=True` 텍스트 |
| T1 | T0 뒤에 그 쪽 `find_tables()` 표를 markdown으로 붙인다 |

둘 이상 주면 같은 공고를 방식마다 따로 추출해 한 리포트에 나란히 쓰고 방식별 입력 토큰 합계를 적는다.

청약홈 정답(HTML)을 공고문 PDF 값과 대조하려면(청약홈과 OpenAI에 요청하지 않는다):

```bash
uv run python -m cheongyak_extract check-truth    # labels/pdf-values-20.json·data/raw/·reports/extract-new.md(대조할 공고 목록과 LLM 틀린 칸)를 읽어 reports/truth-check.md를 쓴다
```

`labels/pdf-values-20.json`은 공고 20건 × 필드 8개 = 160칸의 PDF 값이다. 칸마다 `value`·`quote`(PDF 텍스트에서 글자 그대로)·`page`·`note`를 적고,
코드가 `quote`가 그 쪽에 있는지 확인한다. 칸이 160개가 아니거나 필드·공고가 빠지면 에러를 낸다.
근거를 못 찾은 칸이 하나라도 있으면 종료 코드 1이다. 같은 칸 비율이 기준에 걸리는지는 리포트를 읽는 사람이 판정한다.

## 흐름

```
fetch (목록 → 상세 HTML → 공고문 PDF)  →  data/raw/<pbno>/{detail.html, notice.pdf}
pdf_text (쪽마다 텍스트, T0·T1)         →  list[str]
extract (LLM 한 번 → 8필드 JSON → 근거 확인)  →  {field: Extraction(value, evidence, page)}
regex_extract (라벨 뒤 값 줍기, --extractor regex)  →  같은 꼴. LLM 대신 쓴다
truth (상세 HTML 표 → 정답 필드)        →  {field: str | None}
normalize + report (필드별 지표 표)     →  stdout + reports/*.md
```

## 현재 상태

- 추출은 LLM이 한다. 8필드마다 값·근거 문장·쪽 번호를 받고, 근거 문장도 값도 그 쪽에 없으면 비운다(값을 남기는 조건 C안)
- 세 번째 시도의 측정: [reports/extract-tune-0.md](reports/extract-tune-0.md)(표를 붙인 T1 대 T0),
  [reports/extract-tune.md](reports/extract-tune.md)(프롬프트 수정 기록, 다듬는 공고 29건),
  [reports/extract-new.md](reports/extract-new.md)(고정 뒤 받은 공고 20건)
- 정규식 baseline(#150): 다듬는 29건으로 규칙을 만들고 고정한 뒤 재는 20건을 한 번 쟀다.
  재는 20건 160칸에서 정규식은 맞음 111(69.4%)·비움 34(21.2%)·다른 값으로 채움 15(9.4%), LLM(C안)은 맞음 154(96.2%)·비움 0·다른 값으로 채움 6(3.8%)이다.
  표 위치를 세야 하는 당첨자 발표일(정규식 4칸 대 LLM 20칸)·계약일(9 대 20)·시공사(10 대 19)에서 갈린다.
  [reports/regex-vs-llm.md](reports/regex-vs-llm.md)(비교 표), [reports/regex-tune.md](reports/regex-tune.md)(규칙 수정 기록),
  [reports/regex-new.md](reports/regex-new.md)(재는 20건), [reports/regex-more.md](reports/regex-more.md)(남은 101건 중 100건, 정규식만. 1건은 스캔 PDF라 건너뜀)
- 수집(#151): `data/raw/`에 수집된 공고 150건, 열리지 않는 PDF 0건.
  [reports/raw.md](reports/raw.md)(`check-raw`), [reports/fetch.md](reports/fetch.md)(수집 기록). 150건에는 LLM 추출·`eval`을 아직 돌리지 않았다
- 청약홈 정답과 PDF 값 대조(#149): 재는 20건 160칸에서 정규화 뒤 같은 칸은 155칸(96.9%), 근거를 PDF에서 못 찾은 칸은 0이다.
  같지 않은 5칸은 표기 차이 3(괄호·쉼표)·다른 값 2(입주예정월 1, 시공사 1)다. PDF 값은 구현 루프가 PDF를 읽고 적었다.
  [reports/truth-check.md](reports/truth-check.md), [labels/pdf-values-20.json](labels/pdf-values-20.json)
- 이후 티켓: PDF에만 있는 필드 #152

## 테스트

```bash
uv run pytest
```

네트워크와 API 없이 돈다. 수집 코드는 `httpx.MockTransport`로, PDF는 테스트 안에서 pymupdf로 만든다.
프롬프트 고정 시점의 LLM 응답은 `tests/fixtures/llm/`에 녹화해 두었고 가짜 LLM으로 재생한다.
프롬프트를 고치면 `tests/fixtures/llm/prompt.sha256`이 어긋나 재녹화를 요구한다.
