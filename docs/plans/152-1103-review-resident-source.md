# 152 리뷰 — PR #10

**대상:** `main...HEAD` — 33 commits(PR #9 위에서 시작해 이 PR이 더한 것 + 리뷰 fix 2), 24 files, +4307 −28. 이 리뷰는 PR #9 반려 뒤에 더해진 `7896f34..HEAD`(15 files, +1698 −197)를 봤다
**plan:** docs/plans/152-1103-plan-resident-source.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `tests/test_pdf_fields.py` | 거주지 호출과 두 필드 호출은 `blanked`를 합치는데, 깨진 응답 테스트는 두 호출을 한꺼번에 깨뜨려서 `blanked.update(more.blanked)`를 지워도 통과한다 | fix `e829f80` |
| 2 | Important | `tests/test_pdf_fields.py` | `_load`가 `split`을 안 받는 운영 경로(`pick_resident(eligible, 기존 50건)`, tune·test 분기, 칸 수)를 부르는 테스트가 없다. 기존 50건을 빼는 인자를 `first.test`만으로 바꿔도 통과한다 | fix `bde91a7` |
| 3 | Important | `src/cheongyak_extract/pdf_fields.py:231` | 묶음이 쪽 맨 아래까지 이어지면 거기서 잘리고 쪽 번호 줄(`- 20 -`)이 묶음에 들어간다. 실제 `data/raw`에서 2026000270(20쪽)·2026000310(21쪽) 둘. 다음 쪽에 이어지는 글이 있으면 LLM이 못 보고, 정답 `quote`가 다음 쪽이면 「묶음 밖」으로 걸린다 | defer — 고치면 묶음 프롬프트가 바뀌어 재는 30건 캐시가 달라진다. plan이 재는 30건을 한 번만 재고 그 뒤 프롬프트를 고치지 않게 했다. 2026000270은 재는 30건에 들어 있고 맞음이다. 후속에서 묶음 찾기를 확장할 때 같이 본다 |
| 4 | Important | `src/cheongyak_extract/pdf_fields.py:227` | 「2순위 : ①지역」 줄이 쪽 맨 아래에 있고 「■ ①지역」이 다음 쪽에 있으면 3줄 확인이 쪽 끝에서 멈춰 묶음이 None이 된다(리뷰 에이전트가 2026000454를 예로 들었고 다음 쪽 「■」는 확인 못 함). 그 공고는 `전체` 출처로 간다 | defer — plan §이번에 안 하는 것 「묶음을 못 찾는 공고의 꼴을 코드로 더 찾는 것」이다. 못 찾은 공고는 `전체`로 따로 세고 있다(149건 중 24건) |
| 5 | Important | `src/cheongyak_extract/pdf_fields.py:716` | 거주지 호출이 성공한 뒤 두 필드 호출이 `ContextExceeded`·`BadResponse`로 실패하면 거주지 호출의 입력 토큰이 합계에서 빠지고, 이미 받은 거주지 결과도 공고째 버려진다 | defer — 이번 세 실행(다듬는 50건 2번, 재는 30건 1번)은 건너뛴 공고가 0건이다. 건너뛰면 종료 코드 1이라 조용하지 않다. 토큰 합계 과소만 남는다 |
| 6 | Important | `src/cheongyak_extract/pdf_fields.py:328` | 규칙 2·3 표시가 `note`의 부분 문자열이라 「공통 표 없음」 같은 부정문도 표시로 읽히고, 둘이 같이 있으면 규칙 2가 먼저 잡힌다. `reports/pdf-labels.md`의 규칙별 수가 note 글자에 달려 있다 | push-back — 정답 파일은 사람이 쓴 80칸이고 `note`는 `공통 표.`·`해당지역 우선 문장.`으로 시작하는 고정 꼴이다. 부정문은 지금 없다. 구조화된 칸을 새로 만들면 정답 파일 꼴이 바뀐다 |
| 7 | Suggestion | `src/cheongyak_extract/pdf_fields.py:466` | `render_labels` 제목이 「PDF에만 있는 필드 3개」인데 `labels/pdf-resident-30.json`에는 거주지만 있다. `render_eval` 제목(`:610`)도 test에서 「세 필드」로 나온다 | 기록만 — 이미 낸 리포트와 어긋나지 않게 그대로 둔 것이 PR 본문에 적혀 있다 |
| 8 | Suggestion | `src/cheongyak_extract/pdf_fields.py:33` | 「앞 20건이 다듬는 공고, 나머지 30건이 재는 공고」 주석이 옛 뜻이다. `--set tune`은 이제 기존 50건 전부이고 `--set test`는 새 30건이다. 「재는 공고」가 두 집합을 가리킨다 | 기록만 |
| 9 | Suggestion | `src/cheongyak_extract/pdf_fields.py:165` | `_ONE_REGION`이 지역 이름 없이 숫자만 있는 `30% / 70%`도 꼴이 맞다고 본다(`\S`가 숫자 한 글자를 먹는다). 현재 정답에는 없다 | 기록만 |
| 10 | Suggestion | `src/cheongyak_extract/pdf_fields.py:309` | 정답이 null인 거주지 칸은 그 공고에 묶음이 있어도 검사에 안 걸린다(2026000184는 묶음이 없는 공고라 해당 없음) | 기록만 |
| 11 | Suggestion | `src/cheongyak_extract/pdf_fields.py:697` | `last_usage`가 없는 ask는 토큰 0으로 세어진다. `resident_ask`를 안 주면 `ask`가 두 필드 스키마라 거주지 응답에 키가 없어 모든 공고가 건너뜀으로 센다(CLI는 항상 `resident_ask`를 준다) | 기록만 |
| 12 | Suggestion | `src/cheongyak_extract/__main__.py:105` | OpenAI 인증·한도 오류는 `except (ValueError, OSError, RuntimeError)`에 안 잡혀 트레이스백으로 멈추고 리포트가 안 써진다. 계획이 HARD 오류는 멈추라고 한 것과 맞다 | 기록만 |
| 13 | Suggestion | `tests/test_pdf_fields.py` | 변이 시험에서 살아남을 곳: 입력 토큰 합계의 `resident_ask is ask` 이중 계산, `_resident_rule`에서 표시 둘이 같이 있을 때, `표시 없음` 행, `only=0`·범위 밖 쪽, `해당지역 0%`의 `cell_state` | 기록만 |
| 14 | Suggestion | `README.md` | 「거주지 정답 80칸은 quote가 묶음 안에 있는지 확인한다」는 묶음이 있는 65칸에만 맞다. 없는 15칸은 `note`의 규칙 표시를 확인한다 | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/pdf_fields.py:1` | 모듈 docstring이 `labels/pdf-only-50.json`과 1031 설계만 가리킨다. `labels/pdf-resident-30.json`·1103 설계가 없다. `build_prompt`의 `only` 설명이 `extract_rules`·`extract` docstring에 없다 | 기록만 |
| 16 | Suggestion | PR #10 본문 | 본문 맨 위 「병합 충돌 (Actions 미실행)」이 옛 상태다. jw가 `93211a8`로 main을 머지해 충돌이 풀렸고 `gh pr checks`는 pytest pass다. plan의 「base 브랜치를 merge·rebase하지 않았다」는 그 머지 커밋 전까지의 일이다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. 일반공급 ①지역 묶음 찾기: 다자녀·노부모·일반공급이 다 있으면 일반공급, 「■ ①지역」만 있는 줄 다음 줄까지, 띄어쓰기, 「2순위」 없으면 None | 예 | `pdf_fields.py:217` · `tests/test_pdf_fields.py` resident_block 테스트 |
| 1. `reports/pdf-labels.md`에 149건 중 묶음 찾은 수 | 예 | 125건 (`reports/pdf-labels.md`) · 설계 착수 때 센 값과 같다 |
| 2. 정규형에서 0%를 뺀다, 합이 100이 아닌 값을 알아보는 함수 | 예 | `pdf_fields.py:154,160` · `sum_is_not_100` 테스트 |
| 3. 거주지 정답 검사: 묶음 안 quote, 꼴, 합 100, 기존 검사 둘 | 예 | `_resident_problems` · 정답 80칸 검사에 걸린 칸 0 |
| 4. 묶음이 있으면 묶음만, 없으면 전체와 규칙 2·3, 결과마다 `출처` | 예 | `_extract_notice` · 프롬프트 내용 테스트 · 새 30건 `묶음` 25 `전체` 5 |
| 4. 전매제한·신혼부부는 두 필드 묶음으로 전체 텍스트를 한 번에 | 예 | `TWO_FIELD_SET` · 호출 개수 테스트 |
| 4. 8필드 프롬프트·`OUTPUT_SCHEMA` 그대로, `prompt.sha256` 다시 안 만듦 | 예 | `tests/fixtures` diff 0줄 · `tests/test_llm_replay.py` 통과 |
| 5. `labels/pdf-only-50.json` 거주지 50칸을 새 검사로 고치고 `note`에 이유 | 예 | 거주지 9칸 변경(값이 바뀐 3칸은 note에 이유) · 전매제한·신혼부부 칸 변경 0 |
| 5. `labels/pdf-resident-30.json` 형태, 코드가 다시 뽑은 목록과 대조 | 예 | `check_labels` · `pick_resident` · 이번 리뷰의 fix `bde91a7` 테스트 |
| 6. `eval-pdf --set tune`(50건 세 필드)·`--set test`(새 30건 거주지) | 예 | `__main__.py:105-112` · `tests/test_main.py` |
| 6. 리포트에 `출처`별 수, 맞지 않은 칸 표에 정답 쪽·LLM 쪽·`출처`·합 100 아님 | 예 | `reports/pdf-resident-test.md` 표 머리 |
| 7. 리포트 3개, PR #9 리포트는 그대로 | 예 | `reports/pdf-labels.md` · `pdf-fields-tune-2.md` · `pdf-resident-test.md` · `pdf-fields-tune.md`·`pdf-fields-test.md` diff 없음 |
| 8. README에 거주지 고르는 규칙, 새 명령 사용법, 결과 한 줄, PR #9 줄은 「반려된 첫 시도」 | 예 | `README.md` · 수치가 리포트 셋과 일치(29/30, 48/49, 125/149, 65/6/8) |
| 9. `uv run pytest` 통과, `uv run ruff check` 통과, Actions green | 예 | 557 passed · `All checks passed!` · `gh pr checks 10` pytest pass |
| 9. 테스트가 `data/raw`를 읽지 않고 OpenAI를 부르지 않는다 | 예 | 새 테스트는 `tmp_path`·가짜 ask·`monkeypatch`만 쓴다 |
| 실패 징후 1. 새 30건 거주지 다른 값 0 / 비움 3 이하 / 정답 검사 걸린 칸 0 | 값만 적는다 | 다른 값 1, 비움 0, 정답 검사에 걸린 거주지 80칸 중 0 (`reports/pdf-resident-test.md`, `reports/pdf-labels.md`) |
| 실패 징후 2. `출처`별 결과 | 값만 적는다 | `묶음` 25칸 중 맞음 25, `전체` 5칸 중 맞음 4 |
| 실패 징후 3. 전매제한·신혼부부가 PR #9와 달라졌나 | 값만 적는다 | 기존 50건: 전매제한 47/47, 신혼부부 42/46 (`reports/pdf-fields-tune-2.md`). PR #9 합계(47/47, 40/46)와 비교는 PR 본문에 있다 |
| 실패 징후 4. 순서 (a) 정답 파일 < 재는 리포트 (b) 프롬프트 고정 < 재는 리포트 | 예 | 정답 `97f0a30` 11:05 < 재는 리포트 `e1f8aa2` 11:14, 프롬프트 `8e357d4` 11:11·고정 기록 `d6901f4` 11:13 < `e1f8aa2` |
| 실패 징후 5. 다듬는 50건과 재는 30건의 거주지 맞음 비율 차이 | 값만 적는다 | 48/49(98.0%) 대 29/30(96.7%), 1.3%p |
| 이번에 안 하는 것(전매제한·신혼부부 정답 수정, 지역 이름 비교, 묶음 확장, 재는 30건을 보고 프롬프트 고치기, `run` 흐름) | 예 | `pdf-only-50.json`의 다른 필드 칸 diff 0 · 재는 리포트 뒤 `src/` 커밋 없음(리뷰 fix는 `tests/`만) |

## 게시 기록

- 이 리뷰는 `pr-review-toolkit:review-pr` 에이전트 넷(code-reviewer · pr-test-analyzer · silent-failure-hunter · comment-analyzer)과 직접 확인한 것(2026000502 정답을 PDF 36쪽에서 다시 읽어 `해당지역 100%`가 맞음을 확인, 커밋 순서, README 수치)으로 썼다.
- fix 2건은 둘 다 `tests/`만 바꿨다. `src/`가 안 바뀌어서 프롬프트·캐시·점수는 그대로다. 테스트는 fix 뒤 557 passed, ruff 통과.
- fix 뒤에 변이 시험 둘을 직접 돌렸다: `blanked.update(more.blanked)` 삭제와 `pick_resident` 제외 목록 축소. 둘 다 새 테스트가 실패한다.
- 요약 코멘트 1건과 인라인 스레드 4건(지적 3·4·5·6)을 HEAD `cdd80d8`에 올렸다. 실패 0건.
