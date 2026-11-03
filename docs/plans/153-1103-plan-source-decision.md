# #153 HTML과 PDF 중 어느 쪽 청약정보가 맞는지 jw가 가릴 수 있게 한다 (구현 계획)

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
> Never write the literal promise tag in prose (for example when saying you will NOT emit it). The
> stop hook reads the transcript and counts any occurrence of the tag as completion.

**Tier:** B — 새 명령 하나와 판정 파일·리포트·결정 기록. 기존 모듈(`truth_check`)을 재사용한다
**Notion:** #153 · **설계:** `docs/plans/153-1103-design-source-decision.md`
**흐름:** 이미 있다. 바꾸는 단계는 없고 측정 단계 하나(「판정 파일 만들기·집계」)를 더한다

## jw 기준

html로 측정한 청약정보와 pdf로 측정한 청약정보를 비교하고 두 방식의 우위를 가릴 수 있다

- 되물음(우위는 무엇으로 가리나)에 대한 jw 답: 「어느 쪽도 정답이라 확실할 수 없다면 어느 쪽이 맞는지는 내가 보고 판단하는 영역이 된다」

## 통과 기준

1. `judge-source` 명령(`__main__.py`)이 있다. 판정 파일 `labels/source-judge.json`이 없으면 만들고, 있으면 `jw` 칸을 덮어쓰지 않고 읽는다. 청약홈·OpenAI를 부르지 않는다
2. 판정 파일에 들어가는 칸 = 160칸 중 HTML 값·PDF 값(`labels/pdf-values-20.json`)·LLM 값이 정규화 뒤 하나라도 다른 칸. LLM 값은 `reports/extract-new.md` 「틀리게 채운 칸」 표에 있으면 그 값, 없으면 HTML 값과 같다고 본다(`truth_check.llm_values`, `run_check`가 읽는 방식 그대로)
3. 판정 파일의 칸마다 `pbno`·`field`·`html`·`pdf`·`quote`·`page`·`llm`·`jw`(null)·`jw_note`(null). `jw` 값은 `HTML`·`PDF`·`둘 다`·`둘 다 아님`·null만 받고, 그 밖의 값이면 에러다
4. 판정할 칸의 `quote`가 그 쪽 텍스트에 있는지 `extract.grounded`로 본다. 없는 칸은 리포트에 적고 종료 코드 1
5. `reports/source-judge.md`: 맨 위에 「세 값이 모두 같은 칸은 두 방식 모두 맞다고 본다」는 가정. 같은 칸 수/160, 판정할 칸 수/160, 판정할 칸 표(공고·필드·HTML 값·PDF 값·쪽·LLM 값·jw 판정), jw 판정별 칸 수(`판정 전` 포함). `판정 전`이 하나라도 있으면 「jw 판정 전」이라고 적고 방식별 합계를 쓰지 않는다. 다 차 있으면 방식별로 맞는 값을 가진 칸 수(같은 칸 + 그 방식 또는 `둘 다`로 판정한 칸)를 쓴다
6. 리포트에 「HTML에 없는 필드」 절: 전매제한 기간·거주지 우선 비율·신혼부부 소득 기준은 HTML 쪽 값이 없다(`truth.parse_truth`가 읽는 필드 목록으로 확인). PDF 쪽 숫자는 `reports/pdf-fields-tune-2.md`·`reports/pdf-resident-test.md`에서 출처와 함께 옮긴다
7. `docs/decision-source.md`: 정규식 대 LLM(#150), HTML 대 PDF(이번), PDF에만 있는 필드(#152) 세 결정을 사실과 출처(리포트 경로)로 적는다. 결정마다 「고른 방식과 이유 (jw)」 칸을 비워 둔다
8. README: `judge-source` 사용법과 jw가 판정 파일을 채우는 방법 한 단락
9. `uv run pytest` 통과, `uv run ruff check` 통과. 새 테스트는 `data/raw`를 읽지 않고 `tmp_path`·가짜 입력만 쓴다. 판정 파일이 있을 때 `jw` 칸을 보존하는 테스트, 잘못된 `jw` 값이 에러인 테스트, 판정 전/후 리포트 테스트를 포함한다

## 실패 징후

1. **jw 기준 — jw가 판정할 재료가 칸마다 갖춰졌나.** 잴 값: 판정할 칸 수, 그중 HTML 값·PDF 값·근거 줄·쪽·LLM 값 중 하나라도 빠졌거나 근거 줄이 그 쪽 텍스트에 없는 칸 수. 판정할 칸 목록이 착수 때 센 7칸(설계 §착수 때 확인한 사실 4)과 같은지. baseline 없음 — 첫 측정
   - 통과: 판정할 칸이 7칸으로 착수 때 목록과 같고, 재료가 빠지거나 근거 줄이 쪽에 없는 칸 0
   - 다시 잰다: 판정할 칸 목록이 착수 때 목록과 1~2칸 다르다. 다른 칸마다 왜 달라졌는지(정규화·LLM 값 읽기)를 리포트와 PR 본문에 적는다
   - 미완: 재료가 빠지거나 근거 줄이 쪽에 없는 칸이 1 이상, 목록이 3칸 이상 다르다, 또는 리포트가 없다
   - 우위 숫자 자체는 jw가 게이트에서 판정 파일을 채운 뒤 나온다. 루프는 `jw` 칸을 채우지 않는다
2. **표본 크기.** 판정할 칸이 160칸 중 몇 칸인지와, 그 칸이 어느 필드에 몰렸는지(필드별 칸 수)를 리포트에 적는다
3. **가정의 크기.** 「세 값이 모두 같은 칸」 수를 리포트 맨 위 가정 문장 옆에 적는다

## 파일

- `src/cheongyak_extract/truth_check.py`(판정 파일 만들기·읽기·집계를 여기 더한다), `__main__.py`
- `tests/test_truth_check.py`, `tests/test_main.py`
- `labels/source-judge.json`(새 파일, `jw` 칸은 null), `reports/source-judge.md`, `docs/decision-source.md`, `README.md`

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. 판정할 칸 고르기와 판정 파일 만들기·읽기(`jw` 보존, 값 검사) — 통과 기준 2·3
2. 근거 줄 검사와 리포트(판정 전/후, HTML에 없는 필드 절) — 통과 기준 4·5·6
3. `judge-source` 명령 — 통과 기준 1. 실제 `data/raw`로 돌려 `labels/source-judge.json`과 `reports/source-judge.md`를 만들고 커밋한다
4. `docs/decision-source.md`와 README — 통과 기준 7·8
5. Pre-PR checks, PR

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 120 uv run python -m cheongyak_extract judge-source --out /tmp/x.md; echo EXIT=$?` (청약홈·OpenAI를 부르지 않는다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~9가 전부 참이다. Actions는 PR을 연 뒤 `gh pr checks`로 확인한다. main과 충돌해 Actions가 안 돌면 충돌을 풀지 말고 그 사실을 PR 본문 맨 위에 적은 채 끝낸다
- [ ] 실패 징후 1~3을 측정해 값을 리포트와 PR 본문에 적었다. 1은 잰 값과 그 값이 든 구간 이름(통과·다시 잰다·미완)을 그대로 적고, 그 구간의 할 일을 했다. 판정은 jw 몫이다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문(되물음 답 포함) + 그 기준으로 잰 결과(판정할 칸 수와 재료가 빠진 칸 수). jw가 `labels/source-judge.json`의 `jw` 칸을 채운 뒤 `judge-source`를 다시 돌리면 우위 숫자가 나온다는 것을 적는다
- [ ] `labels/source-judge.json`의 `jw`·`jw_note` 칸이 모두 null이다
- [ ] 청약홈과 OpenAI를 부르지 않았다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`(심볼릭 링크)·`data/llm/`·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#153] feature: HTML과 PDF 중 어느 쪽 청약정보가 맞는지 jw가 판정할 파일과 집계를 더한다`
- [ ] Notion `PR` 프로퍼티를 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-8191-b1e5-d166a67d59df -
  ```
