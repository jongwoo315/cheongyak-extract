# #183 주소 정규화에서 쉼표와 괄호를 지우고 같은 값인지 본다 (구현 계획)

> **For Claude:** This plan is executed via /ralph-loop:ralph-loop in a detached orch session.
> You are ALREADY in the worktree, checked out on the feature branch. Do NOT switch branches,
> create another worktree, or use AskUserQuestion / any interactive prompt — the session is
> headless and cannot receive input, so always take the autonomous (recommended) default and
> keep working. Do NOT use superpowers:executing-plans or subagent-driven-development.
> Emit `<promise>RALPH_DONE</promise>` ONLY when every Done-criteria item and every Pre-PR check
> is genuinely true AND the PR has been created — never to escape the loop.
> Never write the promise tag in any other message, not even to say you will not emit it —
> the loop's stop hook can read an earlier message, so a mention ends the loop.
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

**Tier:** B — 정규화 함수 하나와 판정 파일 읽기 규칙. 판정 파일 처리가 jw가 쓴 칸을 다룬다
**Notion:** #183 · **설계:** `docs/plans/183-1105-design-address-punct.md`
**흐름:** 이미 있다. 바꾸는 단계는 「정규화」의 주소 규칙이다. 판정 파일 읽기(`judge-source`)는 그 결과를 받도록 고친다

## jw 기준

주소 정규화에서 쉼표와 괄호를 지우고 html과 pdf가 같은 값을 반환한다

## 통과 기준

1. `normalize("공급위치", v)`가 `(`·`)`·`,`를 공백으로 바꾼 뒤 공백을 한 칸으로 줄인다(설계 §설계 결정 1). 다른 종류(날짜·회사명 등)의 규칙은 바뀌지 않는다
2. 설계 표의 세 쌍(2026000443·2026000438·2026000437 공급위치)이 테스트에서 같은 값이 된다. 기존 테스트 `test_neighboring_blocks_in_one_address_stay_different`(AC3·AC4블록)는 그대로 통과한다
3. `judge-source`: 판정 파일에 있는데 이번에 안 고른 칸은 파일에 그대로 두고, 리포트에 「정규화로 같아져 판정할 칸에서 빠진 칸」 절로 칸마다 공고·필드·HTML 값·PDF 값·jw 판정을 적는다. 방식별 합계에서 그 칸은 세 값이 같은 칸으로 센다. 이번에 골랐는데 파일에 없는 칸, 같은 칸의 값이 jw가 본 값과 다른 칸은 지금처럼 에러다(설계 §설계 결정 2)
4. `labels/source-judge.json`의 내용이 바뀌지 않는다(`git diff main -- labels/source-judge.json`이 비어 있다)
5. 설계 §설계 결정 3 표의 리포트를 OpenAI·청약홈을 부르지 않고 다시 만들어 커밋한다. LLM 리포트(`extract-new.md`·`extract-tune*.md`)는 다시 만들지 않는다
6. `uv run pytest` 통과, `uv run ruff check` 통과. 새 테스트는 `data/raw`를 읽지 않고 `tmp_path`·가짜 입력만 쓴다. 3의 세 경우(빠진 칸 남김, 새 칸 에러, 값 바뀜 에러)를 각각 테스트한다

## 실패 징후

1. **jw 기준 — HTML과 PDF가 같은 값을 반환하나.** 잴 값: `check-truth`로 다시 만든 `reports/truth-check.md`에서 설계 표 세 칸이 「같은 칸」인지, 공급위치 같은 칸 수/20. 그리고 이번 변경으로 다름에서 같음으로 바뀐 칸 전부(`truth-check`·`regex-new`·`regex-tune`·`regex-more`)를 바꾸기 전·후 리포트에서 골라, 그 칸의 두 값이 쉼표·괄호·공백 말고 다른 글자가 있는지 본다. baseline: 세 칸 다름, 공급위치 17/20(지금 `reports/truth-check.md`)
   - 통과: 세 칸 모두 같은 칸이고, 공급위치 20/20이며, 다름에서 같음으로 바뀐 칸 모두 쉼표·괄호·공백만 다르다
   - 다시 잰다: 세 칸은 모두 같은데, 다름에서 같음으로 바뀐 칸 중 쉼표·괄호·공백 말고 다른 글자가 있는 칸이 1개 이상이다. 규칙을 넓히지 말고 그 칸을 리포트·PR 본문에 두 값과 함께 적는다
   - 미완: 세 칸 중 하나라도 다른 값으로 남거나, 공급위치가 20/20이 아니다(남은 칸이 무엇이고 왜인지 적는다)
