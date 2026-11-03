# #152 PDF에만 있는 필드 3개를 수동 정답 50건으로 잰다 — 구현 계획

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
**Notion:** #152 https://app.notion.com/p/40441e6165c081bda972d050d6575212
**설계:** /Users/jw/prv/.wt/152-pdf-only-fields/docs/plans/152-1031-design-pdf-only-fields.md (먼저 읽는다. 필드 3개의 뜻과 정규형, 공고 50건 고르는 법, 정답을 적는 규칙과 검사 둘이 거기 있다)
**흐름:** 이미 있다(#146). 이 티켓은 `run`·`eval` 8필드 흐름을 바꾸지 않는다. 같은 추출 코드에 필드 묶음 하나를 더하고, 정답을 HTML 대신 정답 파일에서 읽는 명령(`eval-pdf`)을 더한다. 바꾸는 stub 없음

## jw 기준

pdf에 있는 필드 3개애 대한 수동 정답이 나오고 점수도 계산한다

## 통과 기준

1. `labels/pdf-only-50.json`: 공고 50건 × 필드 3개(`전매제한 기간`·`거주지 우선 비율`·`신혼부부 소득 기준`) = 150칸
   - 형태: `{"tune": [pbno 20개], "test": [pbno 30개], "cells": {"<pbno>": {"<필드>": {"value": str|null, "quote": str|null, "page": int|null, "note": str|null}}}}`
   - `tune`·`test`는 설계 §공고 50건의 고르는 법으로 뽑은 것과 같아야 한다(코드가 다시 뽑아 대조한다)
   - 값이 null인 칸은 `note`에 찾아본 쪽을 적는다
2. 정답 검사(`src/cheongyak_extract/pdf_fields.py`, 새 파일)
   - 칸이 150개가 아니거나 공고·필드가 빠지면 에러
   - 값이 있는 칸마다 설계 §수동 정답의 검사 둘: `quote`가 그 쪽 텍스트에 있다(`extract.grounded`, 쪽 텍스트는 `pdf_text.pages(path)`), 정규형의 숫자가 `quote`에 있다(설계의 예외 둘 포함)
   - 정규형 함수 셋은 설계 표 그대로. `normalize.py`의 기존 함수는 바꾸지 않는다
3. 세 필드 LLM 추출
   - `extract`·`llm`이 필드 묶음(필드 이름, 설명, 응답 모양)을 인자로 받는다. 기본값은 지금 8필드다
   - **8필드 프롬프트 글자와 `OUTPUT_SCHEMA`가 그대로다** — `tests/fixtures/llm/prompt.sha256`을 다시 만들지 않고 `tests/test_llm_replay.py`가 통과한다
   - 값을 남기는 조건은 C안(`DEFAULT_RULE`)
4. `eval-pdf` 하위 명령: `--set tune|test`, `--out`. 정답 파일과 `data/raw/`를 읽고 LLM을 부른다(캐시 `data/llm/`). 청약홈에 요청하지 않는다
   - 리포트 맨 위: 정답에 값이 있는 칸 중 맞음 / 비움 / 다른 값으로 채움(수와 %), 정답이 null인 칸 중 비움 / 값을 채움
   - 필드별 같은 네 수
   - 맞지 않은 칸 전부: 공고·필드·정답 값·LLM 값·LLM 근거 쪽
   - 입력 토큰 합계
5. 리포트: `reports/pdf-fields-tune.md`(다듬는 20건, 프롬프트 수정마다 한 절), `reports/pdf-fields-test.md`(재는 30건, 한 번), `reports/pdf-labels.md`(정답 파일 요약: 필드별 값 있는 칸·null 칸, 검사 둘에 걸린 칸 수, 주택형마다 전매제한이 달라 `,`로 이은 칸 수)
6. `README.md`에 `eval-pdf` 사용법, 필드 3개의 뜻 한 줄씩, 결과 한 줄
7. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green. 테스트는 `data/raw/`를 읽지 않고 OpenAI를 부르지 않는다(가짜 ask와 테스트 안에서 만든 PDF)

## 이번에 안 하는 것

- 신혼부부 외 소득 기준, 일반공급 외 거주지 비율, 거주의무기간·재당첨제한
- 정규식 baseline, T1
- 8필드 프롬프트·`normalize.py` 기존 함수·`labels/pdf-values-20.json`·기존 리포트 수정
- `run` 기본 흐름에 세 필드를 넣는 것
- 50건 밖의 공고, 결정 기록(#153)

## 실패 징후

1. **jw 기준 — 수동 정답이 나오고 점수가 계산됐나.** 잴 값: `reports/pdf-labels.md`의 칸 수·검사에 걸린 칸 수, `reports/pdf-fields-test.md` 맨 위 점수. 점수의 높낮이는 기준이 아니다. baseline 없음 — 이번이 첫 측정이다
   - 통과: 정답 150칸이 모두 있고, 값이 있는 칸 중 검사 둘에 걸린 칸 0, 재는 30건 90칸의 점수와 필드별 표가 리포트에 있다
   - 다시 잰다: 검사에 걸린 칸이 1칸 이상. 그 칸의 `quote`·`page`를 PDF 텍스트에서 다시 복사해 고친다. `value`를 바꿔야 하면 PDF를 다시 읽고 바꾼 이유를 `note`에 적는다. 두 번째에도 남으면 그 칸 목록을 PR 본문에 적는다
   - 미완: 정답 공고가 50건 미만이거나, 재는 30건 점수가 없거나(OpenAI 오류로 일부만 잰 경우 포함), 아래 3의 커밋 순서가 반대다
2. **정답이 null인 칸.** 한 필드에서 25칸 이상(50건의 절반)이면 그 필드 정의가 이 공고들에 안 맞는다는 뜻이라 PR 본문에 그 필드의 null 칸 `note`를 표로 적는다
3. **순서.** (a) 정답 파일 첫 커밋 < 세 필드 LLM 첫 실행 리포트(`reports/pdf-fields-tune.md`) 첫 커밋, (b) 고정 프롬프트 커밋 < `reports/pdf-fields-test.md` 첫 커밋. 둘 다 해시로 적는다
4. **다듬는 20건과 재는 30건의 차이.** 정답에 값이 있는 칸의 맞음 비율 차이. 10%p 미만이면 적어 둔다 / 10~20%p면 필드별로 적는다 / 20%p 이상이면 다듬는 공고에 맞춘 문장이 프롬프트에 있는지 점검해 PR 본문에 적는다
5. **정답이 null인데 LLM이 값을 채운 칸.** 재는 30건에서 수를 적고 칸마다 LLM 값·근거 쪽을 적는다. baseline 없음

## 파일

- `labels/pdf-only-50.json`(새 파일)
- `src/cheongyak_extract/pdf_fields.py`(새 파일), `extract.py`·`llm.py`(필드 묶음 인자), `__main__.py`(`eval-pdf`)
- `tests/test_pdf_fields.py`(새 파일), `tests/test_extract.py`·`tests/test_llm.py`·`tests/test_main.py`
- `reports/pdf-labels.md`, `reports/pdf-fields-tune.md`, `reports/pdf-fields-test.md`, `README.md`

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. **필드 묶음 인자** — 통과 기준 3의 앞 두 줄. `extract`·`build_prompt`·`llm.LlmAsk`가 필드 묶음을 받는다. 테스트: 8필드 기본 호출의 프롬프트·스키마가 바뀌지 않았다(`prompt.sha256` 그대로), 다른 묶음을 주면 그 필드만 응답 모양에 있다
2. **세 필드 정의·정규형·정답 검사·50건 고르기** — 통과 기준 2와 설계 §필드 3개의 뜻. 정규형 예: `3년`→`36`, `6개월`→`6`, `없음`→`0`, `평택시 30% / 경기도 20% / 기타 50%`→`30/20/50`, `100% (맞벌이 120%)`→`100/120`. 검사 둘에 걸리는 칸과 안 걸리는 칸을 fixture로 준다
3. **`eval-pdf` 명령과 리포트** — 통과 기준 4. 가짜 ask로 칸 상태 다섯(맞음·비움·다른 값·null에 비움·null에 채움)이 모두 나오는 테스트
4. **정답 150칸 적기** — 통과 기준 1. 이 Task 동안 세 필드 LLM 추출을 돌리지 않는다. PDF 텍스트는 `pdf_text.pages`로 뽑아 읽는다. 정답 검사를 돌려 걸린 칸을 고친 뒤 `labels/pdf-only-50.json`과 `reports/pdf-labels.md`만 커밋한다
5. **프롬프트 다듬기** — `eval-pdf --set tune`. 맞지 않은 칸을 보고 세 필드 설명을 고친다. 최대 3번, 고칠 때마다 `reports/pdf-fields-tune.md`에 한 절(바꾼 문장, 점수). 정답 `value`를 LLM 값에 맞춰 바꾸지 않는다 — 정답이 틀렸다고 보이면 PDF를 다시 읽고 `note`에 이유를 적는다. 마지막에 프롬프트와 리포트를 커밋한다(이 커밋이 고정 시점)
6. **재는 30건** — `eval-pdf --set test --out reports/pdf-fields-test.md`를 한 번. 이 뒤로 세 필드 설명을 고치지 않는다. 리포트를 커밋한다
7. **README** — 통과 기준 6

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 300 uv run python -m cheongyak_extract eval-pdf --set test --out /tmp/x.md; echo EXIT=$?` (캐시가 있어 OpenAI를 다시 부르지 않는다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~7이 전부 참이다. 7의 Actions는 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1~5를 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫). 3은 커밋 해시 넷을 적는다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(정답 칸 수·null 칸 수·검사에 걸린 칸 수, 재는 30건 점수). 정답은 jw가 아니라 구현 루프가 PDF를 읽어 적었다는 사실을 같이 적는다
- [ ] PR 본문에 jw가 확인할 정답 10칸 표(설계 §수동 정답: `random.Random(1520)`로 값이 있는 칸에서 뽑는다). 공고·필드·`value`·쪽·`quote`
- [ ] 청약홈을 부르지 않았다. OpenAI는 `eval-pdf`로만 불렀다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있어 #146에서 끝나지 않고 세션을 붙잡았다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`(심볼릭 링크)·`data/llm/`·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#152] feature: PDF에만 있는 필드 3개를 수동 정답 50건으로 잰다`
- [ ] Notion `PR` 프로퍼티를 새 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-81bd-a972-d050d6575212 -
  ```
