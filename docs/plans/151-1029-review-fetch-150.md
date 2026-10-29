# #151 리뷰 — PR #6

**대상:** `main...HEAD` — 6 commits, 15 files, +828 −42
**plan:** docs/plans/151-1029-plan-fetch-150.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Suggestion | `src/cheongyak_extract/fetch.py:121-130` | 첨부 링크가 여럿일 때 `.pdf` 이름인데 열리지 않는 첨부가 먼저 나오면 `BadPdf`를 바로 올려, 뒤에 있는 열리는 PDF를 시도하지 않고 그 공고를 오류로 센다. 이번 150건에서는 열리지 않는 PDF가 0건이라 나타나지 않았다 | 기록만 |
| 2 | Suggestion | `src/cheongyak_extract/fetch.py:145` | `FetchResult.retries`의 기본값 `{}`는 인스턴스끼리 공유되는 가변 객체다. 지금은 `finish()`가 항상 새 `dict`를 넘겨 영향이 없다 | 기록만 |
| 3 | Suggestion | `src/cheongyak_extract/pdf_text.py:29-40` | (추정) 비밀번호가 걸린 PDF는 `get_text()`에서 예외가 나 `열리지 않는 PDF`로 센다. 이번 데이터에서 그런 PDF는 확인하지 못했다 | 기록만 |
| 4 | Suggestion | `reports/fetch.md` | 101건 실제 수집은 마지막 커밋(`790602a`, HTML 오류 페이지를 PDF로 보지 않는다) 전 코드로 돌았다. 리뷰 시점의 `check-raw`를 HEAD 코드로 다시 돌리면 같은 값(디렉터리 163, 수집 150, 열리지 않는 PDF 0, PDF 없음 13)이 나와 수치는 어긋나지 않는다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. PDF를 `notice.pdf.part`에 쓰고 열리는지 확인한 뒤 `notice.pdf`로 바꾼다. 열리지 않으면 `.part`를 지우고 오류로 센다. 디스크의 `notice.pdf`가 안 열리면 다시 받는다 | 예 | `fetch.py:126-131`, `fetch.py:136-138`, `tests/test_fetch.py:299` `:308` `:330` · `uv run pytest` 340 passed |
| 2. 이름이 `.pdf`로 끝나거나 본문이 `%PDF-`로 시작하면 PDF다 | 예 | `fetch.py:65-66`, `tests/test_fetch.py:342` `:353` `:446` |
| 3. 5xx·타임아웃·연결 끊김은 두 번까지 다시 보낸다(5초, 15초). 목록·상세·PDF 모두. 403·429는 다시 보내지 않는다. 다시 보낸 횟수가 `FetchResult`에 있고 `fetch` 출력에 찍힌다 | 예 | `fetch.py:24` `:69-97`, `__main__.py` 「다시 시도 N회」, `tests/test_fetch.py:398` `:407` `:412` `:421` `:428` `:433` |
| 4. `check-raw`: `data/raw/`만 읽어 `reports/raw.md`를 쓴다. 디렉터리 수·수집된 공고 수·열리지 않는 PDF·PDF가 없는 공고(링크 유무) | 예 | `raw_check.py`, `tests/test_raw_check.py` 9개 · 리뷰 때 `check-raw` 실행: 디렉터리 163, 수집 150, 열리지 않는 PDF 0, PDF 없음 13 (EXIT=0) |
| 5. 수집된 공고 150건 이상. `reports/raw.md`·`reports/fetch.md` 커밋 | 예 | `reports/raw.md:4` 150건, 두 파일 모두 커밋됨 |
| 6. `uv run pytest`·`uv run ruff check` 통과, Actions green, 테스트는 청약홈에 요청하지 않음 | 예 | pytest 340 passed, ruff All checks passed, `gh pr checks 6` pytest pass, 테스트는 `httpx.MockTransport` |
| 실패 징후 1: 수집된 공고·오류 수 | 판정 불가(사람 몫) | 수집 49 → 150, 열리지 않는 PDF 0, 요청 실패로 건너뛴 공고 0, `fetch` 1회 멈춤 없음(`reports/fetch.md`) |
| 실패 징후 2: 수집 대상이 아닌 공고 비율 | 판정 불가(사람 몫) | 113건 중 12건 10.6%(착수 때 3/52, 5.8%). 이유별 번호는 PR 본문 표 |
| 실패 징후 3: 이미 받은 49건이 그대로인가 | 예 | 리뷰 때 `reports/fetch.md`의 sha256 49개를 `data/raw/*/notice.pdf`와 다시 대조: 바뀐 파일 0개 |
| 실패 징후 4: 다시 시도한 요청 수 | 판정 불가(사람 몫) | 0회(목록 0, 상세 0, PDF 0). baseline 없음 |
| 이번에 안 하는 것: OpenAI 호출·`run` 기본값·추출 코드 변경 없음 | 예 | `git diff --stat`에 `llm.py`·추출·정규화·리포트 파일 없음. `os.environ` 추가 없음(기존 `llm.py:29`만) |

fix 커밋 없음. 테스트를 다시 돌려 green을 확인했다(340 passed). 인라인 스레드를 달 `push-back`·`defer`·`won't-fix` 행이 없다.
