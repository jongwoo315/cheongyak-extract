# #147 LLM 추출 — 구현 계획

> **For Claude:** This plan is executed via /ralph-loop:ralph-loop in a detached orch session.
> You are ALREADY in the worktree, checked out on the feature branch. Do NOT switch branches,
> create another worktree, or use AskUserQuestion / any interactive prompt — the session is
> headless and cannot receive input, so always take the autonomous (recommended) default and
> keep working. Do NOT use superpowers:executing-plans or subagent-driven-development.
> Emit `<promise>RALPH_DONE</promise>` ONLY when every Done-criteria item and every Pre-PR check
> is genuinely true AND the PR has been created — never to escape the loop.
> Before emitting it, stop every background shell you started (TaskStop tool). A shell left
> running keeps the session in `bg` state, and orch never marks the step done.
> On a HARD, retry-proof API error (OpenAI insufficient_quota, 401/403, exhausted billing), STOP —
> do NOT emit RALPH_DONE, do NOT create a PR, do NOT spin retrying. It surfaces via the orch
> completion notification; a human fixes billing. (Transient TPM 429 is different — pace and retry.)
> A TRANSIENT error that stops being transient counts as HARD. If 429/529 keeps surfacing AND you
> have produced no commit and no file change for 20 minutes, STOP the same way. Waiting and
> spinning are indistinguishable in a headless loop — nobody is watching the screen, and the loop
> re-submits the prompt after every failed turn, so a server-side outage burns the whole iteration
> budget while the picker still reads `working`.

**Tier:** B
**Notion:** #147 https://app.notion.com/p/40441e6165c081b89e3ff954da162fc9
**설계:** /Users/jw/prv/.wt/147-llm-extract/docs/plans/147-1026-design-llm-extract.md (먼저 읽는다. 결정 근거는 거기 있다)

## jw 기준

extract()의 fields에 대한 값들을 llm이 제대로 파싱한다. 파싱하지 못하면 비운다.

## 통과 기준

1. `extract(pages, ask)`가 LLM 호출 한 번으로 8개 필드(`FIELDS`) 전부의 `Extraction(value, evidence, page)`를 돌려준다.
   응답에 키가 빠져도 모든 키가 있다
2. 설계 문서 §코드가 거르는 규칙 5개가 각각 테스트로 있고, 걸린 칸은 비워지고 비운 이유가 남는다
3. `Extraction`이 모순 값을 만들면 `ValueError`다(값 없음 + 근거나 쪽 있음 / 값 있음 + 근거나 쪽 없음 / 쪽 < 1)
4. 실제 OpenAI 호출은 프롬프트 sha256 캐시를 거친다(`data/llm/`, git 밖). 같은 프롬프트 두 번째 호출은 API를 부르지 않는다 — 테스트로 확인
5. 테스트는 API를 부르지 않는다. 설계에 쓴 공고 3건의 실제 응답이 `tests/fixtures/llm/<pbno>.json`에 커밋돼 있고 이걸 재생하는 테스트가 있다
6. 오프라인 측정 명령: `uv run python -m cheongyak_extract eval --pbno <pbno>... --out <path>`가 `data/raw/<pbno>/`만 읽어 리포트를 쓴다(청약홈에 요청 없음)
   - 리포트 표에 지금 열(정확도·빈 칸·지어낸 값·비어야 하는데 채움·근거 위치 맞음)과 함께 `틀리게 채움`(칸 수)·`근거 확인 못해 비움`(칸 수) 열이 있다
   - 표 아래 「틀리게 채운 칸」 목록: 공고·필드·정답·추출값·근거·쪽
   - 공고별 입력·출력 토큰 수와 합계
7. 리포트 두 개가 커밋돼 있다
   - `reports/extract-design.md` — 설계에 쓴 3건(2026000518·2026000530·2026000532)
   - `reports/extract-new.md` — 프롬프트를 고정한 커밋 뒤에 받은 새 공고(PDF 있는 것, 최대 5건)
8. 지어낸 값(근거가 PDF에 없는데 채운 칸)은 두 리포트 모두 0이다. 거르는 규칙이 있으므로 0이 아니면 버그다
9. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green

## 이번에 안 하는 것

