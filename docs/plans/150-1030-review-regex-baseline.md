# 150 리뷰 — PR #7

**대상:** `main...HEAD` — 12 commits(리뷰 전 8 + 리뷰 fix 4), 17 files, +1317 −12
**plan:** docs/plans/150-1029-plan-regex-baseline.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/compare.py:main` | 다듬는 29건은 LLM 칸 수와 정규식 칸 수를 대조하지 않아, LLM이 건너뛴 공고가 있어도 서로 다른 공고 묶음을 비교한 채 표가 나온다 | fix `374f025` |
| 2 | Important | `tests/test_compare.py` | 칸 수 대조(`_same_cells`)와 공고 목록 읽기(`parse_pbnos`)를 확인하는 테스트가 없다 | fix `374f025` · `bf77415` |
| 3 | Suggestion | `src/cheongyak_extract/compare.py:parse_pbnos` | 리포트가 `--text T0 T1`이면 한 공고가 처리 목록과 건너뛴 목록에 둘 다 올라 두 번 세어질 수 있다. `_same`이 어긋남은 잡는다 | fix `bf77415` (2번과 같은 커밋에서 같이 고침) |
| 4 | Important | `src/cheongyak_extract/regex_extract.py:3` | 모듈 설명이 「표의 몇 번째 칸인지 세지 않는다」, 「첫 번째로 걸린 줄」이라고 하는데 시행사·시공사는 상호 줄을 칸으로 나눠 첫 칸/나머지로 읽고, 값이 없는 줄은 건너뛰며, 파인더가 여럿이면 순서대로 쓴다 | fix `3cd225b` |
| 5 | Important | `README.md:71,102,105` | 「패턴 8개」(필드 8개), 「남은 101건」(실제 100건 처리·1건 스캔 PDF 건너뜀), 「이후 티켓: 정규식 baseline #150」(이 PR이 하는 일)이 현재 PR과 어긋난다 | fix `151a98b` |
| 6 | Important | `src/cheongyak_extract/regex_extract.py:66` | `_contract`가 끝 연도가 없으면 시작 연도를 쓴다. `2026.12.28 ~ 01.05`는 `2026.01.05`가 되어 시작보다 앞선다 | defer — 이 파일을 고치면 plan이 정한 규칙 고정 시점(`43b4de6`) 뒤 수정이라 `regex-new.md`가 무효가 된다(plan 「이번에 안 하는 것」). 재는 20건·남은 100건 리포트에서 이 모양으로 틀린 칸은 확인되지 않았다. 다음 규칙 판에서 고친다 |
| 7 | Important | `src/cheongyak_extract/compare.py:58` | 필드별 LLM 표를 정규식으로 읽을 때 같은 5열 모양의 다른 표가 생기면 키가 덮어써져 LLM 필드별 값이 바뀌어도 에러가 안 난다. 필드별 합과 C안 합계를 대조하는 검사가 없다 | defer — 지금 리포트로는 필드별 맞은 칸 합 154가 C안 합계 154와 같다(이 리뷰에서 손으로 확인). 리포트 형식이 바뀔 때만 위험하고 그때는 두 합이 갈린다. 검사는 `extract-new.md` 형식을 바꾸는 티켓에서 같이 넣는다 |
| 8 | Suggestion | `src/cheongyak_extract/regex_extract.py:55` | `_scale`이 `일반분양`이 없으면 줄의 마지막 `N세대`를 쓴다. `총 500세대 (특별공급 200세대)`면 200세대를 줘 비움이 아니라 틀림이 된다. 재는 20건에서 공급규모 틀린 칸 4 | 기록만 |
| 9 | Suggestion | `src/cheongyak_extract/pipeline.py:_analyze` | `ask=None`이 「정규식으로 뽑는다」 신호다. `ask`를 잘못 못 만든 호출자도 조용히 정규식 결과를 받는다. 지금 CLI 경로에서는 `llm`이면 항상 `ask`를 만든다 | 기록만 |
| 10 | Suggestion | `src/cheongyak_extract/pipeline.py:_report` | 정규식 + `--text T0 T1`이면 방식 비교 표 없이 `## T0`·`## T1` 절이 같은 값으로 나란히 나온다. 스모크 실행은 EXIT=0 | 기록만 |
| 11 | Suggestion | `tests/test_regex_extract.py` | 공급규모·모집공고일·계약일의 값 없는 라벨, 계약일 대체 라벨, 필드별 근거 줄 정확 일치, 머리글 3줄 경계, 연도 넘김 시험이 없다. `--extractor regex` 통합 시험이 `evaluate`까지 안 간다 | 기록만 |
| 12 | Suggestion | `src/cheongyak_extract/compare.py:2,248` | 모듈 설명이 읽는 파일 둘만 적고(`extract-tune-0.md`·`regex-more.md`도 읽음), 비교 표 문장이 「수정 3」을 박아 둔다 | 기록만 |
| 13 | Suggestion | `src/cheongyak_extract/compare.py:12` | 다른 모듈의 `_analyze`·`_state`(밑줄 이름)를 가져다 쓴다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 통과 1: `regex_extract`가 FIELDS 8개를 키로 돌려주고 못 찾으면 `EMPTY` | 예 | `tests/test_regex_extract.py:26,36` · 372 passed |
| 통과 1: 패턴에 공고 번호·회사명·지명을 넣지 않는다 | 예 | `regex_extract.py` 전체를 읽어 확인: 공고 번호·회사명·지명 리터럴 없음 |
| 통과 2: `eval --extractor regex`가 OpenAI 클라이언트 없이 `OPENAI_API_KEY` 없이 동작 | 예 | `tests/test_main.py:117` · `env -u OPENAI_API_KEY ... eval --extractor regex --text T0 T1` EXIT=0 |
| 통과 3: 리포트 넷이 커밋됨 | 예 | `reports/regex-tune.md` · `regex-new.md` · `regex-more.md` · `regex-vs-llm.md` |
| 통과 3: 남은 101건 | 판정 불가 | `regex-more.md`는 100건 처리, 1건(2026000235)은 스캔 PDF로 건너뜀. 건너뛴 사실은 리포트에 적혀 있다 |
| 통과 4: pytest·ruff 통과 | 예 | `374 passed` · `ruff check` All checks passed · `ruff format --check` 57 files already formatted |
| 통과 4: GitHub Actions pytest green | 예 | `gh pr checks`: pytest pass(리뷰 fix 전 커밋 기준) |
| 실패 징후 1: 재는 20건 정규식 정답 있는 칸 160, 세 수가 LLM과 같은 표에 나란히, 필드별 표 | 예 | `reports/regex-vs-llm.md` §1·§2: 정규식 160칸 111/34/15, LLM 160칸 154/0/6 |
| 실패 징후 1: 규칙 고정 커밋이 측정 커밋보다 앞 | 예 | `43b4de6`(고정) < `5368dd1`(측정). `regex_extract.py`는 `43b4de6` 뒤로 안 바뀜 |
| 실패 징후 1: OpenAI API를 부르지 않음 | 예 | `compare.py`·정규식 경로에 `make_ask` 호출 없음. 리뷰에서 재측정·재호출 없음 |
| 실패 징후 2: 다듬는 29건 − 재는 20건 맞은 칸 비율 | 판정하지 않음, 값만 | 정규식 69.40% − 69.38% = +0.02%p, LLM 94.40% − 96.25% = −1.85%p |
| 실패 징후 3: 남은 공고 맞은 칸 비율 | 판정하지 않음, 값만 | 정규식 남은 100건 62.12%(정답 있는 칸 800), 재는 20건과 −7.25%p |
| 실패 징후 4: 재는 20건 칸마다 갈린 곳 | 판정하지 않음, 값만 | 정규식 맞음·LLM 틀림 1, 정규식 틀림·LLM 맞음 44, 둘 다 틀림 5, 둘 다 맞음 110 |

## 확인한 것

- 이 세션은 OpenAI를 부르지 않았다. 리뷰 도중 스모크 실행(`--extractor regex`)만 `data/raw/`를 읽었다
- fix 뒤 `uv run pytest` 374 passed, `uv run ruff check` 통과
- GitHub Actions는 리뷰 fix 커밋을 push하기 전 값이라 push 뒤 다시 확인하지 않았다
- 코드 리뷰 에이전트(`pr-review-toolkit:code-reviewer`)는 시간 안에 결과를 돌려주지 않아 이 리뷰에 그 지적이 없다. 코드 쪽 지적은 이 세션이 직접 읽은 것과 조용한 실패·테스트·주석 에이전트 3개 결과다
