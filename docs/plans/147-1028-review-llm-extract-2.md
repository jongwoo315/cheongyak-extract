# #147 리뷰 — PR #4

**대상:** `main...HEAD` — 18 commits, 35 files, +3276 −106 (이 리뷰 파일 제외)
**plan:** docs/plans/147-1027-plan-llm-extract-2.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/report.py:103` | 기본 값을 남기는 조건이 C안이라 근거 문장이 PDF에 없어도 값이 그 쪽에 있으면 남는데, 본 표의 「지어낸 값」·「근거 위치 맞음」 열은 그런 칸도 센다. 정확도 100%인 필드에 지어낸 값 2가 찍힌다(`reports/extract-new.md` 당첨자 발표일) | fix `f6192f3` (본 표 아래에 뜻을 적는 문장을 더했다. 열 계산은 그대로라 이미 커밋된 리포트 수치는 바뀌지 않는다) |
| 2 | Important | `src/cheongyak_extract/fetch.py:134` | 200 응답인데 공고 행이 하나도 없으면(차단 페이지·마크업 변경) `목록 끝`으로 멈춰 정상 종료처럼 보인다 | fix `f5d3263` |
| 3 | Important | `src/cheongyak_extract/fetch.py:126` | 타임아웃 예외는 메시지가 비어 있어 `다운로드 실패: `처럼 원인이 안 남는다 | fix `0784687` |
| 4 | Important | `tests/test_fetch.py` | 네트워크 예외(타임아웃)가 막힘 연속을 끊는다는 docstring 주장을 검증하는 테스트가 없다. 해당 줄을 지워도 테스트가 통과한다 | fix `a74296d` |
| 5 | Important | `tests/test_fetch.py` | 범위 밖 쪽이 같은 행을 되돌려줄 때 `seen`이 걸러 끝내는 동작이 테스트되지 않는다. 없애면 무한 루프다 | fix `a74296d` |
| 6 | Important | `tests/test_extract.py` | C안이 값을 응답이 가리킨 쪽에서만 찾는지 확인하는 테스트가 없다. 전체 텍스트에서 찾도록 바뀌어도 통과한다 | fix `eba39f0` |
| 7 | Important | `tests/test_llm_replay.py:68` | B안 재생 테스트가 `blanked`가 비어 있어도 통과한다. 녹화 9건 중 7건에는 값이 근거에 없는 칸이 실제로 있다 | fix `7656ad2` |
| 8 | Important | `src/cheongyak_extract/__main__.py:55` | `eval`은 정답이 전부 비었거나 응답 모양이 전부 깨져도 공고 수만 맞으면 exit 0이다. `run`은 정답 있음 0을 실패로 친다 | defer — plan 기준이 아니다. 리포트에 `정답 있음` 열과 `응답 모양이 깨져 비운 칸` 표가 나와 화면에서는 보인다. 측정 자동화가 `eval` exit code를 쓰는 곳이 아직 없어 #149 이후 정한다 |
| 9 | Suggestion | `src/cheongyak_extract/llm.py:40` | 캐시의 `response`가 문자열이 아니면(손으로 고친 파일) 깨진 캐시 검사를 지나가 `json.loads(None)`으로 `eval` 전체가 멈춘다 | 기록만 |
| 10 | Suggestion | `src/cheongyak_extract/fetch.py:42` | `tr`에 `data-hmno`·`data-honm`이 없으면 `KeyError`로 끝나 `FetchResult`(받은 번호)를 못 돌려준다 | 기록만 |
| 11 | Suggestion | `src/cheongyak_extract/fetch.py:82` | `notice.pdf`를 한 번에 쓰므로 중간에 끊기면 잘린 파일이 남고 이후 `fetch`가 그 공고를 영영 건너뛴다. `llm.py`의 `os.replace` 방식과 다르다 | 기록만 |
| 12 | Suggestion | `src/cheongyak_extract/llm.py:75` | `resp.usage`가 `None`이면 `AttributeError`로 캐시 쓰기 전에 멈춰 다시 부르면 다시 과금된다 | 기록만 |
| 13 | Suggestion | `src/cheongyak_extract/pipeline.py:93` | `run`은 목록·상세 403/429에 3연속 멈춤이 없다(`fetch`에만 있다). 목록 403은 트레이스백으로 끝난다 | 기록만 |
| 14 | Suggestion | `src/cheongyak_extract/extract.py:66` | 「설계 문서 §코드가 거르는 규칙 5개」는 이 브랜치에 없는 닫힌 브랜치 문서의 절이다. `규칙 1~5` 라벨을 이 PR만으로는 풀 수 없다 | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/report.py:40` | `Doc.extracted`·`blanked`가 `rules[기본 안]`과 같다는 것을 타입이 지키지 않는다. 직접 만든 `Doc`이 `blanked`를 빼먹으면 통계가 조용히 어긋난다 | 기록만 |
| 16 | Suggestion | `src/cheongyak_extract/__main__.py:31` | `fetch --n 0`·`--start-page 0`이 검사 없이 통과한다 | 기록만 |
| 17 | Suggestion | `tests/test_llm_replay.py` | 녹화 응답이 고정한 프롬프트로 받은 것인지 테스트가 확인하지 않는다. 프롬프트를 고치면 녹화가 조용히 옛것이 된다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. 첫 시도 코드(`ea3e0e8`의 `src/`·`tests/`·`pyproject.toml`·`uv.lock`·`.gitignore`)가 이 브랜치에 있고 테스트가 통과한다 | 예 | 커밋 `dce42e0` · `uv run pytest` 285 passed |
| 2. `pdf_text.pages()`가 기본으로 `sort=True` 텍스트를 준다. #148 측정은 기존 순서를 그대로 써서 `reports/normalize.md` 결과(23/24)가 바뀌지 않는다 | 예 | `src/cheongyak_extract/pdf_text.py:8` · `measure-normalize` 재실행 23/24, `git status` 변화 없음 · `tests/test_pdf_text.py:31-32` |
| 3. 목록 2쪽부터 PDF 있는 공고를 지정한 수만큼 받는 `fetch --start-page 2 --n 20`이 있고, `notice.pdf`가 있는 공고와 2026000531은 건너뛰며, 요청 사이 2초, 403·429 3번 연속이면 멈추고 받은 번호를 출력한다. `httpx.MockTransport` 테스트 | 예 | `src/cheongyak_extract/fetch.py:93-165` · `src/cheongyak_extract/__main__.py:44-51` · `tests/test_fetch.py` (건너뛰기·2초·3연속·출력) |
| 4. A·B·C안이 `extract()` 인자로 있고 각각 테스트가 있다. `eval`이 같은 응답에 세 안을 걸어 리포트에 나란히 적는다 | 예 | `src/cheongyak_extract/extract.py:80,207-233` · `tests/test_extract.py` (안별 테스트, `extract_rules` 한 번 호출) · `tests/test_pipeline.py:305-317` |
| 5. 리포트 `extract-tune-0.md`·`extract-tune.md`·`extract-new.md`가 커밋돼 있다 | 예 | `reports/extract-tune-0.md`, `reports/extract-tune.md`, `reports/extract-new.md` (`extract-new2.md`는 「다시 잴 때만」이며 만들지 않았다) |
| 6. 테스트는 API를 부르지 않는다. 고정 시점 응답을 `tests/fixtures/llm/<pbno>.json`에 녹화하고 재생 테스트가 있다 | 예 | `tests/fixtures/llm/` 9개 · `tests/test_llm_replay.py` · 테스트는 `LlmAsk`에 가짜 클라이언트만 쓴다 |
| 7. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green | 예(pytest·ruff) / 판정 불가(Actions) | pytest 285 passed · ruff All checks passed · Actions는 이 리뷰 커밋을 push한 뒤 `gh pr checks`로 확인한다 |
| 실패 징후 1: 재는 공고 160칸의 맞은 칸·틀리게 채운 칸 비율 | 값만 적는다 | `reports/extract-new.md:18` 맞음 145(90.6%) · 비움 1 · 틀리게 채움 14(8.75%). 구간 판정은 사람 몫 |
| 실패 징후 2: `sort=True`가 근거 못 찾아 비운 칸을 줄였나 | 값만 적는다 | `reports/extract-tune-0.md:11-12` 기본 순서 18, `sort=True` 3 (3/18) |
| 실패 징후 3: 고른 안의 조건으로 비운 칸 비율 | 값만 적는다 | `reports/extract-new.md:20,28` 160칸 중 1칸(1%) |
| 실패 징후 4: 다듬는 9건과 재는 공고의 맞은 칸 비율 차이 | 값만 적는다 | PR 본문: 91.7%(66/72) vs 90.6%(145/160). `reports/extract-tune.md:60`, `reports/extract-new.md:28` |
| 실패 징후 5: 신탁 방식 공고의 시행사 맞은 칸 | 값만 적는다 | PR 본문: PDF에 위탁/수탁 표기가 있는 7건 중 4건, 청약홈 정답이 신탁사인 4건 중 2건. 첫 시도 0/4 |
| 실패 징후 6: 프롬프트 수정 5번 이내 | 예 | `reports/extract-tune.md:6` 수정 3번 |
| Done: 고정 커밋(Task 7)이 재는 공고 받기(Task 8)보다 앞이고 이후 `extract.py`·`pdf_text.py`를 고치지 않았다 | 예 | `1a21371`(고정) → `936b84f`(측정). `git log main..HEAD -- src/cheongyak_extract/extract.py src/cheongyak_extract/pdf_text.py`의 마지막은 `1a21371` |
| Done: `data/raw`·`data/llm/`·`.env`·API 키를 커밋하지 않았다 | 예 | `git ls-files`에 `data/`·`.env` 없음 · `git grep`으로 `sk-` 꼴 키 0건 |

## 확인 방법과 한계

- 리뷰 에이전트 5개(코드·에러 처리·테스트·주석·타입)의 지적을 모아 처리했다. 위 표의 Critical은 없다
- 고친 뒤 `uv run pytest` 285 passed, `uv run ruff check` 통과를 확인했다
- 지적 1은 문장만 더했고 열 정의는 그대로다. 이미 커밋된 `reports/extract-*.md`에는 그 문장이 없다(측정 결과 파일이라 고치지 않았다)
- 지적 2는 `fetch_notices`만 고쳤다. `pipeline.run`의 목록 처리(`pipeline.py:98`)는 지적 13과 같은 이유로 그대로다
