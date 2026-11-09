# cheongyak-extract

청약 모집공고문 PDF에서 구조화된 필드를 뽑고, 청약홈 상세 페이지 표 값을 정답으로 필드별 eval 리포트를 낸다.

## 판단 기록

구현은 AI 에이전트가 했다. 티켓마다 무엇을 성공으로 볼지는 착수 전에 내가 먼저 한 줄로 썼고,
PR이 그 기준을 맞췄는지는 내가 판정했다. 2026-10-25부터 쌓았다.

티켓 10개 · 판정 14건 · jw 기준으로 통과 9 · 반려 4 · 유보 1

자동 기준과 내 판정이 갈린 티켓:

| 티켓 | 착수 전 기준 (jw) | 결과 | 판정 | 이유 |
| --- | --- | --- | --- | --- |
| #147 LLM 추출 | extract()의 fields에 대한 값들을 llm이 제대로 파싱한다. 파싱하지 못하면 비운다. | 프롬프트 고정 뒤 처음 본 공고에서 40칸 중 25칸(62.5%), 48칸 중 27칸(56.3%) 맞음. 자동 기준은 9개 중 8개 통과 | 반려 | 처음 시도한 40개는 62%의 정답률이었고 그다음 48개로 했을 때에는 56%로 llm이 값들을 맞는 필드에 가져오는 비율이 너무 적었음 |
| #147 LLM 추출 (두 번째 시도) | 앞선 pr #3에서 언급된 사실(근거 문장을 PDF에서 찾지 못해 코드가 비운 18칸 중 16칸은 LLM 값이 맞았다, 신탁 사업 4건에서 LLM은 시행사로 위탁자를 골랐다. 청약홈 정답은 수탁자인 신탁사다, 청약홈 목록에 공고가 10건뿐이라, 처음 본 공고로 잴 수 있는 것은 최대 6건이었다)을 바탕으로 이번에는 extract()가 필드마다 값을 정확히 판정한다 | 프롬프트 고정 뒤 처음 본 공고 20건에서 160칸 중 145칸(90.6%) 맞음, 정답과 다른 값을 채운 칸 14(8.75%). 자동 기준은 7개 모두 통과 | 반려 | 추출 성능은 확연히 개선이 됐음(62.5% → 90.6%), 하지만 다른 값으로 채운게 1.25%p 증가, sort=True 부분 좀 더 개선 필요 |
| #152 PDF 전용 필드 | pdf에 있는 필드 3개애 대한 수동 정답이 나오고 점수도 계산한다 | 정답 150칸(값 142, null 8), 근거 검사에 걸린 칸 0. 재는 30건에서 정답에 값이 있는 88칸 중 75칸(85.2%) 맞음, 거주지 우선 비율은 30칸 중 20칸. 자동 기준 7개 모두 통과 | 반려 | 내 기준과 플랜은 모두 만족했으나 거주지 우선 비율 계산과 거주지 정답을 적는 방식에서 llm의 문제를 발견함 |
| #152 거주지 출처 통일 (재시작) | llm이 거주지 우선 비율 계산과 거주지 정답을 소스별로 차이없이 통일되게 판정 | 새 공고 30건 거주지 30칸 중 29칸 같음, 1칸 다름(일반공급 ①지역 줄을 못 찾아 PDF 전체를 준 공고). 정답 검사에 걸린 칸 0. 자동 기준 9개 모두 통과 | 유보 | 정답검사는 모두 통과했으나 지역을 다르게 판단한 한 곳은 llm로직이 잘못됐음, 또한 정답 쪽에서 llm이 보낸 지역을 단지 동일하게 읽었다고 해서 그 코드가 고른 게 맞았는지 판단할 수 없음. #179에서 다시 잰다 |
| #179 거주지 묶음 찾기 | llm이 '일반공급 1지역'을 찾는 로직 개선이 필요하며, 이를 통해서 '거주지 llm 질문'에 pdf전체를 던지는 일이 없다 | 공고 149건 중 PDF 전체를 넘기는 공고 24건에서 1건(2026000184, 텍스트 뒤섞임). LLM 거주지 맞은 칸 재는 30건 30/30. 자동 기준 8개 모두 통과 | 반려 | 전반적으로 거주지 정보를 잘 찾지만 2026000184에 세 규칙이 찾는 줄이 없음, 이 이슈 개선하는 로직 필요 |

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