2. **판정 파일.** 잴 값: `judge-source`의 판정할 칸 수, 빠진 칸 수, 방식별 합계. 착수 때 실측(설계 §착수 때 확인한 사실 2)과 #153 결과가 baseline이다
   - 기대: 판정할 칸 4, 빠진 칸 3(설계 표의 세 칸, jw 판정 모두 「둘 다」), 방식별 합계 HTML 159/160·PDF 159/160
   - 다르면 무엇이 다른지와 왜인지를 PR 본문에 적는다
3. **다른 숫자의 변화.** 다시 만든 리포트마다 바꾸기 전·후 숫자(같은 칸·맞은 칸 수)를 PR 본문 표에 적는다. 착수 때 실측: `truth-check` 155→158, 정규식 20건 공급위치 17→18, 정규식 100건 공급위치 그대로. LLM은 `extract-new.md` 「틀리게 채운 칸」 행을 새 정규화로 다시 맞춰 본 결과(같아지는 칸 수, 예상 2 → 맞은 칸 154→156)를 적는다. 리포트 파일은 고치지 않는다

## 파일

- `src/cheongyak_extract/normalize.py`(`_address`), `src/cheongyak_extract/truth_check.py`(`merge_judge`·`render_judge`·집계)
- `tests/test_normalize.py`, `tests/test_truth_check.py`
- `reports/truth-check.md`, `reports/source-judge.md`, `reports/regex-new.md`, `reports/regex-tune.md`, `reports/regex-more.md`, `reports/regex-vs-llm.md`, `reports/normalize.md`
- `docs/decision-source.md`·README의 숫자가 다시 만든 리포트와 달라지면 같이 고친다(`docs/decisions.md` 지난 행은 고치지 않는다)

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. 주소 규칙 — 통과 기준 1·2
2. 판정 파일에서 빠진 칸을 남기고 리포트에 적기 — 통과 기준 3·4
3. 리포트 다시 만들기 — 통과 기준 5. 리포트마다 바꾸기 전 숫자를 먼저 적어 두고 다시 만든다. 명령은 그 리포트를 처음 만든 plan(`docs/plans/14x-*-plan-*.md`·`150-*`)과 README에서 찾는다. `OPENAI_API_KEY`를 빼고(`env -u OPENAI_API_KEY`) 돌려서 OpenAI를 부르는 명령이면 멈추게 한다
4. 실패 징후 1~3 측정, Pre-PR checks, PR

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 120 uv run python -m cheongyak_extract judge-source --out /tmp/x.md; echo EXIT=$?` (청약홈·OpenAI를 부르지 않는다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~6이 전부 참이다. Actions는 PR을 연 뒤 `gh pr checks`로 확인한다. main과 충돌해 Actions가 안 돌면 충돌을 풀지 말고 그 사실을 PR 본문 맨 위에 적은 채 끝낸다
- [ ] 실패 징후 1~3을 측정해 값을 PR 본문에 적었다. 1은 잰 값과 그 값이 든 구간 이름(통과·다시 잰다·미완)을 그대로 적고, 그 구간의 할 일을 했다. 판정은 jw 몫이다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(세 칸이 같은 칸인지, 공급위치 같은 칸 수/20)
- [ ] `labels/source-judge.json`을 바꾸지 않았다
- [ ] 청약홈과 OpenAI를 부르지 않았다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`·`data/llm`(심볼릭 링크)·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#183] fix: 주소 정규화에서 쉼표와 괄호를 지우고 같은 값인지 본다`
- [ ] Notion `PR` 프로퍼티를 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40e41e61-65c0-81ca-a089-fcc202fc6853 -
  ```
