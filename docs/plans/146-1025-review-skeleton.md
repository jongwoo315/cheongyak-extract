# 146 리뷰 — PR #1

**대상:** `main...HEAD` — 21 commits, 26 files, +2562 −0 (리뷰 fix 8커밋 포함, 이 파일 커밋 전)
**plan:** docs/plans/146-1025-plan-skeleton.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `src/cheongyak_extract/report.py:45` | 근거 문장이 빈 문자열이면 `"" in text`가 참이라 지어낸 값이 0으로 나온다 | fix `c8de12b` |
| 2 | Important | `src/cheongyak_extract/__main__.py:18` | 주석이 정답 없음일 때 「빈 칸 100%」라고 적었지만 실제 표시는 `—`다 | fix `67f9be7` |
| 3 | Important | `tests/test_report.py:61` | 근거 쪽 번호가 범위 밖(0, 마지막+1)인 경우 테스트가 없다 | fix `1db418d` |
| 4 | Important | `tests/test_fetch.py:83` | 상세에 공고문 링크가 없을 때 건너뛰는 경로 테스트가 없다 (plan 실패 징후 1이 이름을 든 경우) | fix `50f30e6` |
| 5 | Important | `tests/test_fetch.py:92` | 첫 첨부가 PDF가 아니고 두 번째 첨부가 PDF인 경우 테스트가 없다 | fix `227597d` |
| 6 | Important | `tests/test_pipeline.py:104` | 요청 사이 2초 쉬기(설계 문서 이용약관 절의 유일한 완화책)를 검증하는 테스트가 없다 | fix `58e003e` |
| 7 | Important | `tests/test_pipeline.py:60` | 통과 기준 1-5의 「stdout에 출력」을 확인하는 테스트가 없다 | fix `0a4e039` |
| 8 | Important | `tests/test_main.py:26` | CLI가 `--n`과 기본 경로를 `run`에 넘기는지 확인하는 테스트가 없다 | fix `db781ba` |
| 9 | Important | `src/cheongyak_extract/truth.py:15` | 표 caption·라벨이 바뀌거나 칸이 비면 모두 `None`이 되어 「사이트가 비워 둔 칸」과 구별이 안 된다. 에이전트는 Critical로 봤으나 stub 단계이고 모든 필드 `with_truth == 0` 검사가 있어 Important로 낮춤 | defer — #149(정답 수동 대조)에서 공고마다 표·라벨을 찾았는지 따로 기록한다 |
| 10 | Important | `src/cheongyak_extract/pipeline.py:62` | 실패한 실행(전부 건너뜀·목록 0건)도 `reports/skeleton.md`를 덮어쓴다 | won't-fix — 이 파일은 git에 있어 `git checkout`으로 복구된다. 건너뛴 공고를 리포트에 적는 것이 plan 「다시 잰다」 구간의 요구라 실패 실행에도 쓴다 |
| 11 | Important | `src/cheongyak_extract/pipeline.py:45` | 403·429·5xx도 공고 하나의 건너뜀으로 처리해 차단당한 뒤에도 목록 끝까지 2초 간격으로 계속 요청한다 | defer — #151(공고 수 확대) 전에 연속 실패 시 중단을 넣는다. 이번은 `--n 3`이라 요청이 최대 20회 안팎이다 |
| 12 | Important | `src/cheongyak_extract/pipeline.py:37` | 목록이 비거나 행에 `data-hmno`가 없으면 원인 설명 없이 빈 리포트·`KeyError`로 끝난다 | defer — #151. 지금은 3건 고정 실행이고 목록 레이아웃이 바뀌면 테스트 fixture 갱신 때 드러난다 |
| 13 | Important | `src/cheongyak_extract/pipeline.py:49` | 암호화·손상 쪽 때문에 `FileDataError`가 아닌 예외가 나면 그때까지의 결과 전체가 사라지고, 텍스트가 0자인 스캔 PDF는 그대로 통과한다 | defer — #147(LLM 추출). 실제 공고문 10건에서는 안 나왔고, 0자 PDF는 추출을 켜야 의미가 생긴다 |
| 14 | Important | `src/cheongyak_extract/fetch.py:73` | PDF 판정이 `Content-Disposition` 파일명 하나뿐이라 헤더가 없거나 `utf-8''` 소문자 등 다른 꼴이면 진짜 PDF도 「PDF 아님」으로 건너뛴다 | defer — #151. 실제 요청 3건은 전부 이 헤더가 왔다 |
| 15 | Important | `src/cheongyak_extract/report.py:58` | `Doc`이 `truth`·`extracted`에 모든 `FIELDS` 키가 있다고 가정해, #147의 실제 추출이 일부 필드만 돌려주면 `KeyError`로 실행 전체가 끝난다 | defer — #147에서 `extract()`가 모든 키를 보장하게 하거나 `.get`으로 바꾼다. 지금 stub은 항상 전부 채운다 |
| 16 | Important | `src/cheongyak_extract/extract.py:10` | `Extraction`이 `page` 있고 `evidence` 없음, `page <= 0` 같은 모순된 값을 막지 않는다 | defer — #147. 값을 만드는 쪽이 생길 때 검증을 같이 넣는다 |
| 17 | Suggestion | `src/cheongyak_extract/report.py:41` | `_norm`이 줄바꿈을 공백으로 바꿔 PDF에서 `…~\n2026.11.21`처럼 줄이 끊긴 근거가 `~ 2026…`이 되어 일치하지 않는다 | 기록만 — #147에서 근거를 PDF 그대로 복사하게 되면 공백을 모두 지우고 비교하는 쪽으로 바꾼다 |
| 18 | Suggestion | `src/cheongyak_extract/truth.py:35` | 청약일정 칸 전체 텍스트가 정답이라 `2026-10-23 (헤럴드경제신문)`처럼 값이 아닌 부분이 붙는다. #148에서 정답 쪽도 같이 정리해야 한다 | 기록만 |
| 19 | Suggestion | `src/cheongyak_extract/truth.py:41` | 기타사항 표에서 `zip(strict=False)`가 길이 불일치와 `colspan`을 조용히 넘긴다. 라벨이 중복되면 뒤가 앞을 덮는다 | 기록만 |
| 20 | Suggestion | `src/cheongyak_extract/fetch.py:70` | 첫 링크의 HTTP 오류가 공고 전체를 건너뛰게 한다 (다음 링크를 안 시도) | 기록만 — plan이 재시도를 이번에 안 하는 것으로 뒀다 |
| 21 | Suggestion | `src/cheongyak_extract/extract.py:13` · `src/cheongyak_extract/truth.py:1` · `src/cheongyak_extract/fetch.py:1` | 주석이 입주예정월(표 밖 문구)·목록 요청 위치(`pipeline.run`)를 정확히 말하지 않는다 | 기록만 |
| 22 | Suggestion | `src/cheongyak_extract/report.py:19` | `Doc`은 `frozen`인데 안의 `dict`·`list`는 바꿀 수 있다. `truth.py`가 `extract.py`에서 `FIELDS`를 가져와 두 모듈이 엮여 있다 | 기록만 |
| 23 | Suggestion | `tests/test_extract.py:10` | `FIELDS` 값을 그대로 복사해 두어 #147·#148이 `FIELDS`를 바꾸면 행동과 무관하게 깨진다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 통과 기준 1. `uv run python -m cheongyak_extract run --n 3` 한 번으로 1~5가 끝나고 exit code 0 | 판정 불가 | 모의 응답으로 끝까지 도는 것은 `tests/test_pipeline.py:44` 통과. 실제 사이트 재실행은 이용약관 불명 상태라 요청을 늘리지 않으려고 하지 않았다. 구현 때 만든 `reports/skeleton.md:3`에 공고 3건이 있다 |
| 통과 기준 2. 리포트 열 7개 | 예 | `src/cheongyak_extract/report.py:7-15` · `reports/skeleton.md:5` |
| 통과 기준 3. 모든 필드 정확도 0%, 빈 칸 100%, 지어낸 값 0, 비어야 하는데 채움 0 | 예 | `reports/skeleton.md:7-14` · `tests/test_pipeline.py:52-54` |
| 통과 기준 4. 모든 필드 정답 있음 ≥ 1 | 예 | `reports/skeleton.md:7-14` 전부 3 |
| 통과 기준 5. `uv run pytest`가 네트워크 없이 통과, 끝까지 도는 테스트 1개 | 예 | `31 passed` (fix 뒤), 테스트의 `httpx.Client`는 전부 `MockTransport`(`grep` 결과 transport 없는 호출 0) |
| 통과 기준 6. GitHub Actions에서 같은 pytest green | 예 | `gh pr checks` → `pytest pass` (fix 푸시 `db781ba` 기준) |
| 실패 징후 1. 공고 3건 처리, 건너뛴 공고와 이유를 리포트에 적는다 | 예 | `reports/skeleton.md:3` 처리 3건 · `reports/skeleton.md:18` 2026000531 「상세에 공고문 링크 없음」 |
| 실패 징후 2. 정답 필드 수 | 예 (값: 8개) | `src/cheongyak_extract/extract.py:14-23`. plan 구간으로는 「6개 이상이면 정상」 |
| 실패 징후 3. 테스트가 네트워크를 타나 | 아니오 (타지 않음) | 위 통과 기준 5 증거와 같다 |
| 이번에 안 하는 것(LLM 추출·정규화·재시도·동시 요청) | 예 | `extract.py:26-28` stub · `report.py:63` strip만 · `fetch.py` 순차 요청, 재시도 없음 |

## 기타

- 다음 티켓 참고(코드 문제 아님): 2026000532의 상세 HTML 당첨자 발표일은 `2026-11-11`인데 공고문 PDF 1쪽에는 `2026.11.10.(화)`로 보인다. 정답 출처가 둘이 다를 수 있다 — #149 재료.
- 테스트: `uv run pytest` 31 passed, `uv run ruff check .` 통과. 리뷰 에이전트 5종(code·tests·errors·comments·types)을 돌렸고 `simplify`는 돌리지 않았다.