HTML 값과 PDF 값 중 어느 쪽이 맞는지 jw가 판정하려면(청약홈과 OpenAI에 요청하지 않는다):

```bash
uv run python -m cheongyak_extract judge-source   # 판정 파일이 없으면 만들고, 있으면 읽어 reports/source-judge.md를 쓴다
```

HTML 값·PDF 값(`labels/pdf-values-20.json`)·LLM 값이 정규화 뒤 하나라도 다른 칸을 `labels/source-judge.json`에 넣는다(재는 20건 160칸 중 4칸). 파일에는 있는데 이번에 안 고른 칸(주소의 쉼표·괄호만 달라 정규화 뒤 같아진 공급위치 3칸, #183)은 파일에 그대로 두고 리포트의 「정규화로 같아져 판정할 칸에서 빠진 칸」 절에 jw 판정과 함께 적는다. 방식별 합계에서는 같은 칸으로 센다.
칸마다 HTML 값·PDF 값·근거 줄·쪽·LLM 값이 있고 `jw`·`jw_note`는 null이다. jw가 칸을 보고 `jw`에 `HTML`(HTML 쪽이 맞다)·`PDF`(PDF 쪽이 맞다)·`둘 다`(같은 뜻이다)·`둘 다 아님` 중 하나를 적고,
필요하면 `jw_note`에 한 줄을 적는다. HTML 값과 PDF 값이 같은 칸(시행사 2칸)에 `HTML`을 적으면 HTML 쪽에만 세고 `둘 다`를 적으면 두 쪽에 센다. 다 채운 뒤 같은 명령을 다시 돌리면 방식별로 맞는 값을 가진 칸 수가 나온다.
`jw` 칸은 코드가 채우지 않고, 다시 돌려도 덮어쓰지 않는다. `jw`에 위 네 값 밖의 값을 적거나, 이번에 골랐는데 파일에 없는 칸이 있거나, 칸의 HTML 값·PDF 값·근거 줄·쪽·LLM 값이 jw가 본 값과 다르거나, 같은 칸이 두 번 있으면 에러다. 근거 줄을 그 쪽에서 못 찾은 칸이 있으면 종료 코드 1이다.
세 결정(정규식 대 LLM, HTML 대 PDF, PDF에만 있는 필드)의 사실은 [docs/decision-source.md](docs/decision-source.md)에 있고, 고른 방식과 이유는 jw가 쓴다.

PDF에만 적힌 필드 3개를 수동 정답으로 재려면(청약홈에 요청하지 않는다. `eval-pdf`는 OpenAI를 부른다):

```bash
uv run python -m cheongyak_extract check-pdf-labels                                           # 정답 파일 둘(180칸)을 검사하고 reports/pdf-labels.md를 쓴다
uv run python -m cheongyak_extract eval-pdf --set tune --out reports/pdf-fields-tune-2.md      # 기존 50건, 세 필드
uv run python -m cheongyak_extract eval-pdf --set test --out reports/pdf-resident-test.md      # 새 30건, 거주지만
```

`--set tune`은 `labels/pdf-only-50.json`의 50건을, `--set test`는 `labels/pdf-resident-30.json`의 새 30건을 잰다.
거주지는 따로 묻는다. 전매제한과 신혼부부 소득 기준은 전체 텍스트로 한 번에 묻는다.

필드 3개의 뜻은 공고 하나에 값 하나로 정했다
(설계: [docs/plans/152-1031-design-pdf-only-fields.md](docs/plans/152-1031-design-pdf-only-fields.md) §필드 3개의 뜻).

- 전매제한 기간: 일반공급 당첨자의 전매제한 기간. 1쪽 요약표의 전매제한 칸이 있으면 그 값(`3년`, `6개월`, `없음`)
- 거주지 우선 비율: 일반공급 물량을 거주 지역별로 나눈 비율, 우선순위가 높은 지역부터(`평택시 30% / 경기도 20% / 기타 50%`). 비율 없이 해당지역 거주자 우선만 적혀 있거나 한 지역이 100%이고 나머지가 0%면 `해당지역 100%`. 0%인 지역은 쓰지 않고, %의 합은 100이어야 한다
  - 같은 공고 PDF 안에서 아래 순서로 처음 걸리는 곳에서 읽는다: (1) 일반공급 「2순위 : ①지역」 줄 아래의 「①지역」 묶음 (2) 특별공급과 일반공급에 같이 적용된다고 적힌 지역우선 공급기준 표 (3) 일반공급 안내의 해당지역 거주자 우선 문장. 코드가 이 순서로 처음 걸리는 것을 묶음으로 잘라 LLM에 주고, 셋 다 못 찾으면 PDF 전체를 준다. 특별공급 유형별 절의 지역 줄은 읽지 않는다. 규칙 1·2·3의 뜻과 정의한 줄은 [docs/concepts.md](docs/concepts.md)에 있다
  (설계: [docs/plans/152-1103-design-resident-source.md](docs/plans/152-1103-design-resident-source.md) §고르는 규칙)
- 신혼부부 소득 기준: 신혼부부 특별공급에서 소득 조건이 가장 낮은 첫 단계(우선공급·1단계)의 월평균소득 대비 %와 맞벌이 %(`100% (맞벌이 120%)`)

`labels/pdf-only-50.json`은 공고 50건(`data/raw/`에서 PDF 텍스트가 있는 149건을 정렬해 `random.Random(152).sample` 50건,
앞 20건이 다듬는 공고 `tune`, 뒤 30건이 재는 공고 `test`) × 필드 3개 = 150칸이다. 코드가 같은 방법으로 50건을 다시 뽑아 파일의 목록과 대조한다.
칸마다 `value`·`quote`·`page`·`note`를 적고, 값이 있는 칸은 `quote`가 그 쪽 텍스트에 있는지, `value`의 숫자가 `quote`에 있는지 확인한다.
정답은 jw가 아니라 구현 루프가 PDF 텍스트를 읽고 적었다. 정답 파일의 첫 커밋 뒤에 세 필드 LLM 추출을 처음 돌렸다.
이 파일의 거주지 50칸은 위 고르는 규칙으로 다시 검사해 9칸을 고쳤다(고친 칸은 `note`에 이유가 있다).

`labels/pdf-resident-30.json`은 새로 재는 공고 30건의 거주지 30칸이다. 위 50건을 뺀 99건을 정렬해 `random.Random(1522).sample` 30건을 뽑고,
코드가 다시 뽑아 파일의 목록과 대조한다. 거주지 정답 80칸(50 + 30)은 `quote`가 묶음 안에 있는지, 꼴이 표대로인지, %의 합이 100인지도 확인한다.

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
  재는 20건 160칸에서 정규식은 맞음 112(70.0%)·비움 34(21.2%)·다른 값으로 채움 14(8.8%), LLM(C안)은 맞음 154(96.2%)·비움 0·다른 값으로 채움 6(3.8%)이다. LLM 쪽 숫자는 `reports/extract-new.md`(바꾸기 전 정규화로 채점)에서 읽은 값이라, 새 정규화로 다시 맞추면 공급위치 2칸(2026000443·2026000437)이 맞은 칸이 되어 LLM이 154가 아니라 156이다.
  표 위치를 세야 하는 당첨자 발표일(정규식 4칸 대 LLM 20칸)·계약일(9 대 20)·시공사(10 대 19)에서 갈린다.
  [reports/regex-vs-llm.md](reports/regex-vs-llm.md)(비교 표), [reports/regex-tune.md](reports/regex-tune.md)(규칙 수정 기록),
  [reports/regex-new.md](reports/regex-new.md)(재는 20건), [reports/regex-more.md](reports/regex-more.md)(남은 101건 중 100건, 정규식만. 1건은 스캔 PDF라 건너뜀)
- 수집(#151): `data/raw/`에 수집된 공고 150건, 열리지 않는 PDF 0건.
  [reports/raw.md](reports/raw.md)(`check-raw`), [reports/fetch.md](reports/fetch.md)(수집 기록). 150건에는 LLM 추출·`eval`을 아직 돌리지 않았다
- 청약홈 정답과 PDF 값 대조(#149): 재는 20건 160칸에서 정규화 뒤 같은 칸은 158칸(98.8%), 근거를 PDF에서 못 찾은 칸은 0이다.
  같지 않은 2칸은 다른 값 2(입주예정월 1, 시공사 1)다. 주소의 쉼표·괄호만 달랐던 3칸은 #183에서 같은 칸이 됐다(그전 155칸). PDF 값은 구현 루프가 PDF를 읽고 적었다.
  [reports/truth-check.md](reports/truth-check.md), [labels/pdf-values-20.json](labels/pdf-values-20.json)
- PDF에만 있는 필드 3개(#152, 거주지를 PDF 안 같은 곳에서 읽는 재시작, #179에서 묶음 찾기를 고침): 거주지를 따로 묻고, 코드가 규칙 1(일반공급 ①지역 묶음)·2(지역우선 공급기준 표)·3(해당지역 우선 문장) 순서로 묶음을 찾아 그 묶음만 LLM에 준다.
  PDF 텍스트가 있는 149건 중 묶음을 찾는 공고가 125건에서 149건(전부)으로 늘었다(규칙 1 137 · 규칙 2 9 · 규칙 3 3). 세 규칙 모두 못 찾아 PDF 전체를 넘기는 공고는 24건에서 0건이 됐다. 마지막 1건이던 2026000184는 텍스트가 뒤섞인 것이 아니라 71쪽 전부가 90도 회전돼 있어 글자 순서가 어긋난 것이었고, `pdf_text.pages`가 쪽 회전을 풀고 뽑게 하자 21쪽에서 규칙 1 묶음을 찾는다.
  새로 뽑은 재는 30건의 거주지 30칸에서 맞음 30(100.0%)·비움 0·다른 값으로 채움 0이다. 읽은 곳별로 `묶음(규칙 1)` 29칸과 `묶음(규칙 2)` 1칸이 모두 맞다.
  기존 50건(다듬는 공고)에서는 거주지 값 있는 50칸(2026000184가 값 있는 칸이 됐다) 중 50칸이 맞고, 전매제한 48/48, 신혼부부 소득 기준 43/47이다. 거주지 정답 80칸 중 정답 검사에 걸린 칸은 1이다(2026000116: 정답 근거 줄은 규칙 3 문장이고 코드는 같은 쪽의 규칙 1 묶음을 골랐다).
  #179에서는 거주지 설명을 묶음 규칙마다 따로 쓰고, 다듬는 50건 결과가 기준 안이라 더 고치지 않았다. 반려 뒤에는 묶음 끝 판정이 줄 중간의 `■`에서도 묶음을 끝내게 바꿔 2026000293 묶음이 76줄에서 26줄이 됐고, 입력이 바뀐 재는 30건을 한 번 더 쟀다(30/30). 정답은 jw가 아니라 구현 루프가 PDF를 읽고 적었다(2026000184 세 칸은 반려 뒤 회전을 푼 텍스트에서 적었다).
  [reports/pdf-labels.md](reports/pdf-labels.md), [reports/pdf-fields-tune-2.md](reports/pdf-fields-tune-2.md), [reports/pdf-resident-test.md](reports/pdf-resident-test.md)
- (반려된 첫 시도, PR #9) 수동 정답 50건 150칸, 다듬는 20건으로 세 필드 설명을 세 번 고친 뒤 재는 30건을 한 번 쟀다.
  재는 30건에서 정답에 값이 있는 88칸 중 맞음 75(85.2%)·비움 7(8.0%)·다른 값으로 채움 6(6.8%)이다. 필드별 맞음은 전매제한 30/30, 거주지 우선 비율 20/30, 신혼부부 소득 기준 25/28이다.
  거주지 20/30이 반려 이유다. LLM이 일반공급이 아닌 다자녀 특별공급의 ①지역 줄(50%)을 읽은 칸이 있었다.
  [reports/pdf-fields-tune.md](reports/pdf-fields-tune.md), [reports/pdf-fields-test.md](reports/pdf-fields-test.md)

## 테스트

```bash
uv run pytest
```

네트워크와 API 없이 돈다. 수집 코드는 `httpx.MockTransport`로, PDF는 테스트 안에서 pymupdf로 만든다.
프롬프트 고정 시점의 LLM 응답은 `tests/fixtures/llm/`에 녹화해 두었고 가짜 LLM으로 재생한다.
프롬프트를 고치면 `tests/fixtures/llm/prompt.sha256`이 어긋나 재녹화를 요구한다.
