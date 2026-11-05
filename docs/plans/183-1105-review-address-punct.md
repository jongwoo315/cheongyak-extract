# 183 리뷰 — PR #12

**대상:** `main...HEAD` — 7 commits, 15 files, +567 −86
**plan:** docs/plans/183-1105-plan-address-punct.md

단어장 없음 (repo에 `docs/concepts.md`가 없어 단어장 검사를 건너뛰었다).

리뷰 방식: `pr-review-toolkit:review-pr` 하위 에이전트 4개(code-reviewer · pr-test-analyzer · comment-analyzer · silent-failure-hunter)가 diff를 읽었다. 같은 지적은 한 행으로 합쳤다.

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/truth_check.py:285` | 정규화로 빠진 칸의 jw 판정이 `둘 다`가 아니어도(`HTML`·`PDF`·`둘 다 아님`) 같은 칸으로 세어 방식별 합계가 jw 판정과 조용히 어긋난다. 지금 파일의 빠진 칸 3개는 모두 `둘 다`라 숫자(159/160)는 맞다 | fix `b25e43a` |
| 2 | Important | `src/cheongyak_extract/__main__.py:154` | 빠진 칸 중 jw가 안 본 칸(`판정 전`)이 CLI 한 줄의 `판정 전` 개수에 안 들어간다 | push-back — 빠진 칸은 정규화로 세 값이 같아진 칸이라 판정할 대상이 아니다. 리포트의 빠진 칸 절에는 `판정 전`으로 표시되고(`test_render_judge_shows_a_dropped_cell_without_jw_as_pending`), 합계를 막는 `판정 전` 배너는 판정할 칸 기준이어야 한다. 정규화가 과하게 합쳤을 때의 위험은 #1 fix가 jw 판정이 있는 쪽을 막는다 |
| 3 | Suggestion | `src/cheongyak_extract/truth_check.py:562` | 판정 파일이 없을 때 쓰는 쓰기가 `atomic`하지 않다(쓰는 도중 끊기면 잘린 JSON이 남는다) | won't-fix — 이 PR이 바꾼 줄이 아니고 혼자 쓰는 CLI다. 잘린 파일은 다음 실행이 `JSONDecodeError`로 멈춰 조용히 넘어가지 않는다 |
| 4 | Suggestion | `reports/regex-vs-llm.md:3` | 정규식 숫자는 새 정규화, LLM 숫자는 이전 정규화 기준이라 리포트만 읽으면 공급위치 18 대 18, 「정규식 맞음 LLM 틀림 2」가 섞여 읽힌다. 이 사실은 README와 `docs/decision-source.md`에만 있다 | defer — LLM 리포트를 다시 만들지 않는 것이 plan의 이번에 안 하는 것이고, 이 리포트의 머리말은 `compare` 코드가 만든다. 리포트 머리말에 한 줄 더하는 것은 #183 밖의 `compare` 수정이라 후속에서 다룬다 |
| 5 | Suggestion | `src/cheongyak_extract/truth_check.py:249` | `merge_judge`만 따로 부르면 파일에 있는데 안 고른 칸을 말없이 무시한다. 두 함수가 `run_judge`에서 같이 불릴 때만 맞다 | 기록만 (docstring이 `dropped_judge`가 따로 다룬다고 적고 있다) |
| 6 | Suggestion | `tests/test_truth_check.py:688` | 빠진 칸 렌더 테스트가 `판정 전` 배너와 `pending`에서 빠진 칸이 제외됨을 `assert`하지 않는다 | 기록만 |
| 7 | Suggestion | `tests/test_truth_check.py` | `run_judge` 수준에서 「파일의 필드 이름이 바뀐 행」 에러를 확인하는 테스트가 없다(단위 테스트만 있다) | 기록만 |
| 8 | Suggestion | `tests/test_normalize.py:84` | 전각 괄호·쉼표(`（），`)와 NBSP를 다루지 않는다. 지금 데이터에 없고 plan은 반각 `(`·`)`·`,`만 정했다 | 기록만 |
| 9 | Suggestion | `docs/decisions.md:14` | #149·#150·#153 행의 지난 숫자(155/5, 111/15, 153/7)가 다시 만든 리포트와 다르다 | 기록만 (plan이 지난 행은 고치지 않는다고 정했다) |
| 10 | Suggestion | `README.md:102` | 에러 목록에 「파일의 칸이 이번에 대조한 칸에 없음」이 빠져 있다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. `normalize("공급위치", v)`가 `(`·`)`·`,`를 공백으로 바꾼 뒤 공백을 한 칸으로 줄인다. 다른 종류의 규칙은 바뀌지 않는다 | 예 | `src/cheongyak_extract/normalize.py:59-62`, 커밋 `8831baa`. 바뀐 줄은 `_address` 하나 |
| 2. 설계 표 세 쌍이 같은 값이 된다. `test_neighboring_blocks_in_one_address_stay_different`는 그대로 통과한다 | 예 | `tests/test_normalize.py` 세 쌍 parametrize, 기존 AC3·AC4 테스트 변경 없음, `uv run pytest` 642 passed |
| 3. 빠진 칸은 파일에 그대로 두고 리포트에 적는다. 새 칸·값 바뀜은 에러다 | 예 | `truth_check.py:260-285`(`dropped_judge`), `tests/test_truth_check.py`의 `test_run_judge_keeps_a_filed_cell_that_became_the_same_and_reports_it`·`..._raises_on_a_picked_cell_the_file_does_not_have`·`..._raises_when_a_dropped_cell_value_changed` |
| 4. `labels/source-judge.json`이 바뀌지 않는다 | 예 | `git diff main -- labels/source-judge.json` 0줄 |
| 5. 설계 표의 리포트를 OpenAI·청약홈 없이 다시 만들어 커밋한다. LLM 리포트는 다시 만들지 않는다 | 예 | 커밋 `0f73e8b`: `reports/{truth-check,source-judge,regex-new,regex-vs-llm}.md` 변경, `extract-*.md` 변경 없음(`git diff --stat main...HEAD`). `regex-tune`·`regex-more`·`normalize` 리포트는 변경 목록에 없다(설계 표에서 「모름」·「그대로일 것」으로 둔 것이며, 값이 안 바뀌어 파일 변경이 없는지는 PR 본문 표에서 확인할 일) |
| 6. `uv run pytest` 통과, `uv run ruff check` 통과. 새 테스트는 `data/raw`를 읽지 않는다. 세 경우를 각각 테스트한다 | 예 | pytest 642 passed(fix 뒤), ruff check · format 통과. 새 테스트는 `tmp_path`·인라인 값만 쓴다(test-analyzer 확인) |
| 실패 징후 2: 판정할 칸 4, 빠진 칸 3, 방식별 합계 HTML 159/160·PDF 159/160 | 예 | `judge-source` 실행 출력 `판정할 칸 4/160, 정규화로 빠진 칸 3, 판정 전 0`. `reports/source-judge.md`에 159/160 두 줄 |
| 실패 징후 1: 설계 표 세 칸이 같은 칸, 공급위치 20/20 | 예 | `reports/truth-check.md` 「공급위치 \| 20 \| 20」, 정규화 뒤 같은 칸 158/160. 다름에서 같음으로 바뀐 칸이 쉼표·괄호·공백만 다른지는 값 비교(사람 판정)라 여기서 판정하지 않는다 |

## 확인한 것

- fix 뒤 `timeout 120 uv run python -m cheongyak_extract judge-source --out /tmp/x183.md`: EXIT 0, `판정할 칸 4/160, 정규화로 빠진 칸 3, 판정 전 0`. `labels/source-judge.json` 변경 없음.
- 새 환경변수(`os.environ.get`·`os.getenv`)는 추가되지 않았다.
- plan 징후 3·PR 본문의 숫자 표는 이 리뷰에서 다시 재지 않았다. comment-analyzer가 README·`docs/decision-source.md`의 숫자를 리포트와 대조해 일치함을 확인했다.