- 정규식 baseline 비교(#150), PDF에만 있는 필드(#152), 정답 수동 대조(#149), 150건 확대(#151)
- 모델 비교와 반복 실행 재현성. 기본 모델 `gpt-5.4-mini` 하나만 쓴다(`OPENAI_EXTRACT_MODEL`로 바꿀 수 있게만 한다)
- 쪽 고르기(검색) 단계. 문서 전체를 넣는다(설계 문서 §문서 전체를 한 번에 넣는다)
- 정규화 규칙 수정(#148 리뷰 13·14 포함). 틀리게 채운 칸의 원인이 정규화면 원인 칸에 적기만 한다
- 수집 쪽 실패 처리(#146 리뷰 11·12·14) — #151
- 새 공고 결과를 보고 프롬프트를 고치는 것. 고치면 그 공고들도 설계에 쓴 공고가 된다

## 실패 징후

칸 = 공고 × 필드 중 정답이 있는 칸. 맞음 / 비움 / 틀리게 채움으로 나뉜다(설계 문서 §측정).
틀리게 채운 칸은 원인을 `LLM 오답` / `정규화` / `정답 쪽` 중 하나로 PR 본문 표에 적는다. 분류 근거(PDF 원문 줄)를 같이 적는다.

1. **jw 기준 — 새 공고에서 제대로 뽑고, 못 뽑으면 비웠나.** 잴 값: `reports/extract-new.md`의 맞음 칸 비율, 그리고 `LLM 오답`으로 분류한 틀리게 채움 칸 수.
   baseline 없음 — 이번이 첫 LLM 측정이고 다음 티켓(#150 정규식)의 비교 대상이 된다
   - 통과: 맞음 80% 이상, 그리고 `LLM 오답` 1칸 이하
   - 다시 잰다: 맞음 60~79% 또는 `LLM 오답` 2~3칸. 프롬프트는 고치지 않고 새 공고를 5건 더 받아 같은 프롬프트로 한 번 더 잰 뒤 두 결과를 합쳐 적는다
   - 미완: 맞음 60% 미만 / `LLM 오답` 4칸 이상 / 새 공고를 하나도 못 받아 `extract-new.md`가 없다
2. **근거를 못 찾아 비운 칸이 많나.** 잴 값: LLM이 값을 준 칸 중 거르는 규칙 4(근거가 그 쪽에 없음)로 비운 칸 비율, 두 리포트 각각
   - 정상: 10% 미만
   - 다시 본다: 10~25%. 비운 칸의 근거 문장과 그 쪽 텍스트를 나란히 PR 본문에 적는다. 고치는 것은 설계에 쓴 3건으로만 한다(프롬프트의 「근거는 원문 그대로 복사」 지시, 공백 비교 규칙)
   - 미완: 25% 초과
3. **설계에 쓴 3건에만 맞춘 프롬프트인가.** 잴 값: 맞음 비율 차이(설계 3건 − 새 공고)
   - 정상: 10%p 미만
   - 지켜본다: 10~20%p. PR 본문에 어떤 필드에서 벌어졌는지 적는다
   - 과적합 의심: 20%p 이상. 그대로 PR 본문 맨 위에 적는다
4. **지어낸 값이 0이 아니다.** 통과 기준 8. 1칸이라도 나오면 거르는 규칙 버그다 — 고친다
5. **컨텍스트 한도.** 한도를 넘어 건너뛴 공고가 있으면 공고 번호와 토큰 수를 리포트·PR 본문에 적는다. 조용히 자르지 않는다

## 파일

| 파일 | 할 일 |
| --- | --- |
| `src/cheongyak_extract/extract.py` | `Extraction.__post_init__` 검증, `build_prompt(pages)`, `extract(pages, ask)` + 거르는 규칙. 비운 이유를 같이 돌려준다 |
| `src/cheongyak_extract/llm.py` (새) | OpenAI Responses API + structured outputs(JSON schema `strict`) 호출, `data/llm/` 캐시, 토큰 수 기록. `make_ask(model, cache_dir)` |
| `src/cheongyak_extract/report.py` | `_grounded`를 공백 전부 제거 비교로(설계 §거르는 규칙 4와 같은 함수를 쓴다), `.get` 기본값(#146 리뷰 15), 새 열 2개, 틀리게 채운 칸 목록, 토큰 표 |
| `src/cheongyak_extract/pipeline.py` | `run()`이 `ask`를 받는다. 0자 PDF·열기 예외·컨텍스트 초과는 그 공고만 건너뛴다(#146 리뷰 13). 오프라인 `evaluate(pbnos, raw_dir, ask, report_path)` |
| `src/cheongyak_extract/__main__.py` | `eval` 하위 명령. `run`은 실제 LLM을 부른다 |
| `tests/fixtures/llm/<pbno>.json` (새) | 설계에 쓴 3건의 실제 응답 |
| `pyproject.toml`, `uv.lock` | `openai` 추가(`uv add openai`) |
| `.gitignore` | `data/llm/` |
| `README.md` | 흐름 그림의 extract 줄, 현재 상태, `eval` 명령, `OPENAI_API_KEY` 필요 |

`evidence`·`page` 같은 이름은 지금 코드를 따른다. 쪽 번호는 1부터다(`pdf_text.py`: 리스트 인덱스 + 1).

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. **`Extraction` 검증** — 통과 기준 3. 기존 테스트가 만드는 `Extraction`이 모순이면 그 테스트를 고친다
2. **근거 비교 함수** — 공백·줄바꿈을 모두 지우고 포함 여부를 본다. `report._grounded`와 거르는 규칙이 같은 함수를 쓴다. 테스트: `…~\n2026.11.29` 근거가 `… ~ 2026.11.29` 쪽 텍스트에서 찾아진다
3. **`extract(pages, ask)` + 거르는 규칙** — `ask`는 `Callable[[str], str]`(프롬프트 → 응답 JSON 문자열). 가짜 `ask`로 규칙 5개 각각, 정상 응답, JSON이 아닌 응답(전부 비우고 이유 남김)을 테스트
   - 프롬프트: 쪽마다 `<page n>` 표시, 필드별 정의(정답이 청약홈 표 값이라는 것 — 예: `공급규모`는 일반분양 세대수 하나, `계약일`은 시작~끝, `입주예정월`은 년·월), 근거는 PDF 원문을 그대로 복사, 확실하지 않으면 값을 null로
   - 출력 schema: 8개 키 각각 `{value: string|null, evidence: string|null, page: integer|null}`, 전부 required, `additionalProperties: false`
4. **`llm.make_ask`** — OpenAI 호출과 캐시. 테스트는 OpenAI 클라이언트를 가짜로 넣어 캐시 적중 시 호출 0회를 확인한다. `pip`이 아니라 `uv add openai`. API 문서는 context7로 확인한다(Responses API `text.format` json_schema)
5. **리포트·파이프라인** — 새 열, 틀리게 채운 칸 목록, 토큰 표, `.get` 기본값, 공고 단위 건너뜀(0자·열기 예외·컨텍스트 초과). 기존 stub 기반 테스트는 가짜 `ask`로 옮긴다
6. **`eval` 명령** — `data/raw/<pbno>/`만 읽는다. `detail.html` 또는 `notice.pdf`가 없으면 그 공고를 건너뛰고 이유를 적는다
7. **프롬프트 다듬기와 고정 — 설계에 쓴 3건만 쓴다.** `eval --pbno 2026000518 2026000530 2026000532 --out reports/extract-design.md`를 실제 API로 돌린다
   - 틀린 칸을 보고 프롬프트를 고친다. 이 단계에서 새 공고는 받지도 보지도 않는다
   - 마지막 실행의 응답을 `tests/fixtures/llm/<pbno>.json`에 복사하고, 재생 테스트(쪽 텍스트는 근거 문장으로 만든다)를 넣는다
   - 이 커밋이 프롬프트 고정 시점이다. 커밋 메시지에 「프롬프트 고정」을 쓴다
8. **새 공고 측정 — 한 번만.** `run --n 8`로 청약홈 목록 위에서부터 PDF 있는 공고를 받는다(요청 사이 2초, 이미 있는 코드)
   - 새 공고 = `data/raw/`에 `notice.pdf`가 있고 설계 3건이 아닌 것. 최대 5건
   - `eval --pbno <새 공고들> --out reports/extract-new.md`
   - 실패 징후 1이 「다시 잰다」면 `run --n 13`으로 5건 더 받아 같은 방식으로 `reports/extract-new2.md`를 쓰고 합친 수치를 PR 본문에 적는다
   - 이 Task 뒤로 `extract.py`의 프롬프트를 고치지 않는다. 고치면 `extract-new.md`를 무효로 적고 PR 본문 맨 위에 그 사실을 쓴다
9. **README** — 위 표의 내용. 판단 기록 절은 건드리지 않는다(PR 게이트에서 jw가 정한 뒤 채운다)

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 600 uv run python -m cheongyak_extract eval --pbno 2026000518 2026000530 2026000532 --out reports/extract-design.md; echo EXIT=$?` (캐시가 있으면 API를 안 부른다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~9가 전부 참이다. 9의 Actions는 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1~5를 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫)
- [ ] 틀리게 채운 칸 전부를 PR 본문 표로 적었다: 공고·필드·정답·추출값·원인(`LLM 오답`/`정규화`/`정답 쪽`)·근거가 된 PDF 원문 줄
- [ ] `reports/extract-design.md`·`reports/extract-new.md`가 커밋돼 있고 PR 본문에 두 표를 그대로 붙였다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(새 공고 맞음 n/m칸, `LLM 오답` k칸, 설계 3건 맞음 n/24)
- [ ] 프롬프트 고정 커밋(Task 7)이 새 공고 수집(Task 8)보다 앞이다. PR 본문에 두 커밋 해시를 적는다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있어 #146에서 끝나지 않고 세션을 붙잡았다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`(심볼릭 링크)와 `data/llm/`, `.env`를 커밋하지 않았다. API 키가 어떤 파일에도 들어가지 않았다(`git diff main...HEAD | grep -c sk-`가 0)
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#147] feature: extract()를 LLM 추출로 바꾸고 근거를 못 찾으면 비운다`
- [ ] Notion `PR` 프로퍼티를 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-81b8-9e3f-f954da162fc9 -
  ```
