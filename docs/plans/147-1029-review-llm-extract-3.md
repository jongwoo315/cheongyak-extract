# 147 리뷰 — PR #5

**대상:** `main...HEAD` — 16 commits(이 리뷰 파일 커밋 제외), 36 files, +3819 −105
**plan:** docs/plans/147-1029-plan-llm-extract-3.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/llm.py:44` | 입력을 거의 읽지 않은 응답을 걸러내는 검사(`MAX_CHARS_PER_TOKEN`)가 API를 새로 부를 때만 실행된다. 2578542 전에 캐시된 590토큰·8필드 null 응답이 캐시에 남아 있으면 계속 재생된다. 이 세션에서 `data/llm/` 221개를 훑었을 때는 그런 파일이 없었다 | fix `6d6f9a3` |
| 2 | Important | `src/cheongyak_extract/llm.py:47` | 캐시 파일의 `response`가 문자열이 아니어도(`{"response": 5, …}`) 그대로 돌려줘 `json.loads`에서 `TypeError`가 나고, 잡는 곳이 없어 `eval` 전체가 멈춘다. 기존 테스트의 깨진 캐시 사례는 `output_tokens` 키가 없어 이 경로에 닿지 않았다 | fix `5c50ad6` |
| 3 | Important | `src/cheongyak_extract/__main__.py:64` | `eval` 종료 코드가 `공고 수 × 방식 수`를 기준으로 하는데, 방식이 둘일 때의 종료 코드를 확인하는 테스트가 없었다. 기준이 `공고 수`로 바뀌어도 테스트가 안 깨진다 | fix `4110e65` |
| 4 | Important | `src/cheongyak_extract/pipeline.py:160` | 방식이 둘일 때 건너뛴 공고 이유 앞에 `T0:`·`T1:`이 붙는 분기를 확인하는 테스트가 없었다 | fix `4ad1b3a` |
| 5 | Important | `README.md:32` | 「청약홈에 요청하지 않는다」 아래 코드 블록에 청약홈에 요청하는 `fetch`가 들어 있었다 | fix `6dc4a2d` |
| 6 | Important | `src/cheongyak_extract/__main__.py:64` | `eval`은 정답이 비어 있는 필드가 있어도 종료 코드 0이다(`run`은 `no_truth`를 보고 1을 낸다). 차단 페이지가 `detail.html`로 저장돼 정답이 전부 비어도 `eval`이 통과로 끝난다. 응답이 JSON이 아니어서 8필드를 비운 경우(`BAD_JSON`)도 응답이 캐시에 남고 종료 코드는 0이다 | defer — `eval`은 공고 몇 건만 골라 돌리는 명령이라 정답 없는 필드가 정상인 경우가 있다. 종료 코드 정책을 정해야 해서 이 PR에서 고치지 않는다. 측정에 쓴 49건은 리포트에서 정답 있는 칸 수(232·160)를 직접 확인했다 |
| 7 | Important | `src/cheongyak_extract/fetch.py:82` | `notice.pdf`를 한 번에 쓰고 PDF인지 확인하지 않는다. 쓰다 끊기거나 HTML 오류 페이지가 PDF 이름으로 저장되면 `fetch_notices`가 「이미 있음」으로 건너뛰어 다시 받지 않고, 나중에 `pages()`에서 「PDF를 열 수 없음」으로 나온다. 차단 페이지가 200으로 오면 「상세에 공고문 링크 없음」으로 기록되고 연속 차단 카운트가 0으로 돌아간다 | defer — 수집 코드를 고치는 일이고 이 PR의 측정(다듬는 29건·재는 20건)은 전부 PDF가 열려 처리됐다(건너뛴 공고 0). 150건으로 늘리는 #151에서 함께 본다 |
| 8 | Important | `tests/test_llm_replay.py:35` | 재생 테스트가 각 쪽을 그 칸의 근거 문장으로만 만들어, 기본인 C안의 「값이 그 쪽에 있다」 분기가 녹화 응답으로는 한 번도 결정을 못 한다. `_contains`가 망가져도 이 테스트는 초록이다 | defer — PDF가 git 밖이라 진짜 쪽 텍스트로는 재생할 수 없다. 이 분기는 `tests/test_extract.py:229-255`가 합성 쪽으로 이미 확인한다 |
| 9 | Suggestion | `src/cheongyak_extract/extract.py:218` | C안은 값이 그 쪽 텍스트 어디에든 들어 있으면 근거 문장이 없어도 값을 남긴다. `84`·`2027`처럼 짧은 값은 거의 모든 쪽에 들어 있어 이 조건이 사실상 아무것도 비우지 않는다(재는 공고 160칸 중 C로 비운 칸 0) | 기록만 |
| 10 | Suggestion | `src/cheongyak_extract/llm.py:42` | 캐시 키가 모델과 프롬프트만 해시하고 `OUTPUT_SCHEMA`는 넣지 않는다. 응답 스키마를 바꿔도 옛 형식 응답이 재생된다 | 기록만 |
| 11 | Suggestion | `src/cheongyak_extract/llm.py:60` | `resp.usage`가 `None`이면 `AttributeError`로 끝나 한 공고만 건너뛰지 못하고 전체가 멈춘다. 거부 응답의 refusal 문구는 버려지고, 입력을 못 읽어 다시 부른 호출의 토큰은 리포트에 안 들어간다 | 기록만 |
| 12 | Suggestion | `src/cheongyak_extract/fetch.py:129` | 목록 요청이 성공할 때마다 연속 차단 횟수를 0으로 되돌린다. 쪽마다 상세 요청이 2번씩 403이고 목록은 통과하면 3번 연속 기준에 안 걸려 목록 끝까지 요청한다 | 기록만 |
| 13 | Suggestion | `src/cheongyak_extract/pipeline.py:48` | T1에서 `find_tables()`가 예외를 내도 공고 전체가 「PDF를 열 수 없음」으로 건너뛰어진다. 같은 PDF가 T0로는 열리는데 이유 문구가 PDF 문제로 읽힌다 | 기록만 |
| 14 | Suggestion | `src/cheongyak_extract/extract.py:66` | 「설계 문서 §…」 참조 3곳(`extract.py:66`·`extract.py:77`·`fetch.py:23`)이 가리키는 절이 이 브랜치의 문서에 없다(첫·두 번째 시도 브랜치의 설계 문서에만 있다). 규칙 번호와 A·B·C 정의 자체는 코드와 맞다 | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/report.py:66` | `ungrounded` 주석과 열 이름 「근거 확인 못해 비움」이 값을 남기는 조건으로 비운 칸(`RULE_BLANKS`)만 센다는 점을 안 드러낸다. 근거·쪽 누락(`NO_EVIDENCE`)·쪽 번호 범위 밖(`BAD_PAGE`)으로 비운 칸은 이 칸에 안 든다 | 기록만 |
| 16 | Suggestion | `reports/extract-new.md:9` | `reports/extract-new.md`와 `reports/extract-tune-0.md`는 71857de 전 `report.py`로 만들어져 방식 비교 표에 「처리한 공고」 칸이 없다. 숫자는 같다. 이 세션에서 캐시만으로(잘못된 API 키) 같은 20건을 다시 돌려 154·0·6이 그대로 나오는 것을 확인했다 | 기록만 |
| 17 | Suggestion | `tests/test_llm_replay.py:44` | 해시 테스트는 쪽 없이 만든 프롬프트(`build_prompt([])`)의 해시라 `<page n>` 감싸는 꼴이 바뀌어도 녹화를 다시 하라고 요구하지 않는다. 해시만 갱신하고 녹화를 안 바꿔도 통과한다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. 두 번째 시도 코드가 이 브랜치에 있고 테스트가 통과한다 | 예 | 커밋 `9b81e62`, `uv run pytest` 310 passed(fix 뒤) |
| 2. `pdf_text.pages()`에 T0·T1이 있고 `eval`에서 고를 수 있다 | 예 | `src/cheongyak_extract/pdf_text.py:19`, `src/cheongyak_extract/__main__.py:31-37`, `tests/test_pdf_text.py` |
| 2. `measure-normalize` 결과(23/24)가 바뀌지 않는다 | 예 | 이 세션에서 다시 돌려 「정규화 후 23/24」, `git diff` 비어 있음. `src/cheongyak_extract/measure.py`는 PDF를 읽지 않는다 |
| 2. T1 테스트: 표가 붙고, 표 없는 쪽은 T0와 같다 | 예 | `tests/test_pdf_text.py` `test_tables_true_appends_markdown…` |
| 3. 리포트에 방식별 입력 토큰 합계가 나온다 | 예 | `src/cheongyak_extract/report.py:280-312` `render_mode_table`, `reports/extract-tune-0.md:11-16`(T0 3,034,205 · T1 4,710,984) |
| 4. 리포트 셋이 커밋돼 있다 | 예 | `reports/extract-tune-0.md`·`extract-tune.md`·`extract-new.md`(`extract-new2.md`는 다시 재는 구간이 아니라 없다) |
| 5. 테스트는 API를 부르지 않고 고정 시점 응답을 재생한다 | 예 | `tests/fixtures/llm/` 9건, `tests/test_llm_replay.py`가 `prompt.sha256`과 `build_prompt([])`를 대조. 코드 리뷰 에이전트가 9건 응답이 `data/llm/` 캐시의 같은 프롬프트 응답과 같다고 확인. 테스트는 `OPENAI_API_KEY` 없이 통과 |
| 6. pytest · ruff · Actions green | 예 | pytest 310 passed, `ruff check` All checks passed, Actions pytest pass(fix 전 커밋 `71857de` 기준. fix 커밋 뒤 Actions는 push 후 다시 실행된다) |
| 이번에 안 하는 것: 재는 공고 뒤에 `extract.py`·`pdf_text.py`를 고치지 않는다 | 예 | `git diff 5d836e8..HEAD -- src`는 `report.py`(처리한 공고 칸·공통 공고 토큰 비율)와 이 리뷰의 `llm.py`(캐시 검사)뿐 |
| 이번에 안 하는 것: `data/raw`·`data/llm/`·`.env` 커밋 안 함 | 예 | `git ls-files`에 `data/`·`.env` 없음, diff에 API 키 모양 문자열 없음 |
| 실패 징후 1: 재는 공고 20건 맞음·다른 값으로 채움 비율 | 판정하지 않음 | 맞음 154/160 = 96.25%, 다른 값으로 채움 6/160 = 3.75%. 두 번째 시도(다른 공고 20건): 90.6% · 8.75% (`reports/extract-new.md:28`). fix 뒤 캐시로 같은 20건을 다시 돌려도 154·0·6 |
| 실패 징후 2: 표를 붙였을 때 회사 필드 다른 값으로 채운 칸 | 판정하지 않음 | T0 11칸, T1 11칸 (`reports/extract-tune-0.md:216`) |
| 실패 징후 3: 입력 토큰 T1 ÷ T0 | 판정하지 않음 | 1.55배, 2배 넘은 공고 2026000444 하나 2.86배 (`reports/extract-tune-0.md:17,219`) |
| 실패 징후 4: 고른 조건으로 비운 칸 | 판정하지 않음 | 160칸 중 0 (`reports/extract-new.md:30`) |
| 실패 징후 5: 다듬는 공고와 재는 공고의 맞은 칸 비율 차이 | 판정하지 않음 | 94.4% − 96.25% = −1.9%p |
| 실패 징후 6: 프롬프트 수정 횟수 | 예 | 3번 (`reports/extract-tune.md` 수정 1~3) |

## 확인한 것

- fix 뒤 `uv run pytest` 310 passed, `uv run ruff check`·`ruff format --check` 통과
- `eval`로 재는 공고 20건을 캐시만으로 다시 돌렸다(`OPENAI_API_KEY=sk-invalid`). 종료 코드 0, 정답 있는 칸 160 · 맞음 154 · 비움 0 · 틀리게 채움 6으로 `reports/extract-new.md`와 같다. 캐시 검사를 넣은 뒤에도 캐시가 미스로 바뀐 공고가 없다
- 리뷰는 `pr-review-toolkit:review-pr`의 코드·테스트·silent failure·주석 에이전트 4개와 직접 읽기로 했다. 타입 설계 에이전트는 새 타입이 `NamedTuple`·`dataclass` 몇 개뿐이라 돌리지 않았다
