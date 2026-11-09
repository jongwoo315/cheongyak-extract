# 179 리뷰 — PR #14 (반려 뒤 재작업)

**대상:** `cd2337a..HEAD` — 9 commits(재작업 8 + 리뷰 fix 1), 13 files(리뷰 파일 제외), +102 −70. 첫 리뷰는 `docs/plans/179-1105-review-resident-block.md`
**plan:** docs/plans/179-1105-plan-resident-block.md (RESUME 절 R1~R5)
**단어장:** `docs/concepts.md`의 `## 용어` 절에 「쓰지 말 말」 칸이 없어 단어장 검사를 건너뛰었다

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `docs/concepts.md:16` | 「전체」 행이 `_extract_notice`의 `else`를 `pdf_fields.py:869`라고 적었다. 실제 `else`는 868줄이고 869줄은 그 안쪽 첫 줄(`got = extract(pages, …)`)이다. `_ends_block` docstring이 한 줄 늘면서 867이 868로 밀렸는데 고칠 때 869로 적었다 | fix `621e3bc` |
| 2 | Suggestion | `tests/test_pdf_text.py:84` | 회전된 쪽을 `tables=True`(T1)로 뽑는 테스트가 없다. 픽스처에 표가 없어 `remove_rotation()`이 `find_tables()` 앞에 있는지는 어느 테스트로도 확인되지 않는다. 2026000184의 21쪽을 T1으로 뽑으면 「익산」과 `[표]` 2개가 나오는 것은 코드 리뷰 에이전트가 손으로 확인했다 | 기록만 |
| 3 | Suggestion | `tests/test_pdf_text.py:104` | `test_pages_leaves_an_unrotated_page_as_it_was`는 기대값을 같은 `get_text(sort=True)`로 만들어 `remove_rotation()`을 지워도 통과한다. 회전 테스트는 90도 하나뿐이다(180·270도는 없다) | 기록만 |
| 4 | Suggestion | `src/cheongyak_extract/pdf_fields.py:263` | 줄 중간의 `■`는 어디서든 묶음을 끝낸다. 본문 이어지는 줄이 `해당지역 거주자 ■ 수원시` 꼴이면 그 뒤가 잘린다. 이 동작을 고정하는 테스트는 `■ 다음 항목` 꼴 하나이고, 이전(main) 코드의 `"■" in rest`와 같은 동작이며 plan R3가 정한 것이다. 149건 중 글이 바뀐 공고는 2026000293 하나(4574자 → 1231자, 26줄)다 | 기록만 |
| 5 | Suggestion | `src/cheongyak_extract/pdf_text.py:12` | 90도·270도 회전 쪽에서 `remove_rotation()`이 내부에서 `set_mediabox()`를 불러 CropBox를 지운다(코드 리뷰 에이전트가 pymupdf 소스에서 확인). 회전과 잘라 낸 영역이 같이 있는 공고가 들어오면 안 보이던 여백 글자가 쪽 텍스트에 섞일 수 있다. 149건 중 회전된 쪽의 CropBox와 MediaBox가 다른 경우는 0건이다 | 기록만 |
| 6 | Suggestion | `src/cheongyak_extract/pdf_fields.py:267` | `_block_rule_1` docstring이 끝 판정을 「다음 머리 기호 줄이나 「②」가 든 줄 앞까지」로 두었다. 줄 중간 `■`는 `_ends_block` docstring(`:262`)과 `docs/concepts.md:13`에만 있다. `pages()` docstring(`pdf_text.py:21`)에도 쪽 회전을 푼다는 말이 없고 주석(`:12`)에만 있다 | 기록만 |
| 7 | Suggestion | `docs/plans/179-1105-design-resident-block.md:46` | 설계 §설계 결정 1 본문이 묶음 끝을 「다음 머리 기호 줄 또는 `②`가 든 줄 앞」으로 두었다. 줄 중간 `■`는 맨 아래 「반려 뒤 고친 것」 절(`:76`)에만 있다. 같은 문서 「착수 때 확인한 사실」 4·5번의 숫자(규칙 1 65·2 6·3 8, 48/49·29/30)도 착수 시점 값이라 지금 리포트(73·6·1·0, 50/50·30/30)와 다르다. plan `:111`의 「텍스트가 뒤섞여 …」 추측은 `:88`이 처음 실행의 plan이라고 밝혀 두었다 | 기록만 |
| 8 | Suggestion | `README.md:20` | 판단 기록 표의 #179 행 결과 칸에 「24건에서 1건(2026000184, 텍스트 뒤섞임)」이 남아 있다. 이 행은 `docs/decisions.md`의 반려 시점 PR 게이트 기록을 옮긴 것이고 plan R5가 그쪽 행은 고치지 않는다고 했다. 원인이 쪽 회전이었다는 것은 같은 README `:163`이 설명한다 | 기록만 |

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| R1: `pdf_text.pages`가 회전된 쪽의 회전을 풀고 뽑는다. 가짜 PDF 테스트가 있다(`tmp_path`, `data/raw`를 안 읽는다) | 예 | `src/cheongyak_extract/pdf_text.py:12`, `tests/test_pdf_text.py:84-108` 테스트 2개. 테스트 분석 에이전트가 `remove_rotation()`을 빼면 `lines[0]`이 `②추첨`이 되어 실패함을 확인 |
| R1: 바꾸기 전·후 149건 쪽 텍스트 비교로 바뀐 공고가 2026000184 하나뿐이다 | 예 | 이 세션이 `data/raw`의 PDF 150개(텍스트 없는 1개 포함)에 `remove_rotation()` 전·후 `get_text(sort=True)`를 비교: 바뀐 공고 `2026000184` 1건(71쪽), 회전된 쪽이 있는 공고도 이 1건 |
| R2: `labels/pdf-only-50.json`의 2026000184 세 칸을 회전을 푼 텍스트에서 채우고, LLM을 다시 돌리기 전에 커밋한다. 다른 칸은 안 바꾼다 | 예 | 커밋 `7c99cdc`가 `e0d6d58`(LLM 다시 측정)보다 앞이다. `git diff main -- labels/` 12 insertions · 12 deletions, 전부 2026000184의 세 칸. 세 인용(5·21·13쪽)이 해당 쪽의 회전을 푼 텍스트에 공백을 무시하고 들어 있다 |
| R3: 묶음 끝 판정이 줄 중간 `■`에서도 묶음을 끝낸다. 테스트가 있고 2026000293 묶음이 다시 26줄이다. 149건 묶음 비교를 PR 본문에 적는다 | 예 | `pdf_fields.py:261-263`, `tests/test_pdf_fields.py:979`(새 테스트는 이전 식에서 실패함을 테스트 분석 에이전트가 확인), `reports/pdf-resident-test.md` 2026000293 76줄 → 26줄. PR 본문에 비교 결과 있음 |
| R4: `check-pdf-labels`·`eval-pdf` 두 번·`regex-more.md`·`regex-vs-llm.md`를 다시 만든다. LLM 설명은 안 고친다 | 예 | `73e5c6c` `e0d6d58` `9ad978e`. README 숫자(규칙 1 137·2 9·3 3, 50/50, 30/30)와 세 리포트가 서로 같다(주석 분석 에이전트가 대조). OpenAI는 이 세션이 다시 부르지 않아 숫자 자체는 다시 재지 않았다 |
| R5: 설계 문서·README·`docs/concepts.md`에서 2026000184를 「텍스트 뒤섞임」으로 적은 곳을 고친다. `docs/decisions.md`는 안 고친다 | 예 | `README.md:163`, `docs/concepts.md`, 설계 문서 고침. 남은 곳은 위 7·8번(반려 시점 기록과 처음 실행 plan) |
| `uv run pytest`, `ruff check`, `ruff format --check` 통과 | 예 | `676 passed`, `All checks passed!`, `89 files already formatted` |
| 실패 징후 1: PDF 전체를 넘기는 공고 수(통과 0 / 다시 잰다 0건인데 21쪽 규칙 1이 아님 / 미완 1 이상)와 2026000184 묶음 | 값만 적음 | `reports/pdf-labels.md`: 0건/149. 이 세션이 고른 자리를 다시 재지는 않았고 코드 리뷰 에이전트가 2026000184 묶음이 21쪽 규칙 1, 첫 줄 `■ ① 지역  : 해당지역 거주자 (익산시 거주자) → …`임을 확인. 구간 판정은 사람 몫 |
| 실패 징후 2: 쪽 텍스트가 바뀐 공고 수(기대 1), 정규식 100건 맞은 칸 전·후 | 값만 적음 | 바뀐 공고 1건(위 R1). 정규식 100건 맞은 칸 497 → 502는 PR 본문 값이고 이 세션은 다시 재지 않았다 |
| 실패 징후 3: `QUOTE_OUTSIDE_BLOCK` 칸 수(정상 1 이하 / 다시 본다 2 / 미완 3 이상) | 값만 적음 | `reports/pdf-labels.md`: 1칸(2026000116, baseline과 같다) |
| 실패 징후 4: 거주지 맞은 칸(정상: 다듬는 쪽 틀린 칸 0~1, 재는 30건 29 이상) | 값만 적음 | `reports/pdf-fields-tune-2.md` 50/50, `reports/pdf-resident-test.md` 30/30. 2026000184 세 칸의 LLM 값과 정답은 PR 본문에 있고 정답과 같다 |
| Done criteria: `git diff main -- labels/`가 2026000184 세 칸뿐이다 | 예 | 위 R2 |

## 처리 결과

- 리뷰 fix 1건(1번)을 커밋했다. 8건 중 Important는 이 1건이고 나머지 7건은 Suggestion이라 기록만 했다
- 지난 리뷰의 defer(1·2·9번)는 그대로다. 1번(줄 중간 `■`로 묶음이 안 끊김)은 이번 재작업 `a478a4b`가 풀었다. 2026000293 묶음이 76줄에서 26줄로 돌아왔다
- `push-back`·`defer`·`won't-fix` 행이 없어 인라인 스레드는 달지 않는다
- OpenAI와 청약홈은 부르지 않았다. 이 세션의 측정은 PDF 150개의 회전 전·후 비교와 인용 확인뿐이다
