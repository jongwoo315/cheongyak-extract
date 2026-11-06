# #179 일반공급 ①지역 줄 찾기를 고쳐 거주지 질문에 PDF 전체를 넘기지 않는다 (구현 계획)

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

**Tier:** B — 묶음 찾기 함수 하나지만 규칙 2개를 더하고 LLM 설명이 묶음 종류마다 갈린다. LLM을 다시 잰다
**Notion:** #179 · **설계:** `docs/plans/179-1105-design-resident-block.md`
**흐름:** 이미 있다. 바꾸는 단계는 「PDF 전용 필드 추출」의 거주지 묶음 고르기(`resident_block`)와 그 묶음을 묻는 설명이다

## RESUME — 반려 뒤 재작업 (2026-11-06)

jw가 PR #14를 반려했고 같은 PR에서 고치기로 정했다. **이 절이 이번 실행의 범위다.** 아래 Task R1~R5만 한다. 이미 있는 커밋(`e5b3a64`~`04dd790`)과 리포트를 처음부터 다시 만들지 않는다. 파일이 있다고 통과로 치지 않고 테스트와 측정으로 확인한다. 새 PR을 만들지 않고 PR #14에 push한다.

### 반려 뒤 jw 기준

전반적으로 거주지 정보를 잘 찾지만 2026000184에 세 규칙이 찾는 줄이 없음, 이 이슈 개선하는 로직 필요

### main이 확인한 사실

- 2026000184는 71쪽 전부 90도 회전돼 있다(`page.rotation`). 149건 중 회전된 쪽이 있는 공고는 이 한 건이다
- PDF 21쪽 이미지에 「2순위 : ①지역 → ②추첨」과 「■ ①지역 : 해당지역 거주자(익산시 거주자) → 기타지역 거주자(전북특별자치도 거주자)」가 그대로 있다. 「텍스트가 뒤섞여 세 규칙의 줄이 없다」는 설명은 틀렸다. 뽑은 글자의 순서가 어긋났을 뿐이다
- scratchpad 시험: 쪽마다 `page.remove_rotation()`을 부른 뒤 `get_text(sort=True)`로 뽑으면 지금 `resident_block`이 21쪽 규칙 1 묶음을 찾는다
- `pdf_text.pages`를 쓰는 리포트 중 이 공고가 든 것: `regex-more.md`, `pdf-labels.md`, `pdf-fields-tune-2.md`. 8필드 LLM 리포트(`extract-new`·`extract-tune`)에는 없다

### 통과 기준 (재작업)

- R1. `pdf_text.pages`가 회전된 쪽의 회전을 풀고 텍스트를 뽑는다. 회전된 쪽을 가짜 PDF로 만든 테스트가 있다(`tmp_path`, `data/raw`를 읽지 않는다). 바꾸기 전·후로 149건의 쪽 텍스트를 비교해 바뀐 공고가 2026000184 하나뿐인지 스크립트로 확인해 PR 본문에 적는다
- R2. `labels/pdf-only-50.json`의 2026000184 세 칸(전매제한 기간·거주지 우선 비율·신혼부부 소득 기준)을 회전을 푼 텍스트에서 읽어 값·근거 줄·쪽·note로 채운다. **LLM을 다시 돌리기 전에 이 커밋을 먼저 만든다.** 커밋 순서가 LLM 값을 보지 않고 적었다는 증거다. 찾아봐도 그 필드가 PDF에 없으면 null로 두고 찾아본 쪽을 note에 쓴다. 이 세 칸 말고 정답 파일의 다른 칸은 바꾸지 않는다
- R3. 묶음 끝 판정: 줄 처음의 머리 기호에 더해 줄 중간의 `■`에서도 묶음을 끝낸다(이전 코드의 `"■" in rest`와 같은 동작). 테스트가 있다. 2026000293 묶음이 다시 26줄이 되는지 확인한다. 이 변경 전·후로 149건 묶음을 비교해 글이 달라진 공고 목록을 PR 본문에 적는다
- R4. `check-pdf-labels`, `eval-pdf --set tune`, `eval-pdf --set test`를 다시 돌리고 `regex-more.md`·`regex-vs-llm.md`도 다시 만든다(README의 명령). LLM 설명은 고치지 않는다
- R5. 설계 문서·README·`docs/concepts.md`에서 2026000184를 「텍스트 뒤섞임」으로 적은 곳을 고친다. 지난 행(`docs/decisions.md`의 PR 게이트 기록)은 고치지 않는다
- `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` 통과

