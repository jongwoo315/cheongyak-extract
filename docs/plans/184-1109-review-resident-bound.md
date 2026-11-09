# 184 리뷰 — PR #15

**대상:** `main...HEAD` — 11 commits, 13 files, +1658 −28
**plan:** docs/plans/184-1109-plan-resident-bound.md

## 지적

| # | 심각도 | 위치 | 내용 | 처리 |
| --- | --- | --- | --- | --- |
| 1 | Important | `docs/concepts.md:14` · `docs/concepts.md:16` | 이 PR이 코드를 늘려 규칙 2 행(`:297`)과 전체 행(`:868`)의 줄 번호가 어긋났다. 현재 코드는 `_block_rule_2`가 306, `_extract_notice`의 `else` 가지가 889다 | fix `a5e0ccb` |
| 2 | Important | `tests/test_pdf_fields.py:1160` | `test_rule_3_uses_the_first_title_line_of_the_document`의 문장이 두 제목 줄 뒤에만 있어, 마지막 제목 줄을 써도 통과한다. 이름이 말하는 동작을 확인하지 않는다 | fix `c6e1e43` |
| 3 | Important | `tests/test_pdf_fields.py:1020` | 규칙 1 상한의 경계(정확히 5줄, 6줄)가 안 박혀 있다는 지적 | push-back — 9줄 이어지는 쪽 테스트가 묶음이 정확히 5줄임을 확인하고, 끝 줄이 5줄 전에 나오는 테스트와 쪽을 넘는 테스트(5줄째에서 끊김)가 있어 상한이 하나 크거나 작아지면 어느 쪽이든 실패한다 | <!-- style-exempt -->
| 4 | Suggestion | `src/cheongyak_extract/pdf_fields.py:303` | 목차 줄을 거르는 `_TOC_TAIL`이 점선 + 쪽 번호만 잡는다. 점선 없이 공백으로 쪽 번호를 띄운 목차 줄(`5  일반공급 (…)   16`)은 첫 제목 줄이 되어 앞쪽 문장을 고를 수 있다 | defer — 149건에는 이 꼴이 없다(리포트에서 규칙 3 공고 셋의 제목 줄은 16쪽·9쪽·20쪽이고 PDF 전체를 넘기는 공고는 0건). plan 실패 징후 2의 미완 구간에 해당하는 입력이라, 실제 공고에서 나오면 그때 정규식을 넓힌다 |
| 5 | Suggestion | `src/cheongyak_extract/pdf_fields.py:359` | 제목 줄이 없는 공고에서 `rule_lines`의 문장 수가 0으로 나와, 「제목 줄이 없어서 0」과 「제목 줄은 있고 문장이 없어서 0」이 구분되지 않는다 | defer — `rule_lines`는 PDF 전체를 넘기는 공고의 원인을 보는 진단이고 이번 149건은 그런 공고가 0건이다. 그런 공고가 생기면 제목 줄 위치도 같이 돌려주게 바꾼다 |
| 6 | Suggestion | `src/cheongyak_extract/pdf_fields.py:285` | 상한에서 잘린 줄이 `Block`에 표시되지 않는다 | 기록만 — 잘리는 것이 plan이 정한 동작이고, 잘린 공고 둘의 전문은 `reports/resident-bound.md`에 있다 | <!-- style-exempt -->
| 7 | Suggestion | `src/cheongyak_extract/resident_bound.py:81` | 비교 코드가 `before`와 `after`의 공고 목록이 다르면 `KeyError`로 멈추고, `MUST_KEEP` 공고가 없으면 그 줄을 조용히 건너뛰고, 문장을 못 찾은 행이 「제목 줄 아래: 아니오」로 찍힌다 | 기록만 — 149건에 한 번 돌리는 일회성 리포트 코드다 |
| 8 | Suggestion | `src/cheongyak_extract/__main__.py:38` | 기준 커밋 `a51fe89`가 코드에 박혀 있고 `--compare-to` JSON이 그 커밋의 값인지 확인하지 않는다 | 기록만 |
| 9 | Suggestion | `tests/test_pdf_fields.py:1213` | 목차 꼴 파라미터 행 `5 일반공급 ........ 16`은 `_TOC_TAIL`이 아니라 「일반공급」 뒤가 `.`라서 거부되고, `…` 한 글자 점선 목차는 테스트가 없다 | 기록만 |
| 10 | Suggestion | `src/cheongyak_extract/resident_bound.py:67` | `_sentence_place`가 줄 내용이 같으면 제목 줄 아래의 첫 일치를 문장 위치로 잡는다. 같은 쪽에 똑같은 줄이 둘이면 다른 줄을 가리킬 수 있다 | 기록만 — 리포트에서 규칙 3 공고 셋의 쪽·줄이 plan의 값과 맞는다 |

