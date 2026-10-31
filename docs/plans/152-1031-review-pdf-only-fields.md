# 152 리뷰 — PR #9

**대상:** `main...HEAD` — 15 commits(구현 10 + 리뷰 fix 5), 18 files, +2754 −27
**plan:** docs/plans/152-1031-plan-pdf-only-fields.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/pdf_fields.py:132` | 전매제한 정답 검사가 `6개월`이 `36개월` 안에, `3년`이 `2023년` 안에 있는 것도 통과시킨다(앞 숫자 경계가 없다). 코드리뷰·테스트·silent-failure 에이전트 셋이 같은 지적 | fix `e75cbb9` |
| 2 | Important | `src/cheongyak_extract/pdf_fields.py:436` | LLM 응답이 JSON이 아니거나 키·칸 모양이 틀리면 칸이 전부 빈 값이 되고, 정답이 null인 칸에서는 「null에 비움」(맞음)으로 세어져 점수가 오른다. 이유도 리포트에 안 나온다 | fix `6266a30` |
| 3 | Important | `tests/test_pdf_fields.py` | `ContextExceeded` 건너뛰기 분기에 테스트가 없다(분기를 바꿔도 통과) | fix `b024d42` |
| 4 | Important | `tests/test_pdf_fields.py` | 입력 토큰 합계가 공고마다 더해지는지 보는 테스트가 없다(`+=`를 `=`로 바꿔도 통과) | fix `9892bac` |
| 5 | Important | `tests/test_pdf_fields.py` | 「값과 근거가 쪽에 없어 비움」 경로와 리포트의 비운 이유 칸을 보는 테스트가 없다 | fix `ecac9b1` |
| 6 | Important | `src/cheongyak_extract/extract.py:239` | 기본 C안은 값 글자가 그 쪽 어딘가에 있으면 근거가 지어낸 문장이어도 값을 남긴다(`3년` 같은 짧은 값은 거의 늘 쪽에 있다) | push-back — plan 통과 기준 3이 값을 남기는 조건을 C안으로 정했다. A·B안으로 바꾸면 8필드와 비교가 안 된다. 근거 문장의 원문 일치율은 리포트 「LLM 근거」 열로 사람이 볼 수 있다 |
| 7 | Important | `src/cheongyak_extract/pdf_fields.py:111` | 거주지 우선 비율·신혼부부 소득 기준의 정규형이 숫자만 비교해서 지역 이름이 바뀌어도(`경기도 30% / 평택시 20%` 대 `평택시 30% / 경기도 20%`) 맞음으로 센다 | won't-fix — 설계 §필드 3개의 뜻 표가 「지역 이름은 비교하지 않는다」로 정했다. 순서 바뀜은 PR 본문 10칸 확인이 맡는다 |
| 8 | Important | `src/cheongyak_extract/pdf_fields.py:358` | 건너뛴 공고가 있으면 맞음 비율의 분모가 줄지만 리포트 맨 위에 「30건 중 N건 잰」이 없다(맨 아래 절에만 나온다) | defer — 이번 재는 30건·다듬는 20건 모두 건너뛴 공고 0건이라 영향이 없다. 건너뛰면 종료 코드 1이다. 맨 위 표기는 후속 |
| 9 | Important | `src/cheongyak_extract/pdf_fields.py:264` | `split=None`인 운영 경로(`scan`→`has_text`→`pick`→정답 파일 대조)를 부르는 테스트가 없다 | defer — 리뷰 때 실제 `data/raw` 149건으로 `pick()` 결과가 정답 파일의 tune·test와 같고 `check-pdf-labels`가 150칸 0건임을 직접 돌려 확인했다. 단위 테스트는 후속 |
| 10 | Suggestion | `src/cheongyak_extract/pdf_fields.py:291` | 「검사 둘」 문구인데 코드는 정규형을 못 만드는 칸(`NO_NORMAL_FORM`)까지 세어 검사가 셋이다. README·리포트·docstring 5곳 | 기록만 |
| 11 | Suggestion | `src/cheongyak_extract/pdf_fields.py:86` | 쉼표 없이 `6개월 / 3년`처럼 이은 값은 `_months`가 42로 더한다 | 기록만 |
| 12 | Suggestion | `src/cheongyak_extract/pdf_text.py:29` | `has_text` docstring 「첫 쪽을 찾으면 멈춘다」가 1쪽으로 읽힌다(코드는 글자 있는 첫 쪽) | 기록만 |
| 13 | Suggestion | `src/cheongyak_extract/pdf_fields.py:33` | `PDF_HEAD`의 「숫자는 모두 evidence 안에」와 `해당지역 100%` 약속이 어긋난다. 고정한 프롬프트라 고치지 않는다 | 기록만 |
| 14 | Suggestion | `src/cheongyak_extract/llm.py:49` | 캐시 키가 `model + prompt`뿐이라 같은 프롬프트에 다른 스키마를 주면 옛 응답을 돌려준다. 지금은 필드 이름이 프롬프트에 있어 충돌 없다 | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/pdf_fields.py:444` | 입력 토큰 합계에 캐시 적중 호출도 포함된다 | 기록만 |
| 16 | Suggestion | `tests/test_pdf_fields.py` | 변이 시험에서 살아남은 8곳(`isinstance(page, bool)`, `cell_state`의 `want is not None`, 세 필드 프롬프트 해시 없음, CLI 오류 분기 등) | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. `labels/pdf-only-50.json` 공고 50건 × 필드 3개 = 150칸, tune 20·test 30이 코드가 다시 뽑은 것과 같다 | 예 | `check-pdf-labels` 150칸 · 실제 `data/raw` 149건에서 `pick()`과 정답 파일의 tune·test 일치 확인 |
| 1. 값이 null인 칸은 `note`에 찾아본 쪽을 적는다 | 예 | `_check_cell` 검사 · `reports/pdf-labels.md` null 8칸 note |
| 2. 칸 150개가 아니거나 공고·필드가 빠지면 에러 | 예 | `pdf_fields.py:check_labels` · `tests/test_pdf_fields.py` 구조 오류 파라미터 테스트 |
| 2. 값이 있는 칸마다 quote가 그 쪽에 있다, 정규형 숫자가 quote에 있다 | 예 | 정답 검사에 걸린 칸 0 (fix `e75cbb9` 뒤에도 같다) |
| 2. 정규형 함수 셋은 설계 표 그대로, `normalize.py` 기존 함수는 바꾸지 않는다 | 예 | `git diff main...HEAD -- src/cheongyak_extract/normalize.py` 0줄 |
| 3. 8필드 프롬프트·`OUTPUT_SCHEMA` 그대로, `prompt.sha256` 다시 안 만듦 | 예 | `tests/fixtures` diff 0줄 · `tests/test_llm_replay.py` 통과 |
| 3. 값을 남기는 조건은 C안 | 예 | `pdf_fields.py:436` 기본 rule · 지적 6 참조 |
| 4. `eval-pdf --set tune|test --out`, 청약홈 요청 없음, 캐시 `data/llm/` | 예 | `__main__.py` · 캐시로 두 집합 재실행해 리포트가 커밋본과 같음(test) |
| 4. 리포트 맨 위 칸 상태 수와 %, 필드별 네 수, 맞지 않은 칸 전부, 입력 토큰 합계 | 예 | `reports/pdf-fields-test.md` · `render_eval` 테스트 |
| 5. 리포트 3개 | 예 | `reports/pdf-labels.md` · `pdf-fields-tune.md` · `pdf-fields-test.md` 존재 |
| 6. README에 `eval-pdf` 사용법, 필드 뜻, 결과 한 줄 | 예 | README 수치가 두 리포트와 일치(재는 30건 88칸 중 맞음 75, 비움 7, 다른 값 6) |
| 7. `uv run pytest` 통과, `ruff check` 통과 | 예 | 505 passed · `All checks passed!` |
| 7. GitHub Actions pytest green | 예 | 리뷰 fix push 뒤 HEAD `ee32d44`에서 `gh pr checks` pytest pass |
| 7. 테스트가 `data/raw`를 읽지 않고 OpenAI를 부르지 않는다 | 예 | 새 테스트는 `tmp_path`·가짜 ask만 쓴다 |
| 실패 징후 3. 커밋 순서 (a) 정답 파일 < tune 리포트, (b) 고정 프롬프트 < test 리포트 | 예 | 정답 `f60a43e` < tune `a4a88e0`(고정 프롬프트 포함) < test `c385356` |
| 실패 징후 1. 재는 30건 90칸의 점수와 필드별 표 | 값만 적는다 | 맞음 75 / 비움 7 / 다른 값 6, null 2칸 중 비움 2 (`reports/pdf-fields-test.md`) |
| 이번에 안 하는 것(8필드 프롬프트·`normalize.py`·기존 리포트 수정, `run` 흐름 변경) | 예 | `git diff main...HEAD --stat`에 해당 파일 없음. `__main__.py`는 하위 명령만 추가 |