### 실패 징후 (재작업)

1. **jw 기준.** 잴 값: PDF 전체를 넘기는 공고 수/149와 2026000184의 묶음(쪽·규칙·첫 줄). baseline: 1건(2026000184)
   - 통과: 0건이고 2026000184 묶음이 21쪽 규칙 1이며 「익산시」가 들어 있다
   - 다시 잰다: 0건인데 2026000184 묶음이 21쪽 규칙 1이 아니다. 고른 자리와 PDF 21쪽 줄을 나란히 리포트에 적는다
   - 미완: 1건 이상
2. **회전 처리의 영향.** 잴 값: 쪽 텍스트가 바뀐 공고 수. 기대 1(2026000184). 다르면 공고마다 무엇이 바뀌었는지 PR 본문에 적는다. 정규식 100건(`regex-more.md`)의 바꾸기 전·후 맞은 칸 수를 같이 적는다
3. **묶음 밖 칸.** 잴 값: `QUOTE_OUTSIDE_BLOCK` 칸 수. baseline: 1칸(2026000116)
   - 정상: 1칸 이하
   - 다시 본다: 2칸. 늘어난 칸의 묶음과 정답 근거 줄을 나란히 적는다. 정답을 고치지 않는다
   - 미완: 3칸 이상
4. **LLM 값.** 잴 값: 거주지 맞은 칸. baseline: 다듬는 50건 값 있는 49칸 중 49, 재는 30건 30/30. 2026000184가 값 있는 칸이 되면 다듬는 50건의 분모가 50이 된다
   - 정상: 다듬는 쪽 틀린 칸 0~1이고 재는 30건 29 이상
   - 다시 잰다: 어느 쪽이든 2칸 틀렸다. 그 칸의 묶음 규칙·LLM 값·정답을 리포트에 적는다
   - 미완: 어느 쪽이든 3칸 이상 틀렸다
   - 2026000184의 전매제한·신혼부부 소득 기준 칸의 LLM 값과 정답도 PR 본문에 적는다. 재는 30건을 이번 재작업에서 다시 측정한 사실과 이유(2026000293 입력이 바뀜)를 `reports/pdf-resident-test.md`와 PR 본문에 적는다

### Tasks (재작업, Task 하나 = 커밋 하나)

- R1 회전 풀기(테스트 먼저) → R2 정답 세 칸 → R3 묶음 끝 판정(테스트 먼저) → R4 측정·리포트 → R5 문서, Pre-PR checks, PR 본문 고치기
- OpenAI는 R4에서만 부른다. `data/raw`는 읽기만 한다

### Done criteria (재작업)

- [ ] 통과 기준 R1~R5가 전부 참이다. 실패 징후 1~4를 측정해 값과 구간 이름을 그대로 PR 본문에 적었다. 판정은 jw 몫이다
- [ ] `gh pr edit 14 --body-file`로 PR 본문을 고쳤다. 맨 위 `## 착수 전 기준 (jw)` 절에 처음 기준 원문과 **반려 뒤 jw 기준 원문**을 둘 다 두고 그 기준으로 잰 결과를 적는다. 그 아래 `## 반려 뒤 재작업` 절에 R1~R5와 측정값을 적는다
- [ ] `git diff main -- labels/` 변경은 `labels/pdf-only-50.json`의 2026000184 세 칸뿐이다
- [ ] 청약홈을 부르지 않았다. 새 PR을 만들지 않았다. 아래 원래 Done criteria 중 PR 만들기와 Notion 갱신은 이미 끝났다. 나머지(커밋 메시지·`ls`·merge 금지·add 지정·API 키)는 그대로 지킨다
- [ ] CI는 push 뒤 `gh pr checks 14`로 확인한다. Pre-PR checks를 다시 돌려 출력을 보인다