단어장 검사: `docs/concepts.md`의 「쓰지 말 말」(일반공급 헤더, 절 시작 줄)이 diff의 코드·주석·docstring·문서에서 나온 곳은 그 정의 행뿐이다. 지적 없음.

## plan 대조

| plan 기준 | 코드가 만족하나 | 증거 |
| --- | --- | --- |
| 1. 규칙 1 묶음은 ①지역 줄부터 글이 든 줄 5개를 넘지 않는다(빈 줄 제외), 끝 줄이 먼저 나오면 거기서 끝, 상한에 걸려도 규칙 1 묶음 | 예 | `pdf_fields.py:268-293`, `tests/test_pdf_fields.py:1023-1050`, `reports/resident-bound.md`(5줄을 넘는 묶음 0건) | <!-- style-exempt -->
| 2. 규칙 3은 문서에서 처음 나온 일반공급 절 제목 줄 아래에서만 문장을 찾고(쪽을 넘어), 제목 줄이 없으면 묶음을 내지 않는다. 제목 줄 꼴 테스트 (a)~(d) | 예 | `pdf_fields.py:318-344`, `tests/test_pdf_fields.py:1131-1213` |
| 3. 규칙 3 정규식이 「거주자에 우선」도 받고, 기존 「거주자 말고 다른 것의 우선」 테스트는 통과 | 예 | `pdf_fields.py:299`, `test_rule_3_takes_a_resident_sentence_written_as_gojuja_e_usun`, `pytest` 701 passed |
| 4. `rule_lines`가 규칙 3을 `_block_rule_3`과 같은 범위로 센다 | 예 | `pdf_fields.py:359-371`, `test_rule_lines_counts_the_lines_each_rule_looks_for` |
| 5. 기존 규칙 3 테스트의 가짜 쪽에 제목 줄을 넣어 고친다 | 예 | `tests/test_pdf_fields.py`의 `GENERAL_TITLE` 사용 |
| 6. 149건 비교 리포트 `reports/resident-bound.md`와 main 쪽 값 `resident-bound-before.json` | 예 | 리포트를 다시 만들어 보니 재현 명령 줄의 출력 경로만 다르고 본문이 같다 |
| 7. `check-pdf-labels`·`eval-pdf` 두 번을 다시 돌린다 | 예(`check-pdf-labels`) · 판정 불가(`eval-pdf`) | `check-pdf-labels`를 다시 돌리니 `reports/pdf-labels.md`와 같고 정답 검사에 걸린 칸 1개다. `eval-pdf` 두 번은 OpenAI를 부르는 일이라 이 세션에서 다시 돌리지 않았다. `reports/pdf-resident-test.md`는 재는 30건이 PR 본문 값으로 바뀌어 있다 |
| 8. `docs/concepts.md`·README에 규칙 1·3과 일반공급 절 제목 줄을 반영 | 예 | `docs/concepts.md:13-17`, `README.md` 거주지 우선 비율 절. 규칙 2·전체 행 줄 번호는 지적 1로 고침 |
| 9. `uv run pytest`·`ruff check`·`ruff format --check` 통과, 새 테스트가 `data/raw`를 읽지 않는다 | 예 | pytest 701 passed, ruff 모두 통과 |

실패 징후 값(리포트 기준, 판정은 하지 않는다): 규칙 1 묶음 중 5줄을 넘는 것 0건, 잘린 공고 2건(2026000293·2026000310), 두 묶음에 필요한 줄이 남았다. 규칙 3 공고 셋(2026000274 20쪽, 2026000401 9쪽, 2026000402 20쪽)은 모두 제목 줄 아래이고 PDF 전체를 넘기는 공고는 0/149건이다.

테스트: 수정 뒤 `uv run pytest` 701 passed, `uv run ruff check`·`ruff format --check` 통과.
