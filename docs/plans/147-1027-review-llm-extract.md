# 147 리뷰 — PR #3

**대상:** `main...HEAD` — 20 commits, 24 files, +2062 −101 (이 리뷰의 fix 7개 포함)
**plan:** docs/plans/147-1026-plan-llm-extract.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/extract.py:170` | 캐시 파일이 깨지면(`{trunc`) 캐시 읽기의 `JSONDecodeError`가 「응답이 JSON 객체가 아님」으로 잡혀 그 공고 8칸이 조용히 비고, 깨진 캐시가 그대로 남아 매번 같은 결과가 재생된다 | fix `bb8af7a` |
| 2 | Important | `src/cheongyak_extract/report.py:164` | 응답 모양이 깨져 비운 이유(`BAD_JSON`·`BAD_CELL`·`NO_KEY`)가 리포트 어디에도 안 나와, 응답이 통째로 깨진 공고가 LLM이 일부러 비운 공고와 같은 「비움」으로 보인다 | fix `0384def` |
| 3 | Important | `src/cheongyak_extract/extract.py:163` | 규칙 4는 근거 문장이 그 쪽에 있는지만 봐서 표 머리글만 복사한 근거(`당첨자발표일`, `시행위탁자`)도 통과한다. 리포트의 「지어낸 값」은 같은 `grounded()`를 다시 써서 구조상 늘 0이라 통과 기준 8은 측정이 아니라 같은 말의 반복이다 | defer — 설계 §코드가 거르는 규칙이 값이 근거 안에 있는지는 이번에 보지 않기로 했고, PR 본문 실패 징후 4가 「0은 구조상 0」이라고 이미 적었다. 값 포함 검사를 비우는 규칙으로 쓰면 맞은 칸 13개를 잃는다(공백만 빼고 비교했을 때 두 리포트 기준). 측정 열로만 넣을지는 #149(정답 수동 대조) 전에 정한다 — 후속 티켓 필요 |
| 4 | Important | `tests/test_pipeline.py:275` | `run`/`evaluate` 테스트의 가짜 LLM이 근거 규칙에 걸리는 응답을 주지 않아, `_analyze`가 `blanked`를 빼먹어도(`{}`) 실패 징후 2의 지표가 항상 0%가 되는데 테스트가 안 깨진다 | fix `2931178` |
| 5 | Important | `src/cheongyak_extract/pipeline.py:52` | 인증·한도 오류는 공고별 건너뜀으로 삼키지 않고 멈춘다는 약속에 테스트가 없다. `except (ContextExceeded, BadResponse)`가 `except Exception`으로 넓어져도 안 깨진다 | fix `f3a4bf2` |
| 6 | Important | `src/cheongyak_extract/report.py:32` | 요약의 분모(`_GAVE_THEN_BLANKED`)는 규칙 2·3·4만 세는데 테스트는 규칙 4와 규칙 1만 만든다. 튜플에서 `BAD_PAGE`를 빼거나 `BAD_JSON`을 넣어도 안 깨진다 | fix `a084824` |
| 7 | Important | `src/cheongyak_extract/llm.py:69` | 끝나지 않은 응답을 건너뛸 때 메시지에 `status`만 있고 `error`·`incomplete_details`가 없어, 한도 초과와 일시 장애를 메시지로 구분할 수 없다 | fix `b5d3330` |
| 8 | Important | `README.md:39` | README가 비운 이유 전부를 「근거 확인 못해 비움」 열이 센다고 읽히게 쓰였다. 실제로는 규칙 4로 비운 칸만, 정답이 있는 칸만 센다 | fix `06a81e3` |
| 9 | Important | `src/cheongyak_extract/extract.py:20` | `Extraction.__post_init__`이 타입을 검사하지 않아 `Extraction("a", "e", True)`가 만들어지고 `Extraction(" a ", "e", 1)`처럼 strip 안 된 값도 통과한다 | push-back — plan 통과 기준 3이 정한 `invariant`는 값·근거·쪽의 세 가지 모순이고 그대로 구현돼 있다. 유일한 생성 경로 `_check`가 문자열 타입, `bool`이 아닌 정수 쪽, `strip()`을 먼저 거른다. 새 생성 경로가 생기면 그때 같이 올린다 |
| 10 | Important | `src/cheongyak_extract/extract.py:85` | `Extracted`가 `fields`는 `FIELDS` 키 전부, `blanked`는 그 부분집합이라는 관계를 타입으로 강제하지 않는다 | push-back — `extract()` 한 곳에서만 만들고 `test_rule_5`가 키 8개가 항상 있음을 확인한다. `blanked`를 `Extraction`에 합치는 것은 이번 PR 범위 밖 설계 변경이다 |
| 11 | Important | `src/cheongyak_extract/llm.py:75` | 응답이 `completed`인데 `resp.usage`가 `None`이면 캐시를 쓰기 전에 `AttributeError`로 멈추고, 이미 과금된 응답이 캐시에 안 남는다 | defer — Responses API는 `completed` 응답에 `usage`를 담는다. 이 PR의 실제 호출 9건에서 한 번도 없었다. 없는 응답이 관측되면 응답을 먼저 캐시에 쓰고 토큰 수를 비워 두는 쪽으로 고친다 |
| 12 | Suggestion | `src/cheongyak_extract/extract.py:152` | 근거를 못 찾아 비운 칸의 원래 값·근거·쪽이 버려져, 리포트만으로는 실패 징후 2가 요구한 「근거 문장과 그 쪽 텍스트 나란히」를 만들 수 없다 | 기록만 — PR 본문이 캐시 응답으로 18칸을 이미 나란히 적었다 |
| 13 | Suggestion | `src/cheongyak_extract/llm.py:37` | 캐시 키가 `OUTPUT_SCHEMA`를 포함하지 않아 스키마를 바꿔도 같은 프롬프트면 옛 응답이 재생된다 | 기록만 |
| 14 | Suggestion | `src/cheongyak_extract/pipeline.py:44` | PDF 열기 실패의 이유에 예외 클래스 이름이 없어 `MemoryError`도 「PDF를 열 수 없음」으로 보인다 | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/__main__.py:39` | `eval`의 종료 코드는 처리한 공고 수만 보고 `run`처럼 「정답 있음이 0인 필드」를 안 본다 | 기록만 |
| 16 | Suggestion | `src/cheongyak_extract/report.py:57` | `ungrounded` 주석과 모듈 docstring이 규칙 4만 센다는 것, `146` 설계의 지표 표에 새 열 2개가 없다는 것을 적지 않았다 | 기록만 |
| 17 | Suggestion | `src/cheongyak_extract/pipeline.py:52` | 「인증·한도 오류는 잡지 않고」의 「한도」가 바로 윗줄의 컨텍스트 한도와 헷갈린다. `tests/test_main.py:57` 이름의 `offline`은 청약홈 요청만 막고 OpenAI 호출은 막지 않으며, README 캐시 설명은 모델이 키에 들어간다는 것을 안 적었다 | 기록만 |
| 18 | Suggestion | `src/cheongyak_extract/extract.py:120` | 프롬프트 고정 뒤 `PROMPT_HEAD`·`_FIELD_HELP`를 바꿔도 깨지는 테스트가 없어 `extract-new.md`가 무효가 되어도 모른다. 캐시 키가 바뀌어 `eval`이 조용히 API를 다시 부른다 | 기록만 |
| 19 | Suggestion | `src/cheongyak_extract/extract.py:91` | `FIELDS`·`KIND`·`_FIELD_HELP` 키가 같은지 import 때 확인하지 않고, `_CELL` 사전 하나를 8개 속성이 같이 쓴다 | 기록만 |
| 20 | Suggestion | `src/cheongyak_extract/pipeline.py:55` | `getattr(ask, "last_usage", None)`·`getattr(ask, "model", None)`는 오타를 못 잡는다. `Protocol`로 올릴 수 있다 | 기록만 |
| 21 | Suggestion | `src/cheongyak_extract/report.py:43` | `Doc.blanked`·`usage` 기본값 때문에 넘기는 것을 빼먹어도 지표가 조용히 0이 된다. 생성 경로는 `_analyze` 하나다 | 기록만 |
| 22 | Suggestion | `tests/test_llm.py:95` | `os.replace`를 `write_text`로 되돌려도 깨지는 테스트가 없고, 프롬프트에서 `<page n>`과 쪽 본문이 짝지어 나오는지, `page: true` 거부, 이유 상수 비교도 확인하지 않는다 | 기록만 |
| 23 | Suggestion | `docs/plans/147-1026-plan-llm-extract.md:138` | Done criteria의 `git diff main...HEAD \| grep -c sk-`가 1이다. plan이 이 명령을 적은 줄 자신이 걸린 것이고 실제 키는 0건(`sk-` 뒤 16자 이상 패턴 0건) | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. `extract(pages, ask)`가 LLM 호출 한 번으로 8개 필드 전부의 `Extraction`을 돌려주고 응답에 키가 빠져도 모든 키가 있다 | 예 | `src/cheongyak_extract/extract.py:168`, `tests/test_extract.py::test_rule_5_missing_key_is_blank_not_keyerror` |
| 2. 거르는 규칙 5개가 각각 테스트로 있고 걸린 칸은 비워지고 이유가 남는다 | 예 | `tests/test_extract.py:112-151` (`test_rule_1`~`test_rule_5`) |
| 3. `Extraction`이 모순 값을 만들면 `ValueError` | 예 | `src/cheongyak_extract/extract.py:20`, `tests/test_extract.py:41` |
| 4. 실제 호출은 프롬프트 sha256 캐시를 거치고 같은 프롬프트 두 번째 호출은 API를 안 부른다 | 예 | `src/cheongyak_extract/llm.py:37`, `tests/test_llm.py::test_second_call_with_same_prompt_hits_cache_and_skips_api` |
| 5. 테스트는 API를 안 부르고 설계 공고 3건의 실제 응답이 `tests/fixtures/llm/<pbno>.json`에 있어 재생 테스트가 있다 | 예 | `tests/fixtures/llm/` 3개, `tests/test_llm_replay.py:45` |
| 6. `eval --pbno ... --out ...`이 `data/raw/<pbno>/`만 읽어 리포트를 쓰고, 열 2개·틀리게 채운 칸 목록·공고별 토큰 수가 있다 | 예 | `src/cheongyak_extract/pipeline.py:107`, `tests/test_pipeline.py::test_evaluate_reads_only_raw_dir_and_writes_report`, `reports/extract-design.md` |
| 7. 리포트 두 개가 커밋돼 있다 (`extract-design.md`, 프롬프트 고정 뒤 새 공고의 `extract-new.md`) | 예 | `reports/extract-design.md`, `reports/extract-new.md`(+`extract-new2.md`), 고정 커밋 `ecd4b18`이 `9961f09`보다 앞 |
| 8. 지어낸 값이 두 리포트 모두 0이다 | 예 (값은 0). 이 0은 규칙 4와 같은 함수로 잰 것이라 구조상 0이다 (지적 3) | `reports/extract-design.md`·`reports/extract-new.md`의 「지어낸 값」 열 전부 0 |
| 9. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green | 예 | 이 리뷰 뒤 로컬 186 passed, `ruff check`·`ruff format --check` 통과. Actions는 이전 head `bcdb719`에서 pass(run 40345972546), 이 리뷰의 push 뒤 head는 확인 전 |
| 실패 징후 1 — 새 공고 맞음 비율과 `LLM 오답` 칸 수 | 값만 적는다 | 5건 25/40(62.5%), 6건 27/48(56.3%). `LLM 오답` 1칸(PR 본문 분류), 시행사 3칸 중 2칸은 PR 본문이 `정답 쪽`으로 분류했다. baseline 없음(첫 LLM 측정) |
| 실패 징후 2 — 규칙 4로 비운 칸 비율 | 값만 적는다 | `extract-design` 0/24, `extract-new` 12/40(30%), `extract-new2` 6/8(75%) |
| 실패 징후 3 — 맞음 비율 차이(설계 3건 − 새 공고) | 값만 적는다 | 100% − 62.5% = 37.5%p(5건), 100% − 56.3% = 43.8%p(6건) |
| 실패 징후 4 — 지어낸 값 | 값만 적는다 | 세 리포트 모두 0. 구조상 0이다(지적 3) |
| 실패 징후 5 — 컨텍스트 한도로 건너뛴 공고 | 값만 적는다 | 건너뛴 공고 0건, 입력 토큰 최대 150,209(2026000496) |
| 이번에 안 하는 것 — 프롬프트 고정 뒤 `extract.py`의 프롬프트를 안 고친다 | 예 | `git diff ecd4b18..HEAD -- src/cheongyak_extract/extract.py`는 이 리뷰의 fix `bb8af7a`(프롬프트 밖 `extract()` 본문 3줄)만 있고 `PROMPT_HEAD`·`_FIELD_HELP`는 그대로다 |

## 메모

- 이 세션의 fix 7개는 모두 리뷰 지적이다. `report.py`·`tests/test_report.py`에는 `ruff format`도 같이 돌렸다.
- fix `bb8af7a`는 `extract.py`를 건드리지만 프롬프트가 아니라 `extract()`의 `ask` 호출 위치만 옮겼다. 그래서 캐시 키가 안 바뀌고 `reports/*.md`는 다시 만들지 않았다. `0384def`의 새 절은 응답 모양 오류가 있을 때만 나와서 커밋된 리포트 3개도 그대로 맞다.
- 테스트는 fix 전 174 passed에서 186 passed로 늘었다.
- 인라인 스레드는 `defer` 2건(지적 3·11)과 `push-back` 2건(지적 9·10)에 올린다.
