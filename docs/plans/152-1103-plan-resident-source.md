# #152 재시작 — 거주지 우선 비율을 PDF 안 같은 곳에서 읽는다 (구현 계획)

> **For Claude:** This plan is executed via /ralph-loop:ralph-loop in a detached orch session.
> You are ALREADY in the worktree, checked out on the feature branch. Do NOT switch branches,
> create another worktree, or use AskUserQuestion / any interactive prompt — the session is
> headless and cannot receive input, so always take the autonomous (recommended) default and
> keep working. Do NOT use superpowers:executing-plans or subagent-driven-development.
> Emit `<promise>RALPH_DONE</promise>` ONLY when every Done-criteria item and every Pre-PR check
> is genuinely true AND the PR has been created — never to escape the loop.
> RALPH_DONE means the work is finished, NOT that the result passed. If an honest measurement
> lands in a below-pass band of the plan (re-measure or 미완), and the plan step for that band has
> been carried out, write the band and the measured value verbatim in the report and at the top of
> the PR body, then emit RALPH_DONE. Judging the result is jw's call at the gate, not yours.
> Do not keep iterating to push a number over a threshold the plan's tasks no longer cover.
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
**설계:** /Users/jw/prv/.wt/152-pdf-only-fields-2/docs/plans/152-1103-design-resident-source.md (먼저 읽는다. 고르는 규칙 1~3, 값의 꼴과 계산, 새 재는 30건 뽑는 법이 거기 있다)
**이전 시도:** PR #9(반려). 이 브랜치는 그 브랜치 끝(`7896f34`)에서 시작했다. 그때 계획은 `docs/plans/152-1031-plan-pdf-only-fields.md`
**흐름:** 이미 있다(#146, PR #9의 `eval-pdf`). 바꾸는 곳: 거주지 우선 비율을 묻는 방법과 그 정답 검사. `run`·`eval` 8필드 흐름은 그대로

## jw 기준

llm이 거주지 우선 비율 계산과 거주지 정답을 소스별로 차이없이 통일되게 판정

- 되물음에 대한 jw 답: 「소스: 같은 공고 PDF 안에서 비율이 적힌 곳」

## 통과 기준

1. 일반공급 ①지역 묶음 찾기(`pdf_fields.py`): 쪽 텍스트 목록을 받아 설계 §고르는 규칙 1의 묶음 `(쪽 번호, 텍스트)` 또는 None을 돌려준다
   - 테스트: 한 PDF에 다자녀(50%)·노부모·일반공급 ①지역이 다 있으면 일반공급 것을 고른다(2026000449 꼴), 「■ ①지역」만 있는 줄 다음 줄까지 묶는다(2026000312 꼴), 「① 지역」·「2순위  :」 띄어쓰기, 「2순위」 줄이 없으면 None
   - `reports/pdf-labels.md`에 PDF 텍스트가 있는 149건 중 묶음을 찾은 공고 수를 적는다(설계 착수 때 main 세션이 센 값은 125)
2. 거주지 값의 꼴과 계산(설계 §값의 꼴과 계산)
   - 정규형에서 0%를 뺀다(`제주특별자치도 100% / 기타지역 0%` → `100`)
   - %의 합이 100이 아닌 값을 알아보는 함수. 정답에서는 검사에 걸리고, LLM 값에서는 리포트에 표시한다
3. 거주지 정답 검사(설계 §정답 검사에 더하는 것): 묶음이 있는 공고는 `quote`가 묶음 안에 있다, 꼴이 표대로다, 합이 100이다. 기존 검사 둘(쪽 텍스트에 `quote`가 있다, 숫자가 `quote`에 있다)은 그대로
4. 거주지를 따로 묻는다
   - 묶음이 있으면 그 묶음 텍스트만 LLM에 준다. 없으면 전체 텍스트와 설계 §고르는 규칙 2·3 순서를 준다. 결과마다 `출처`(`묶음` / `전체`)를 남긴다
   - 전매제한·신혼부부 소득 기준은 두 필드 묶음으로 전체 텍스트를 한 번에 묻는다
   - 8필드 프롬프트와 `OUTPUT_SCHEMA`는 그대로다(`tests/fixtures/llm/prompt.sha256`을 다시 만들지 않고 `tests/test_llm_replay.py`가 통과한다). 값을 남기는 조건은 C안 그대로
5. 정답 파일
   - `labels/pdf-only-50.json`: 기존 50건 150칸. 거주지 50칸을 3의 검사로 다시 보고 걸린 칸을 고친다. 고친 칸은 `note`에 이유를 적는다. 전매제한·신혼부부 칸은 바꾸지 않는다
   - `labels/pdf-resident-30.json`(새 파일): 설계 §재는 공고의 방법으로 뽑은 30건의 거주지 30칸. 형태 `{"test": [pbno 30개], "cells": {"<pbno>": {"거주지 우선 비율": {"value", "quote", "page", "note"}}}}`. 코드가 다시 뽑아 목록을 대조한다
6. `eval-pdf`
   - `--set tune`: 기존 50건, 세 필드
   - `--set test`: 새 30건, 거주지만
   - 리포트 맨 위: 지금처럼 칸 상태별 수와 %. 거주지는 `출처`별(`묶음` / `전체`)로 같은 수를 따로 센다
   - 맞지 않은 칸 표에 정답 근거 쪽, LLM 근거 쪽, `출처`, 「합 100 아님」 칸을 더한다
7. 리포트: `reports/pdf-labels.md`(두 정답 파일 요약 — 필드별 값 있는 칸·null 칸, 검사에 걸린 칸 수와 사유별 수, 거주지 정답이 고르는 규칙 1·2·3 중 어디서 왔는지 수), `reports/pdf-fields-tune-2.md`(다듬는 50건, 고칠 때마다 한 절), `reports/pdf-resident-test.md`(새 30건, 한 번). PR #9의 `reports/pdf-fields-tune.md`·`reports/pdf-fields-test.md`는 그대로 둔다(반려된 실행 기록)
8. `README.md`: 거주지 고르는 규칙 한 줄, 새 명령 사용법, 결과 한 줄. PR #9 결과 줄은 「반려된 첫 시도」로 남긴다
9. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green. 테스트는 `data/raw/`를 읽지 않고 OpenAI를 부르지 않는다

## 이번에 안 하는 것

- 전매제한·신혼부부 소득 기준의 정답·필드 설명 수정. 두 필드는 결과만 다시 재서 PR #9와 나란히 적는다
- 지역 이름 비교
- 묶음을 못 찾는 공고의 꼴을 코드로 더 찾는 것. `전체`로 따로 센다
- 재는 30건(새 30건)을 보고 프롬프트를 고치는 것
- `run` 기본 흐름에 세 필드를 넣는 것, 결정 기록(#153)

## 실패 징후

1. **jw 기준 — 정답과 LLM이 같은 곳에서 같은 값을 읽었나.** 잴 값: `reports/pdf-resident-test.md` 거주지 30칸의 「다른 값으로 채움」 수와 「비움」 수, `reports/pdf-labels.md`의 거주지 80칸(50 + 30) 중 검사에 걸린 칸 수. baseline: PR #9 재는 30건(이번과 다른 공고)에서 다른 값 6, 비움 4, 정답 꼴이 둘(37칸 대 3칸)
   - 통과: 다른 값 0, 비움 3 이하, 정답 검사에 걸린 거주지 칸 0
   - 다시 잰다: 다른 값 1~2, 또는 비움 4~6. 프롬프트는 고치지 않는다. 그 칸마다 정답 근거 쪽·LLM 근거 쪽·`출처`·LLM 값을 PR 본문 표로 적는다
   - 미완: 다른 값 3 이상, 비움 7 이상, 정답 검사에 걸린 거주지 칸이 1 이상 남음, 또는 재는 30건 점수가 없다(OpenAI 오류로 일부만 잰 경우 포함)
2. **`출처`별 결과.** 새 30건 중 `전체` 칸 수와 그 칸의 맞음 수. `전체` 칸이 0이면 그 사실을 적는다 — 그때 1의 결과는 묶음을 찾은 공고에서만 잰 것이다
3. **전매제한·신혼부부가 PR #9와 달라졌나.** 기존 50건에서 두 필드의 맞음 수를 PR #9(다듬는 20건 + 재는 30건 합: 전매제한 47/47, 신혼부부 40/46)와 나란히 적는다. 한 필드에서 맞음이 2칸 이상 줄면 줄어든 칸을 표로 적는다
4. **순서.** (a) `labels/pdf-resident-30.json` 첫 커밋 < `reports/pdf-resident-test.md` 첫 커밋, (b) 거주지 프롬프트 고정 커밋 < `reports/pdf-resident-test.md` 첫 커밋. 해시로 적는다
5. **다듬는 50건과 재는 30건의 차이.** 거주지 맞음 비율 차이. 10%p 미만이면 적어 둔다 / 10~20%p면 `출처`별로 적는다 / 20%p 이상이면 다듬는 공고에 맞춘 문장이 프롬프트에 있는지 점검해 PR 본문에 적는다

## 파일

- `src/cheongyak_extract/pdf_fields.py`, `__main__.py`
- `tests/test_pdf_fields.py`, `tests/test_main.py`
- `labels/pdf-only-50.json`(거주지 칸만), `labels/pdf-resident-30.json`(새 파일)
- `reports/pdf-labels.md`, `reports/pdf-fields-tune-2.md`, `reports/pdf-resident-test.md`, `README.md`

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. **일반공급 ①지역 묶음 찾기** — 통과 기준 1. 테스트는 쪽 텍스트를 문자열로 만들어 준다
2. **꼴·계산·정답 검사** — 통과 기준 2·3. 걸리는 칸과 안 걸리는 칸을 fixture로 준다(0% 지역, 합 150, 묶음 밖 `quote`)
3. **거주지 따로 묻기와 `eval-pdf` 두 묶음** — 통과 기준 4·6. 가짜 ask로: 묶음이 있으면 거주지 프롬프트에 묶음 텍스트만 들어간다, 없으면 전체 텍스트와 규칙 2·3이 들어간다, 두 필드 호출에 거주지 설명이 없다, 리포트에 `출처`별 수와 「합 100 아님」이 나온다
4. **정답** — 통과 기준 5. 이 Task 동안 LLM 추출을 돌리지 않는다. (a) 기존 50건 거주지 칸을 새 검사로 돌려 걸린 칸을 PDF 텍스트를 다시 읽고 고친다 (b) 새 30건을 뽑아 거주지 정답을 적는다. 고르는 규칙 1이 있는 공고는 그 묶음에서 읽는다. `check-pdf-labels`가 두 파일을 같이 검사해 걸린 칸 0이 될 때까지 고친다. 정답 파일 둘과 `reports/pdf-labels.md`를 커밋한다
5. **다듬기** — `eval-pdf --set tune --out reports/pdf-fields-tune-2.md`. 거주지 설명은 최대 2번 고친다. 고칠 때마다 리포트에 한 절(바꾼 문장, 점수). 정답 `value`를 LLM 값에 맞춰 바꾸지 않는다 — 정답이 틀렸다고 보이면 PDF를 다시 읽고 `note`에 이유를 적는다. 마지막에 프롬프트와 리포트를 커밋한다(이 커밋이 고정 시점)
6. **재는 30건** — `eval-pdf --set test --out reports/pdf-resident-test.md`를 한 번. 이 뒤로 거주지 설명을 고치지 않는다. 리포트를 커밋한다. 결과가 실패 징후 1의 어느 구간이든 그 구간의 할 일을 하고 다음 Task로 간다
7. **README** — 통과 기준 8

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 300 uv run python -m cheongyak_extract eval-pdf --set test --out /tmp/x.md; echo EXIT=$?` (캐시가 있어 OpenAI를 다시 부르지 않는다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~9가 전부 참이다. 9의 Actions는 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1~5를 측정해 값을 리포트와 PR 본문에 적었다. 1은 잰 값과 그 값이 든 구간 이름(통과·다시 잰다·미완)을 그대로 적고, 그 구간의 할 일을 했다. 판정은 jw 몫이다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문(되물음 답 포함) + 그 기준으로 잰 결과(새 30건 거주지의 맞음·비움·다른 값, `출처`별 수, 거주지 정답 80칸 중 검사에 걸린 칸 수). 정답은 jw가 아니라 구현 루프가 PDF를 읽어 적었다는 사실을 같이 적는다
- [ ] PR 본문에 jw가 확인할 거주지 정답 10칸 표: 두 정답 파일의 거주지 80칸 중 `random.Random(1523)`로 뽑는다. 공고·`value`·쪽·`quote`·고르는 규칙 1/2/3
- [ ] 청약홈을 부르지 않았다. OpenAI는 `eval-pdf`로만 불렀다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`(심볼릭 링크)·`data/llm/`·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#152] feature: 거주지 우선 비율을 PDF 안 같은 곳에서 읽고 PDF에만 있는 필드 3개를 잰다`. 본문에 반려된 PR #9 링크와, 이 브랜치가 그 위에서 시작했다는 사실을 적는다
- [ ] Notion `PR` 프로퍼티를 새 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-81bd-a972-d050d6575212 -
  ```
