# #148 리뷰 — PR #2

**대상:** `main...HEAD` — 20 commits, 14 files, +781 −4 (이 리뷰의 fix 11개 포함)
**plan:** docs/plans/148-1026-plan-normalize.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/normalize.py:22` | 끝 연도를 생략한 날짜 범위(`2026.11.10~11.11`)가 날짜 하나로 읽혀 정답 `2026-11-10`과 같아진다 | fix `fddebd7` |
| 2 | Important | `src/cheongyak_extract/normalize.py:38` | 끝 연도를 생략한 월 범위(`2029.08~09`)가 월 하나로 읽혀 정답 `2029-08`과 같아진다 | fix `4e15163` |
| 3 | Important | `tests/test_pdf_forms.py:32` | 쪽 번호가 범위 밖이어도 통과한다 (`page: 0`이 마지막 쪽을 가리킨다) | fix `727085c` |
| 4 | Important | `tests/test_pdf_forms.py:23` | 값이 null뿐인 fixture도 통과한다 | fix `c7f0422` |
| 5 | Important | `src/cheongyak_extract/measure.py:29` | fixture가 비면 `0/0`과 「안 맞는 쌍 없음」이 찍혀 깨끗해 보인다 | fix `55a808b` |
| 6 | Important | `tests/test_measure.py` | 24쌍 결과(전 3 → 후 22 이상)를 고정한 테스트가 없다 | fix `3d16adb` |
| 7 | Important | `tests/test_normalize.py:38` | 회사 목록에서 이름 하나가 빠진 경우가 다르게 남는지 검사가 없다 | fix `1daed75` |
| 8 | Important | `tests/test_normalize.py:50` | 블록만 다른 주소(`AC3블록`/`AC4블록`)가 다르게 남는지 검사가 없다 | fix `74e4d29` |
| 9 | Important | `src/cheongyak_extract/normalize.py:1` | 모듈 docstring이 규칙이 있다고 가리키는 설계 문서 §설계 결정에는 종류 목록뿐이다 | fix `aa6c054` |
| 10 | Important | `tests/test_normalize.py:102` | 주석이 「값이 둘 이상 읽히면」이라 하는데 7개 중 일부만 그 경우다 | fix `160d27b` |
| 11 | Important | `tests/test_pdf_forms.py:32` | 모의값을 정답에 맞게 줄여도(`358세대`만 남기기) 「그 쪽에 있다」 검사는 통과한다. 줄 경계까지 맞는지 검사해야 한다 | push-back — 모의값은 표의 한 칸이고 같은 PDF 줄에 다른 칸이 같이 있어서(`㈜넥스트건설` 옆에 다른 칸) 줄 경계로 비교하면 정상 값이 실패한다. plan 통과 기준 2가 정한 검사는 「공백만 무시하고 그 쪽에 있다」이고 그대로 구현돼 있다 |
| 12 | Important | `tests/test_pdf_forms.py:35` | CI에는 `data/raw`가 없어서 이 테스트 3개가 전부 skip된다. 통과 기준 2는 GitHub Actions에서 검증되지 않는다 | defer — CI에서 돌리려면 공고 PDF 쪽 텍스트를 레포에 커밋해야 하는데 외부 공고문을 public 레포에 넣어도 되는지 정해야 한다. 그 전까지 이 검사는 로컬 전용이다 (PR 본문에 적을 것) |
| 13 | Important | `src/cheongyak_extract/normalize.py:22` | `2026.10.23 접수마감`처럼 날짜 뒤 글자가 신문명·URL이 아니어도 날짜로 읽혀 `2026-10-23`과 같아진다 | push-back — 설계 결정이 「정답 쪽에 신문명·URL이 붙어 있어 날짜 밖 글자는 떼고 비교한다」이다. 떼도 되는 글자와 값을 바꾸는 글자를 가르려면 실제 추출값이 필요하다. #147 이후 오탐이 보이면 그때 허용 목록으로 좁힌다 |
| 14 | Important | `src/cheongyak_extract/normalize.py:56` | 문장에 `N세대`가 하나뿐이면 무엇을 가리키든 그 숫자를 공급규모로 읽는다 (`취소 614세대` → `614`) | push-back — plan이 `총 358세대` → `358`을 정했다. 어느 숫자가 공급규모인지는 추출(#147)이 정하는 일이고 `reports/normalize.md`도 그렇게 적고 있다 |
| 15 | Important | `src/cheongyak_extract/normalize.py:50` | `주식회사`·`(주)`를 이름 어디서든 지워서 `(주)한국주식회사`와 `한국`이 같아진다 | won't-fix — 법인 표기는 이름 앞뒤에만 붙고 중간에 낀 실제 회사명은 이 3건에도 없다. 같아지는 방향이 한 군데뿐이라 오탐 위험도 낮다 |
| 16 | Important | `src/cheongyak_extract/measure.py:41` | 정답이 빈 쌍은 모의값이 비어 맞아도 일치로 세지 않고 분모에는 남는다. `report.metrics()`의 정의와 다르다 | defer — 지금 24쌍에는 정답이 빈 쌍이 없다. fixture에 그런 쌍이 들어오는 티켓에서 분모 처리를 정한다 |
| 17 | Important | `tests/test_report.py:78` | stub 테스트는 `EMPTY`(값 None)를 써서 `normalize`가 호출되기 전에 걸러진다. normalize 회귀로는 실패할 수 없다 | won't-fix — 통과 기준 5의 실제 검사는 `tests/test_pipeline.py:51`(전 필드 `accuracy == 0.0 and blank == 1.0`)이고 이미 `normalize`를 지나간다. 이 테스트는 보조라 두어도 해롭지 않다 |
| 18 | Important | `tests/test_report.py:11` | 빈 추출값 vs 정답 있음, 정답 없음 vs 추출값 있음을 `metrics()` 단에서 끝까지 확인하는 테스트가 없다 | push-back — `test_metrics_follow_design_definitions`가 이미 `blank`(`EMPTY`)와 `filled_empty`(정답 None + 값 있음)를 같이 센다 |
| 19 | Suggestion | `src/cheongyak_extract/normalize.py:30` | `_period`가 날짜 둘만 세고 `~`는 안 봐서 `2026.11.23, 2026.11.25`가 기간 `11-23~11-25`와 같아진다 | 기록만 |
| 20 | Suggestion | `src/cheongyak_extract/normalize.py:30` | 끝 연도를 생략한 기간(`2026.11.23~11.25`)은 못 읽어서 원본 비교로 떨어진다. 같은 값이 다르다고 나오는 방향이다 | 기록만 |
| 21 | Suggestion | `reports/normalize.md` | 24쌍이 3개 공고에서 나왔고 규칙도 같은 쌍에 맞춰 다듬었다. 23/24는 이 3건에서의 수치라는 설명이 리포트에 없다 | 기록만 |
| 22 | Suggestion | `src/cheongyak_extract/normalize.py:78` | 원본 `strip()`으로 떨어진 횟수를 세지 않아 「정규화가 몇 쌍에서 실제로 쓰였나」가 리포트에 안 나온다 | 기록만 |
| 23 | Suggestion | `src/cheongyak_extract/normalize.py:20` | 달력에 없는 날짜(`2026.13.45`)도 그대로 정규형이 된다 | 기록만 |
| 24 | Suggestion | `src/cheongyak_extract/measure.py:1` | 「24쌍」이 모듈 docstring·`--help`에 박혀 있어 fixture가 늘면 실제와 맞지 않게 된다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. 정확도 비교가 정답·추출값 양쪽을 정규화한 뒤 비교하고, 리포트·저장 값은 원본 그대로다 | 예 | `src/cheongyak_extract/report.py:64`, `tests/test_report.py:66` |
| 2. 모의 추출값 24쌍(3건 × 8필드)이 fixture에 있고, 각 값이 그 쪽 텍스트에 있다 | 예 (로컬). CI는 판정 불가 | `tests/fixtures/pdf_forms.json` 24칸. `tests/test_pdf_forms.py` 4 passed 로컬, CI에서는 `data/raw` 없어 skip (#12) |
| 3. `measure-normalize`가 정규화 전·후 일치 수를 나란히 출력하고 `reports/normalize.md`에 쓴다 | 예 | 재실행해도 `reports/normalize.md` 변화 없음. 정규화 전 3/24, 정규화 후 23/24, 안 맞는 쌍 1 |
| 4. 설계 §정규화 결과가 같아지면 안 되는 것 5개 경우가 테스트로 있고 통과한다 | 예 | `tests/test_normalize.py:68-84` |
| 5. stub `run --n 3`이 모든 필드 정확도 0%·빈 칸 100%다 | 예 (테스트로). `run --n 3` 실제 재실행은 안 함 | `tests/test_pipeline.py:51`, plan이 허용한 방식 |
| 6. `uv run pytest` 통과, GitHub Actions pytest green | 예 | 로컬 102 passed. fix push 뒤 head `b7f293d`의 CI run 40252399957 pytest pass |
| 실패 징후 1 — 일치 쌍 수, 정규화 전과 후 | 값만 적는다 | 전 3/24 → 후 23/24. plan이 짚은 「6 근처」보다 전 값이 낮다 |
| 실패 징후 2 — 모의값이 PDF 해당 쪽에 없으면 미완 | 판정하지 않는다 | 로컬 `test_every_value_is_on_its_page` 3 passed (쪽 범위 검사는 fix `727085c`에서 추가) |
| 실패 징후 3 — stub 정확도가 0%가 아니다 | 아니오 (0%가 아닌 필드 없음) | `tests/test_pipeline.py:51` |

## 메모

- 이 세션에서 만든 fix 11개 중 `b7f293d`는 지적이 아니라 위 fix가 늘린 긴 줄 2개를 ruff(100자)에 맞춘 것이다.
- 리뷰 후 로컬 `uv run pytest` 102 passed, `ruff check .` 통과.
- 인라인 스레드 8건 중 7건을 올렸다. 지적 18(`tests/test_report.py:11`)은 그 줄이 diff 밖(기존 줄)이라 GitHub이 422로 거부해 못 올렸다. 이유는 위 표에 있다.