---

아래는 처음 실행의 plan이다. 재작업과 어긋나면 위 RESUME 절을 따른다. 예: 「정답 파일을 바꾸지 않는다」는 2026000184 세 칸만 예외이고, 「재는 30건 한 번」은 이번에 한 번 더 잰다.

## jw 기준

llm이 '일반공급 1지역'을 찾는 로직 개선이 필요하며, 이를 통해서 '거주지 llm 질문'에 pdf전체를 던지는 일이 없다

## 통과 기준

1. 규칙 1(일반공급 ①지역 묶음)이 설계 §설계 결정 1의 꼴을 받는다: `2순위 : [ ① 지역 …` 순위 줄, 머리 기호가 `■`가 아니거나 없는 ①지역 줄, 순위 줄과 ①지역 줄이 쪽을 넘는 경우, 쪽을 넘어 이어지는 묶음. 꼴마다 테스트가 있다
2. 규칙 1이 없으면 규칙 2(지역우선 공급기준 표), 그것도 없으면 규칙 3(해당지역 우선 문장)으로 묶음을 만든다(설계 §설계 결정 2). `Block`에 `rule`(1·2·3)이 있다. 다른 쪽을 가리키는 안내 문장은 규칙 2 제목으로 잡지 않는다. 규칙마다 테스트가 있다
3. 지금 묶음을 찾는 125건은 계속 규칙 1로 찾고 묶음의 쪽 번호가 바뀌지 않는다(바꾸기 전·후를 스크립트로 비교해 바뀐 공고 수를 PR 본문에 적는다. 묶음 끝이 늘어난 공고는 따로 센다)
4. 거주지 LLM 질문은 묶음 규칙마다 설명을 따로 쓴다(설계 §설계 결정 3). 세 규칙 다 못 찾으면 지금처럼 PDF 전체를 넘긴다
5. `check-pdf-labels`를 다시 돌려 `reports/pdf-labels.md`를 고친다. 고르는 규칙별 칸 수 표는 이제 코드가 고른 규칙으로 센다
6. `eval-pdf --set tune`(다듬는 50건)과 `eval-pdf --set test`(재는 30건)를 다시 돌려 `reports/pdf-fields-tune-2.md`·`reports/pdf-resident-test.md`를 고친다. 리포트의 출처 표가 `묶음(규칙 1)`·`묶음(규칙 2)`·`묶음(규칙 3)`·`전체`로 나뉜다
7. `docs/concepts.md`를 만들고 거주지 묶음 규칙 1·2·3 표를 둔다(이름 · 뜻 한 줄 · 정의한 파일·줄 · 만든 티켓). README의 거주지 설명·숫자가 새 리포트와 다르면 같이 고친다
8. `uv run pytest` 통과, `uv run ruff check`·`uv run ruff format --check` 통과. 새 테스트는 `data/raw`를 읽지 않고 가짜 쪽 텍스트만 쓴다

## 실패 징후

1. **jw 기준 — 거주지 질문에 PDF 전체를 넘기는 공고가 없나.** 잴 값: PDF 텍스트가 있는 공고 149건 중 세 규칙 모두 묶음을 못 찾아 PDF 전체를 넘기는 공고 수(`reports/pdf-labels.md`에 줄로 적는다). baseline: 24건(지금 `reports/pdf-labels.md` 「묶음을 찾은 공고 125건」)
   - 통과: 0건
   - 다시 잰다: 1~2건이고, 남은 공고 모두 PDF 텍스트에 세 규칙의 어느 줄도 없다(정규식으로 찾아 보고 없음을 리포트에 적는다). 그때 할 일: 남은 공고마다 `pdf_text.pages(..., sort=False)` 텍스트로도 세 규칙을 찾아 결과를 리포트에 적는다. 규칙을 그 공고에 맞춰 더 넓히지 않는다
   - 미완: 3건 이상, 또는 남은 공고 중 하나라도 텍스트에 세 규칙의 줄이 있는데 못 찾았다
   - 착수 때 실측: 2026000184는 텍스트가 뒤섞여 세 규칙의 줄이 없을 공산이 크다(설계 §착수 때 확인한 사실 3)
