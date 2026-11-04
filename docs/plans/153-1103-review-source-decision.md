# 153 리뷰 — PR #11

**대상:** `main...HEAD` — 18 commits(리뷰 전 9 + 리뷰 fix 9), 11 files, +1059 −13
**plan:** docs/plans/153-1103-plan-source-decision.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/truth_check.py:160` | 틀리게 채운 칸 표에 대조한 칸에 없는 행(필드 이름이 바뀐 행 등)이 있으면 `pick_cells`가 그 행을 말없이 버린다 | fix `0bdc3b2` |
| 2 | Important | `src/cheongyak_extract/truth_check.py:390` | 근거 줄을 못 찾은 칸이 있는데 jw가 판정을 끝내면 리포트가 방식별 합계를 그대로 쓴다 | fix `dec3c18` |
| 3 | Important | `docs/decision-source.md:4` | 「숫자는 모두 160칸에서 나왔다」가 틀렸다. 1절에 공고 29건, 3절에 150칸·30칸 숫자가 있다 | fix `98ff0fa` |
| 4 | Important | `src/cheongyak_extract/__main__.py:76` | `judge-source` 도움말이 HTML 값과 PDF 값만 비교하는 것처럼 적혀 있다. 실제는 LLM 값까지 세 값 중 하나라도 다른 칸이다 | fix `39dc1cb` |
| 5 | Important | `README.md:102` | 「다른 값을 적으면 에러다」가 코드의 에러 조건 세 가지(`jw` 값, 칸 목록·증거 값 변경, 같은 칸 중복)를 다 말하지 않는다 | fix `22eaf45` |
| 6 | Important | `README.md:100` | HTML 값과 PDF 값이 같은 시행사 2칸에 `HTML`을 적을 때와 `둘 다`를 적을 때 집계가 다르다는 설명이 없다 | fix `76896f2` |
| 7 | Important | `tests/test_truth_check.py:430` | `ungrounded_judge`에 `quote`는 있고 `page`가 없거나 0인 칸 테스트가 없다. `is not None` 검사를 지워도 테스트가 안 깨진다 | fix `572af1d` |
| 8 | Important | `tests/test_truth_check.py:361` | `load_judge` 형식 검사 테스트가 쪽 번호 bool·0·음수, 문자열이 아닌 `pbno`·`quote`, 객체가 아닌 칸을 안 다루고 에러 메시지도 안 본다 | fix `d4ba4c6` |
| 9 | Important | `tests/test_truth_check.py:558` | 판정을 다 채운 뒤 리포트 테스트가 전부 `PDF`로만 채워 「8/8」을 본다. 어떤 합계 계산에도 8/8이 나와 아무것도 증명하지 못한다 | fix `d302642` |
| 10 | Important | `src/cheongyak_extract/truth_check.py:253` | `ungrounded_judge`는 판정할 칸의 근거 줄만 본다. 세 값이 같은 칸의 근거 줄이 쪽에 없어도 `judge-source` 리포트는 그 칸을 「같은 칸」으로 세고 말하지 않는다 | push-back — plan 통과 기준 4가 근거 줄 검사 대상을 「판정할 칸의 `quote`」로 정했다. 같은 칸의 근거 줄은 `check-truth`가 이미 검사하고(`reports/truth-check.md`의 「근거를 그 쪽에서 못 찾은 칸: 0」) 이 PR은 그 범위를 바꾸지 않는다 |
| 11 | Suggestion | `src/cheongyak_extract/truth_check.py:253` | 근거 줄 검사가 `Cell.ungrounded`와 같은 `grounded` 호출을 다시 계산한다. 한쪽만 바뀌면 두 리포트가 어긋난다 | 기록만 |
| 12 | Suggestion | `src/cheongyak_extract/truth_check.py:248` | `missing_material`이 PDF에 정말 값이 없는 칸(`pdf=None`)도 재료가 빠졌다고 센다. 현재 데이터에는 그런 칸이 0이다 | 기록만 |
| 13 | Suggestion | `src/cheongyak_extract/truth_check.py:390` | `render_judge`가 안내 문구에 기본 판정 파일 경로를 고정해 쓴다. `--judge`로 다른 파일을 주면 리포트가 틀린 파일을 가리킨다 | 기록만 |
| 14 | Suggestion | `src/cheongyak_extract/truth_check.py:222` | `merge_judge` 에러가 값이 바뀐 뒤 어떻게 복구하는지 안 알려 준다(파일을 지우면 jw 판정이 사라진다) | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/truth_check.py:210` | `load_judge` 에러가 파일 이름을 안 말하고, JSON 객체의 중복 키(`"jw"`가 두 번)를 조용히 받는다 | 기록만 |
| 16 | Suggestion | `src/cheongyak_extract/truth_check.py:474` | 판정 파일 첫 생성이 `atomic`하지 않다. 쓰는 도중 끊기면 일부만 있는 파일이 남는다 | 기록만 |
| 17 | Suggestion | `src/cheongyak_extract/__main__.py:143` | 근거 줄을 못 찾아 종료 코드 1일 때 stderr에 이유 한 줄이 없다 | 기록만 |
| 18 | Suggestion | `tests/test_truth_check.py:420` | `merge_judge`의 칸 집합 불일치 테스트가 필드 이름만 보고, 파일에만 있는 칸과 고른 칸에만 있는 칸, `pbno`만 다른 칸을 가르지 않는다 | 기록만 |
| 19 | Suggestion | `tests/test_truth_check.py:582` | `match="다르다"`가 증거 값 변경 에러 메시지에도 있어 엉뚱한 이유로 통과할 수 있다 | 기록만 |
| 20 | Suggestion | `tests/test_main.py:67` | 근거 줄을 못 찾은 CLI 테스트가 종료 코드만 보고 출력된 요약 줄은 안 본다 | 기록만 |
| 21 | Suggestion | `docs/decision-source.md:36` | 3절의 47/47·49/48·42/46은 다듬는 공고(tune) 점수인데 리포트 표의 「기존 50건」에는 그 표시가 없다 | 기록만 |
| 22 | Suggestion | `src/cheongyak_extract/truth_check.py:1`, `src/cheongyak_extract/__main__.py:147` | 모듈 docstring이 `judge-source`를 안 말하고 예외 주석이 에러 경로 일부만 적었다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. `judge-source` 명령이 있다. 판정 파일이 없으면 만들고, 있으면 `jw` 칸을 덮어쓰지 않고 읽는다. 청약홈·OpenAI를 부르지 않는다 | 예 | `src/cheongyak_extract/__main__.py:143`, `truth_check.py:474`, `tests/test_main.py`(`make_client`·`make_ask`가 호출되면 실패), `tests/test_truth_check.py::test_run_judge_reads_the_filled_file_without_overwriting_it` |
| 2. 판정 파일에 들어가는 칸 = 세 값이 정규화 뒤 하나라도 다른 칸. LLM 값은 표에 있으면 그 값, 없으면 HTML 값 | 예 | `truth_check.py:160`, `tests/test_truth_check.py::test_pick_cells_*` 5개 |
| 3. 칸마다 `pbno`·`field`·`html`·`pdf`·`quote`·`page`·`llm`·`jw`·`jw_note`. `jw`는 넷 중 하나 또는 null, 그 밖은 에러 | 예 | `truth_check.py:157`·`:210`, `tests/test_truth_check.py::test_load_judge_*`, `labels/source-judge.json` 7칸 |
| 4. 판정할 칸의 `quote`를 `extract.grounded`로 본다. 없는 칸은 리포트에 적고 종료 코드 1 | 예 | `truth_check.py:253`, `__main__.py:156`, `tests/test_main.py::test_judge_source_exits_1_when_a_quote_is_not_found`, `reports/source-judge.md`의 「근거 줄을 그 쪽에서 못 찾은 칸: 0」 |
| 5. 리포트: 맨 위 가정, 같은 칸 수/160, 판정할 칸 수/160, 판정할 칸 표, `판정 전` 포함 jw 판정별 칸 수. `판정 전`이 있으면 방식별 합계를 쓰지 않고, 다 차면 방식별 칸 수를 쓴다 | 예 | `reports/source-judge.md:5-12`, `tests/test_truth_check.py::test_render_judge_*`, `test_run_judge_report_counts_mixed_verdicts_per_method` |
| 6. 「HTML에 없는 필드」 절: 전매제한 기간·거주지 우선 비율·신혼부부 소득 기준, 출처와 함께 | 예 | `reports/source-judge.md` 맨 아래 절, 47/47·49/48·30/29·46/42가 `reports/pdf-fields-tune-2.md:33-35`·`reports/pdf-resident-test.md:33`과 같음(문서 검토 에이전트가 원본과 대조) |
| 7. `docs/decision-source.md`: 세 결정의 사실과 출처, 결정마다 「고른 방식과 이유 (jw)」 칸을 비워 둔다 | 예 | `docs/decision-source.md`, 3절 숫자의 바탕 설명은 `98ff0fa`에서 바로잡음 |
| 8. README: `judge-source` 사용법과 jw가 판정 파일을 채우는 방법 한 단락 | 예 | `README.md:92-104` |
| 9. `uv run pytest`·`uv run ruff check` 통과, 새 테스트가 `data/raw`를 읽지 않음, 보존·잘못된 값·판정 전/후 테스트 포함 | 예 | `614 passed`, `All checks passed!`, 새 테스트는 `tmp_path`·`tests/fixtures/detail.html`·가짜 입력만 쓴다(코드 검토 에이전트도 확인) |
| 실패 징후 1. 판정할 칸 7칸이 착수 때 목록과 같고 재료가 빠지거나 근거 줄이 쪽에 없는 칸이 0 | 예 | 7칸 = 설계 §착수 때 확인한 사실 4의 7칸(`2026000443·437·438 공급위치`, `454 입주예정월`, `314 시공사`, `437·438 시행사`)과 같음. 재료가 빠진 칸 0, 근거 줄을 못 찾은 칸 0(`reports/source-judge.md:11-12`). 통과 구간 |
| 실패 징후 2. 판정할 칸이 160칸 중 몇 칸인지와 필드별 칸 수를 리포트에 적는다 | 예 | `reports/source-judge.md`: 판정할 칸 7/160, 「필드별 판정할 칸」 표 |
| 실패 징후 3. 「세 값이 모두 같은 칸」 수를 가정 문장 옆에 적는다 | 예 | `reports/source-judge.md:5`: 같은 칸 153/160 |
| Done: `labels/source-judge.json`의 `jw`·`jw_note`가 모두 null | 예 | 7칸 전부 null(`labels/source-judge.json`) |
| Done: `data/raw`·`data/llm/`·`.env`를 커밋하지 않았고 새 환경변수가 없다 | 예 | `git ls-files`에 `data/`·`.env` 없음, `git diff main...HEAD`에 `os.environ.get`·`os.getenv`·`process.env` 추가 줄 없음 |
| Done: 우위 숫자(HTML 쪽·PDF 쪽이 맞는 칸 수) | 판정 불가 | jw가 `jw` 칸을 채운 뒤 나오는 값이다. 지금 리포트는 `판정 전 7칸`이라 합계를 쓰지 않는다 |

테스트 재실행: fix 9개를 적용한 HEAD에서 `uv run pytest -q`는 `614 passed`, `uv run ruff check`와 `uv run ruff format --check`는 통과했다. 지적 10의 push-back은 이 파일 처리 칸의 이유와 같다.
