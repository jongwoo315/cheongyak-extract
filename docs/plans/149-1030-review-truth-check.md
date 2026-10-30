# 149 리뷰 — PR #8

**대상:** `main...HEAD` — 15 commits(구현 8 + 리뷰 fix 7), 10 files(리뷰 파일 제외), +1877 −1
**plan:** docs/plans/149-1030-plan-truth-check.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `labels/pdf-values-20.json:452` | 2026000437·2026000438의 시공사·시행사 4칸은 `quote`가 값이 적힌 줄이 아니라 「구분 공공시행자 민간사업자 한국토지주택공사」여서 근거 검사(0칸)가 이 4칸의 값을 확인하지 못했다 | fix `49775e7` |
| 2 | Important | `src/cheongyak_extract/truth_check.py:79` | 근거 검사는 `quote`가 쪽 텍스트에 있는지만 보고 `value`가 `quote` 안에 있는지는 안 본다. 라벨에서 `value`를 잘못 적어도 「근거를 못 찾은 칸 0」으로 통과한다 | defer — `value ⊂ quote`를 강제하면 정정·표기 차이 칸(`2026000454` 준공월, `2026000314` 시공사 두 곳을 쉼표로 이은 값)이 거절된다. 어떤 필드에 어떻게 느슨하게 적용할지가 설계 결정이라 이 PR에서 정하지 않는다. 지금 160칸은 #1 수정 뒤 4칸만 남은 어긋남이 `2026000314` 시공사(표 줄을 `, `로 이은 값)와 `2026000436` 모집공고일(PDF 텍스트가 `(금입니다)`로 깨짐)이다 |
| 3 | Important | `src/cheongyak_extract/truth_check.py:138` | 다시 읽기는 추출기가 HTML과 다르게 채운 칸만 본다. 추출값이 HTML과 같고 PDF와 다른 칸(예: 2026000438·2026000437 공급위치, 쉼표 차이)은 어느 표에도 안 나와, 「LLM 6칸 중 4칸」을 읽을 때 PDF 기준 점수가 154+4=158이 아니라 157로 읽어야 하는 것이 리포트에 없다 | defer — 설계 §LLM·정규식 점수를 다시 읽는 표가 「정답과 다른 값으로 채운 칸」만 읽는다고 정했고 리포트 문구(`truth_check.py:210`)가 그 범위를 적는다. PDF 기준 전체 재채점은 이번에 안 하는 것(기존 점수 수정)과 맞닿아 있어 jw가 게이트에서 정한다 |
| 4 | Important | `src/cheongyak_extract/truth_check.py:127` | `llm_values`가 `splitlines()`로 줄을 나눠 `\r`·`\x0c`가 든 추출값이 첫 줄에서 끊기고, 추출값이 `\`로 끝나면 추출값·근거 열이 합쳐진다. 칸 집합 비교는 통과해 잘린 값이 조용히 「다름」으로 읽힌다 | fix `4a1a267` |
| 5 | Important | `src/cheongyak_extract/truth_check.py:61` | 라벨 파일 맨 위가 리스트이거나 공고 칸이 객체가 아니면 `AttributeError`·`TypeError` 트레이스백으로 죽어 CLI의 「대조할 수 없다」 메시지가 안 나온다 | fix `bb931c1` |
| 6 | Important | `tests/test_main.py:239` | `check-truth`의 종료 코드 1(근거를 못 찾은 칸 > 0) 경로와 요약 줄에 테스트가 없어 `return 0 if not bad else 1`이 `return 0`이 되어도 통과한다 | fix `24efef5` |
| 7 | Important | `tests/test_truth_check.py:282` | 틀리게 채운 칸 표에서 행이 빠지면 에러를 내는 방어선(`set(values) != wrong`)에 테스트가 없다 | fix `0781b7c` |
| 8 | Important | `tests/test_truth_check.py:240` | 정규식 쪽 다시 읽기(`regex_wrong` 구성과 「#150 정규식… 15칸」 표)를 끝까지 밟는 테스트가 없다. 픽스처의 정규식이 한 칸도 틀리지 않아 `got.regex`가 비어 있다 | defer — 실데이터 리포트에서는 정규식 15칸이 `reports/regex-new.md`의 15칸과 같은 값으로 나와 지금은 맞다. 정규식이 틀린 값을 내는 PDF fixture를 만들어야 해 이 PR 범위 밖의 테스트 추가라 후속으로 둔다 |
| 9 | Important | `src/cheongyak_extract/truth_check.py:229` | `run_check` 독스트링과 README가 라벨 파일·`data/raw/`만 읽는다고 적었는데 실제로는 `reports/extract-new.md`(대조할 공고 목록과 LLM 틀린 칸)도 읽는다. 없으면 명령이 실패한다 | fix `2cca558` |
| 10 | Important | `src/cheongyak_extract/truth_check.py:244` | 에러 메시지가 「C안 합계가 센 칸과 다르다」인데 이 줄이 비교하는 것은 같은 표를 두 방식(`llm_values`, `compare.parse_llm_new`)으로 읽은 결과다 | fix `043bca4` |
| 11 | Important | `src/cheongyak_extract/truth_check.py:210` | 리포트 소제목 「#147 LLM이 정답과 다른 값으로 채운 6칸」의 6은 `extract-new.md` C안 행의 값이고 README의 #147 행은 14칸이라 둘을 아는 독자는 어긋난 것으로 읽는다 | push-back — plan 통과 기준 3이 「#147 LLM이 정답과 다른 값으로 채운 6칸」이라고 문장째 적었고 README 109행이 이 6칸을 「LLM(C안)」이라고 설명한다. plan이 정한 표 이름을 바꾸는 것이라 이번 범위가 아니다 |
| 12 | Important | `docs/plans/149-1030-design-truth-check.md:34` | 설계가 PDF 값을 적는 동안 기존 리포트를 열지 않는다고 했는데 구현 루프가 `reports/extract-new.md` 맨 위를 `head`로 읽다가 「틀리게 채운 칸」 표 앞 4행의 HTML 정답을 봤다고 PR 본문이 스스로 적었다. 이 4행 중 2026000438·2026000437 시행사 두 칸이 다시 읽기 표의 「PDF 값과 다름」 2칸과 겹친다 | defer — 코드로 고칠 수 없는 절차 위반이다. 커밋 순서(`be10450` < `0f27a34`)와 그 사이 `value`·`quote`·`page` 변경 0은 확인했지만 눈가림이 아니었다는 것은 확인할 수 없다. #1에서 고친 quote로 이 두 칸을 PDF에서 직접 확인할 수 있다. 판정은 jw가 한다 |
| 13 | Suggestion | `src/cheongyak_extract/truth_check.py:81` | HTML 값과 PDF 값이 모두 `None`이면 `same`이 참이다. `parse_truth`가 필드를 못 찾게 바뀌고 라벨이 「PDF에 없음」이면 같은 칸으로 센다. 지금은 160칸 모두 HTML 값이 있어 영향 없음 | 기록만 |
| 14 | Suggestion | `src/cheongyak_extract/truth_check.py:77` | `check_cells` 안의 지역 변수 `pages`가 가져온 함수 `pages`를 가려 안에서 `pages(...)`를 부르면 `TypeError`가 난다. 지금은 영향 없음 | 기록만 |
| 15 | Suggestion | `src/cheongyak_extract/truth_check.py` | 라벨 JSON의 중복 키가 마지막 값으로 조용히 정해진다 · 실패한 실행이 이전 `reports/truth-check.md`를 그대로 남긴다 · `cause()`가 `same` 칸의 note나 `pdf=None`인 칸의 「표기 차이」를 검사하지 않는다 · 정규식 15칸이 `reports/regex-new.md`의 15와 같은지 대조하지 않는다 | 기록만 |
| 16 | Suggestion | `README.md:88` | 「`quote`(PDF 텍스트에서 글자 그대로)」는 코드(`grounded`가 공백·줄바꿈을 모두 지우고 비교)보다 엄격하게 읽힌다. 「그 쪽」은 「그 페이지」인데 앞에 가리키는 말이 없다 | 기록만 |
| 17 | Suggestion | `tests/test_truth_check.py:108` | `test_missing_notice_raises`는 이름과 달리 「라벨에 없는 공고」를 확인하고, `test_cell_count_must_match_expected`의 `match="0"`은 약하다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 통과 기준 1: `labels/pdf-values-20.json` 공고 20건 × 필드 8개 = 160칸, 칸마다 `value`·`quote`·`page`·`note` | 예 | `check_cells`가 칸 수 160·키 4개를 검사하고 `check-truth`가 `칸 160`으로 통과 · `49775e7` 뒤 재실행 출력 `정규화 뒤 같은 칸 155/160, 근거를 못 찾은 칸 0` |
| 통과 기준 1: 같지 않은 칸 `note` 첫머리에 원인 하나(표기 차이·정정·다른 값·PDF에 없음) | 예 | `reports/truth-check.md` 같지 않은 5칸 모두 원인 표시, 원인 미기재 행 없음 |
| 통과 기준 2: 칸 수 160이 아니거나 필드·공고가 빠지면 에러 | 예 | `tests/test_truth_check.py`의 칸 수·필드·공고 누락 테스트, 라벨 형태 `bb931c1` |
| 통과 기준 2: `quote` 근거를 `extract.grounded`·`pdf_text.pages`로 검사 | 예 | `truth_check.py:79` |
| 통과 기준 3: `check-truth`가 `reports/truth-check.md`를 쓰고 청약홈·OpenAI에 요청하지 않는다 | 예 | `tests/test_main.py:197` `no_network` 스파이 · 리포트가 `49775e7` 뒤 재실행 결과와 바이트 같음 |
| 통과 기준 3: 맨 위 n/160(%), 근거를 못 찾은 칸 수, 원인별 수, 참고 비율, 필드별 표, 같지 않은 칸 전부, LLM·정규식 다시 읽기 표와 합계 줄 | 예 | `reports/truth-check.md`에 모두 있음. LLM 6칸 중 4, 정규식 15칸 중 2 |
| 통과 기준 4: README에 사용법과 결과 한 줄 | 예 | `README.md:84`, `README.md:115` |
| 통과 기준 5: `uv run pytest`·`ruff check` 통과, Actions green, 테스트가 `data/raw/`를 읽지 않음 | 예 | 로컬 `414 passed`, `ruff check` 통과, `gh pr checks` pytest pass(리뷰 시작 시점), 테스트는 `tests/fixtures/`·`tmp_path`만 사용 |
| 실패 징후 1: 같은 칸 비율 | 판정 불가 | 값은 155/160(96.9%), 근거를 못 찾은 칸 0. plan 임계값이 144칸 이상이면 통과인데 이 값이 jw 기준에 걸리는지는 jw가 정한다 |
| 실패 징후 2: 같지 않은 칸 중 표기 차이 비율 | 판정 불가 | 5칸 중 3칸(60%). plan은 절반을 넘으면 PR 본문에 표를 적으라고 했고 PR 본문에 표가 있다 |
| 실패 징후 3: 라벨 첫 커밋이 첫 실데이터 리포트 커밋보다 앞 | 예 | 라벨 `be10450`(10:46) < 리포트 `0f27a34`(10:48). 둘 사이 `value`·`quote`·`page` 변경 0, `note` 5곳만 변경. 이 PR 본문이 적은 절차 위반은 #12 |
| 실패 징후 4: LLM·정규식 다시 읽기 | 판정 불가 | LLM 6칸 중 PDF 값과 같은 칸 4, 정규식 15칸 중 2. baseline 없음 — 값만 적는다 |
| 이번에 안 하는 것: eval 정답·기존 리포트·정규화 규칙 수정, 20건 밖 공고, LLM 호출 | 예 | `git diff --stat main...HEAD`에 `normalize.py`·기존 `reports/*` 변경 없음 |

fix 커밋 이후 테스트: `uv run pytest` 414 passed, `uv run ruff check` 통과. fix 이후 `check-truth`를 scratchpad로 다시 돌려 `reports/truth-check.md`와 바이트가 같음을 확인했다(155/160, 근거를 못 찾은 칸 0).