2. **코드가 고른 자리가 맞나.** 잴 값: `check-pdf-labels`에서 정답 근거 줄이 묶음 밖에 있는 칸(`QUOTE_OUTSIDE_BLOCK`) 수. 특히 지금 못 찾는 24건 중 정답이 있는 15건. baseline: 검사에 걸린 칸 0
   - 정상: 0칸
   - 다시 본다: 1~2칸. 칸마다 묶음의 쪽·규칙과 정답의 쪽·근거 줄을 리포트에 나란히 적는다. 정답을 고치지 않는다
   - 미완: 3칸 이상
3. **LLM 거주지 값이 나빠지지 않았나.** 잴 값: 거주지 맞은 칸. baseline: 다듬는 50건 값 있는 49칸 중 48, 재는 30건 30칸 중 29
   - 정상: 다듬는 48 이상이고 재는 29 이상
   - 다시 잰다: 어느 쪽이든 1칸 줄었다. 그 칸의 묶음 규칙·LLM 값·정답을 리포트에 적는다
   - 미완: 어느 쪽이든 2칸 이상 줄었다
   - 설명은 다듬는 50건 결과로만 고친다(최대 2번, 고칠 때마다 리포트 「거주지 설명을 고친 기록」에 적는다). 재는 30건은 설명을 고정한 뒤 한 번만 잰다

## 파일

- `src/cheongyak_extract/pdf_fields.py`(`resident_block`·`Block`·`RESIDENT_*_SET`·`_extract_notice`·`_resident_rule`·리포트 출처 표)
- `tests/test_pdf_fields.py`(없으면 기존 PDF 필드 테스트 파일을 찾아 거기에)
- `reports/pdf-labels.md`, `reports/pdf-fields-tune-2.md`, `reports/pdf-resident-test.md`
- `docs/concepts.md`(새로), README

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. 규칙 1 꼴 넓히기 — 통과 기준 1. 바꾸기 전 149건의 묶음(쪽·첫 줄)을 scratchpad에 먼저 떠 둔다(통과 기준 3 비교용)
2. 규칙 2·3 묶음과 `Block.rule` — 통과 기준 2·3
3. 규칙별 LLM 설명과 정답 검사 — 통과 기준 4·5. `check-pdf-labels` 다시 돌리기(OpenAI 안 부름). 실패 징후 1·2 측정
4. LLM 다시 측정 — 통과 기준 6. 다듬는 50건 → (필요하면 설명 고침, 최대 2번) → 재는 30건 한 번. 실패 징후 3 측정. OpenAI는 이 Task에서만 부른다
5. `docs/concepts.md`·README, Pre-PR checks, PR — 통과 기준 7·8

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 120 uv run python -m cheongyak_extract check-pdf-labels --out /tmp/x.md; echo EXIT=$?` (청약홈·OpenAI를 부르지 않는다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~8이 전부 참이다. Actions는 PR을 연 뒤 `gh pr checks`로 확인한다. main과 충돌해 Actions가 안 돌면 충돌을 풀지 말고 그 사실을 PR 본문 맨 위에 적은 채 끝낸다
- [ ] 실패 징후 1~3을 측정해 값을 PR 본문에 적었다. 잰 값과 그 값이 든 구간 이름을 그대로 적고, 그 구간의 할 일을 했다. 판정은 jw 몫이다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(PDF 전체를 넘기는 공고 수/149, 남은 공고 번호와 이유)
- [ ] 정답 파일(`labels/pdf-only-50.json`·`labels/pdf-resident-30.json`)을 바꾸지 않았다(`git diff main -- labels/`가 비어 있다)
- [ ] 청약홈을 부르지 않았다. OpenAI는 Task 4의 `eval-pdf` 두 번(설명을 고치면 그만큼 더)에서만 불렀다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`·`data/llm`(심볼릭 링크)·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#179] fix: 일반공급 ①지역 줄 찾기를 고쳐 거주지 질문에 PDF 전체를 넘기지 않는다`
- [ ] Notion `PR` 프로퍼티를 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40d41e61-65c0-8140-b6ba-e489bc7a5061 -
  ```
