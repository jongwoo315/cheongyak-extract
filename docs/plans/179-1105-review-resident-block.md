# 179 리뷰 — PR #14

**대상:** `main...HEAD` — 13 commits(구현 8 + 리뷰 fix 5), 10 files(리뷰 파일 제외), +777 −146
**plan:** docs/plans/179-1105-plan-resident-block.md
**단어장:** `docs/concepts.md`의 `## 용어` 절에 「쓰지 말 말」 칸이 없어 단어장 검사를 건너뛰었다

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/pdf_fields.py:261` | `_ends_block`이 줄 처음의 머리 기호만 묶음 끝으로 본다. 줄 중간의 `■`(이전 코드는 `"■" in rest`로 끊었다)에서 안 끊겨 2026000293(재는 30건)의 묶음이 26줄에서 76줄로 늘었다. 17쪽에서 시작해 19쪽의 주택소유 판정 절까지 LLM에 간다. PR 본문은 늘어난 이유를 「쪽을 넘어 이어 가서」라고 적었는데 2026000310만 맞다. 늘어난 줄 바로 앞은 ` 주택을   ■ 다음 각 호의 …`이다 | defer — 고치면 재는 30건에 든 2026000293의 LLM 입력이 바뀌어, 한 번만 측정하기로 한 재는 30건 결과가 이 공고에서 달라진다. 이 세션은 OpenAI를 부르지 않는다. 다시 잴지는 jw가 게이트에서 정한다 |
| 2 | Important | `src/cheongyak_extract/pdf_fields.py:277` | 규칙 1 묶음은 길이 상한도 % 확인도 없다. 끝 줄(머리 기호 줄·`②` 줄)이 없으면 문서 끝까지 이어지고, ①지역 줄만 있고 %가 없어도 규칙 2·3으로 넘어가지 않는다 | defer — 1번과 같은 뿌리다. 길이 상한을 두면 묶음 모양이 바뀌어 149건 비교와 재는 30건을 다시 해야 한다. 149건 실측에서 늘어난 공고는 2건(2026000293·2026000310)이다 | <!-- style-exempt -->
| 3 | Important | `src/cheongyak_extract/pdf_fields.py:864` | 쪽을 넘는 묶음의 글을 ①지역 줄이 있는 쪽 하나에 몰아 넣는다. LLM이 다음 쪽 줄을 인용해도 근거 확인을 통과하고 쪽 번호는 근사값이다 | push-back — 설계 §설계 결정 1이 「묶음의 쪽 번호는 ①지역 줄이 있는 쪽」으로 정했다. 점수(`cell_state`)는 쪽을 비교하지 않는다 |
| 4 | Important | `src/cheongyak_extract/pdf_fields.py:62` | 프롬프트 문자열과 규칙 3 정규식이 모두 `_SENTENCE`다(`:293`에서 다시 묶인다). 지금은 `RESIDENT_SENTENCE_SET`이 먼저 만들어져서 동작하지만, 뒤에서 `_head(_SENTENCE, 1)`을 쓰면 정규식이 프롬프트에 들어간다 | fix `998b67d` |
| 5 | Important | `docs/concepts.md:16` | 「전체」 행이 `_extract_notice`의 `else`를 `pdf_fields.py:865`라고 적었다. 실제 `else`는 867줄이고 865줄은 규칙 1·2·3 가지다 | fix `72353c7` |
| 6 | Important | `src/cheongyak_extract/pdf_fields.py:297` | 규칙 2 docstring과 개념 표가 「줄 안에 %가 없는 제목은 건너뛴다」라고 썼는데 코드는 제목 줄이 아니라 20줄 전체에서 %를 찾는다 | fix `f375b9f` |
| 7 | Important | `tests/test_pdf_fields.py:726` | `QUOTE_OUTSIDE_BLOCK`을 규칙 2·3 묶음 글로 판정하는 테스트가 없었다. 규칙 2의 20줄이나 규칙 3의 두 줄이 바뀌어도 통과한다 | fix `fc4afe1` |
| 8 | Important | `tests/test_pdf_fields.py:751` | `sort=False` 텍스트에서 찾은 규칙(`WholeNotice.unsorted_rule`)을 리포트에 적는 경로가 테스트에 없다. `sort=False` 인자를 빼도, 열이 늘 「없음」이어도 통과한다 | fix `5c3d9a2` |
| 9 | Important | `src/cheongyak_extract/pdf_fields.py:314` | 규칙 3이 문서에서 처음 걸리는 문장을 쓰고 일반공급 절로 한정하지 않는다. 특별공급 절에 같은 문장이 먼저 있으면 그 문장이 묶음이 될 수 있다(리뷰 에이전트의 추정이고 실제 사례는 못 찾았다) | defer — 정답 파일의 규칙 3 칸 1개는 정답 quote가 묶음 안이고 검사에 걸린 칸은 규칙 1인 2026000116 하나뿐이다. 일반공급 한정은 규칙 조건을 늘리는 설계 결정이라 오탐 사례가 나오면 후속 티켓에서 다룬다 |
| 10 | Suggestion | `src/cheongyak_extract/pdf_fields.py:431` | 값이 null인 거주지 칸은 코드가 묶음을 찾았는지와 대조하지 않는다. 틀린 묶음과 맞는 null이 리포트에서 같아 보인다 | 기록만 |
| 11 | Suggestion | `src/cheongyak_extract/pdf_fields.py:296` | 규칙 2가 설계(다음 `■`에서 끊기)와 달리 평평한 20줄(빈 줄 포함)이다. PR 본문에 이유(2026000438)가 있고 설계 문서에는 어긋남 기록이 없다. 제목 정규식은 줄 처음에 고정되지 않고 `%`는 20줄 어디든 하나면 통과한다 | 기록만 |
| 12 | Suggestion | `src/cheongyak_extract/pdf_fields.py:331` | `rule_lines`가 센 값은 규칙이 실제로 맞추는 줄이 아니라 후보 줄이다(`②`가 든 ①지역 줄, `%` 없는 제목도 센다). 「줄은 있는데 못 찾았다」가 과하게 나올 수는 있어도 못 찾은 것을 숨기지는 않는다. 지금 남은 공고(2026000184)는 모두 0이다 | 기록만 |
| 13 | Suggestion | `src/cheongyak_extract/pdf_fields.py:313` | 규칙 3은 문장 줄과 다음 한 줄만 준다. 다음 줄 뒤에 지역별 %가 이어지면 LLM이 `해당지역 100%`로 답하고 검사(`number_problems` 면제)가 모두 통과한다 | 기록만 |
| 14 | Suggestion | `tests/test_pdf_fields.py:777` | 리포트 규칙별 칸 수 표 테스트에서 규칙 2·3 칸이 모두 0이라 두 행이 서로 바뀌어도 통과한다. 쪽을 넘는 묶음을 `_extract_notice`·`check_labels`까지 이어서 확인하는 테스트와 `_AREA_LINE`의 줄 중간 머리 기호 갈래, 규칙 3 정규식의 `있는 경우`·`거주자를` 갈래, `rule_lines`의 쪽 마지막 줄 문장 테스트도 없다 | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/pdf_fields.py:140` | 주석·도움말·상수 이름이 새 규칙 1·2·3 번호와 겹치는 옛 말을 쓴다: `RESIDENT_FULL_SET` 주석의 「규칙 2·3 순서」, `NO_RULE_NOTE`·`RULE_2_MARK`·`RULE_3_MARK`의 「묶음이 없는데 규칙 2·3 표시」. `_BELOW` 주석 「이 수 안에」 | 기록만 |
| 16 | Suggestion | `README.md:122` | 거주지 설명의 설계 링크가 #152 설계(`152-1103-design-resident-source.md`)를 가리킨다. 3줄 창·20줄·규칙 3 문장은 #179 설계에 있다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 통과 기준 1: 규칙 1이 설계 §설계 결정 1의 꼴(`[ ①지역` 순위 줄·머리 기호 없는 줄·쪽 넘는 줄·쪽 넘어 이어지는 묶음)을 받고 꼴마다 테스트가 있다 | 예 | `tests/test_pdf_fields.py` 규칙 1 꼴별 테스트(테스트 분석 에이전트가 4꼴 모두 확인), `uv run pytest` 673 passed |
| 통과 기준 2: 규칙 2·3 묶음과 `Block.rule`, 안내 문장은 규칙 2 제목이 아니다, 규칙마다 테스트 | 예 | `src/cheongyak_extract/pdf_fields.py:296`·`:308`, `Block.rule`(`:245`), 규칙 2·3·안내 문장 테스트 |
| 통과 기준 3: 지금 찾는 125건은 계속 규칙 1이고 쪽 번호가 안 바뀐다. 끝이 늘어난 공고는 따로 센다 | 예 | 이전 코드(main)와 149건을 다시 비교: 규칙·쪽이 바뀐 공고 0건, 묶음 글이 달라진 공고 2건(2026000293 26→76줄, 2026000310). 위 1번 참고 |
| 통과 기준 4: 거주지 LLM 질문은 묶음 규칙마다 설명을 따로 쓰고, 세 규칙 다 못 찾으면 PDF 전체를 넘긴다 | 예 | `_BLOCK_SETS`(`pdf_fields.py:526`), `RESIDENT_FULL_SET`, `_extract_notice` `else`(`:867`), 규칙별 FieldSet 선택 테스트 |
| 통과 기준 5: `check-pdf-labels`를 다시 돌려 `reports/pdf-labels.md`를 고친다. 규칙별 칸 수는 코드가 고른 규칙 기준 | 예 | `reports/pdf-labels.md`의 「코드가 고른 규칙」 표 |
| 통과 기준 6: `eval-pdf` 두 번으로 두 리포트를 고치고 출처 표가 `묶음(규칙 1)`·`묶음(규칙 2)`·`묶음(규칙 3)`·`전체`로 나뉜다 | 예 | `reports/pdf-fields-tune-2.md`·`reports/pdf-resident-test.md`. 리포트 숫자와 README 숫자가 서로 같다(주석 분석 에이전트가 대조). OpenAI를 다시 부르지 않아 숫자 자체는 다시 재지 않았다 |
| 통과 기준 7: `docs/concepts.md` 규칙 1·2·3 표, README의 거주지 설명·숫자 | 예 | `docs/concepts.md`, `README.md:121-164`. 줄 번호 오류 1곳은 `72353c7`로 고쳤다 |
| 통과 기준 8: pytest·ruff 통과, 새 테스트가 `data/raw`를 안 읽는다 | 예 | `uv run pytest` 673 passed, `uv run ruff check`·`ruff format --check` 통과(리뷰 fix 후). 새 테스트는 `tmp_path`와 가짜 PDF만 쓴다 |
| 실패 징후 1: PDF 전체를 넘기는 공고 수(통과 0 / 다시 잰다 1~2 / 미완 3 이상) | 값만 적음 | `reports/pdf-labels.md`: 1건(2026000184), 줄 점검은 순위 줄 0 · ①지역 줄 0 · 제목 줄 0 · 문장 0이고 `sort=False`에서도 못 찾음. 구간 판정은 사람 몫 |
| 실패 징후 2: `QUOTE_OUTSIDE_BLOCK` 칸 수(정상 0 / 다시 본다 1~2 / 미완 3 이상) | 값만 적음 | `reports/pdf-labels.md`: 1칸(2026000116, 묶음 25쪽·규칙 1, 정답 근거는 같은 쪽 규칙 3 문장) |
| 실패 징후 3: 거주지 맞은 칸(정상: 다듬는 48 이상·재는 29 이상) | 값만 적음 | `reports/pdf-fields-tune-2.md` 49/49, `reports/pdf-resident-test.md` 30/30. 다만 2026000293의 입력은 위 1번처럼 이전 코드보다 길었다 |
| Done criteria: 정답 파일을 안 바꿨다 | 예 | `git diff main -- labels/` 0줄 |

## 처리 결과

- 리뷰 fix 5건(4·5·6·7·8번)을 각각 커밋했다. 마지막에 `uv run pytest` 673 passed, `ruff check`·`ruff format --check` 통과
- 4·5·6번 fix 뒤에도 `pdf_fields.py`의 줄 수는 같다(주석·이름·docstring 한 줄 교체). 그래서 `docs/concepts.md`의 나머지 줄 번호(`:265`·`:296`·`:308`)는 그대로 맞다
- OpenAI와 청약홈은 부르지 않았다. 이 세션의 측정은 `rtk` 없이 이전·이후 `resident_block`을 149건에 돌린 것뿐이다
