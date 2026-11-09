# #184 거주지 묶음 규칙 1 길이 상한 · 규칙 3 일반공급 절 한정 (구현 계획) <!-- style-exempt -->

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

**Tier:** B — 함수 두 개(`_block_rule_1`·`_block_rule_3`)의 조건을 바꾼다. 바뀌는 공고는 적지만 LLM 입력이 바뀌는 공고(2026000293, 재는 30건)가 있어 다시 잰다
**Notion:** #184 · **설계:** `docs/plans/184-1109-design-resident-bound.md` (먼저 읽는다. 「착수 때 확인한 사실」이 측정의 기준값이다)
**흐름:** 이미 있다. 바꾸는 단계는 「PDF 전용 필드 추출」의 거주지 묶음 고르기(`resident_block`) 중 규칙 1·규칙 3

## jw 기준

일반지역 지역 묶음을 찾는데 길이상한이 생긴다, 해당지역 거주자 우선 문장을 정확한 위치에서 찾는다 <!-- style-exempt -->

- 「일반지역 지역 묶음」 = 규칙 1(일반공급 ①지역 묶음). 「정확한 위치」 = 그 공고의 일반공급 절 안(설계 §jw 기준)

## 통과 기준

1. 규칙 1 묶음은 ①지역 줄부터 글이 든 줄 5개를 넘지 않는다(빈 줄은 안 센다). 끝 줄(줄 처음의 머리 기호·줄 중간 `■`·`②`가 든 줄)이 먼저 나오면 지금처럼 거기서 끝난다. 상한에 걸려도 규칙 1 묶음으로 쓴다(규칙 2·3으로 넘기지 않는다). 테스트: 끝 줄 없이 글이 든 줄 8개가 이어지는 가짜 쪽에서 묶음이 글이 든 줄 5개다 <!-- style-exempt -->
2. 규칙 3은 문서에서 처음 나온 일반공급 절 제목 줄 아래에서만 문장을 찾는다(쪽을 넘어 찾는다). 제목 줄보다 앞의 문장은 쓰지 않는다. 제목 줄이 없으면 규칙 3은 묶음을 내지 않는다
   - 일반공급 절 제목 줄: 줄 처음(앞 공백 허용)에 번호(`5`, `8.`, `3` 같은 아라비아 숫자 1~2자리, 뒤에 `.`·`)` 있어도 됨, 또는 로마 숫자)와 「일반공급」이 오고, 그 뒤가 `(`·줄 끝·「신청」인 줄. 착수 때 149건 중 143건에서 찾았다(설계 사실 5)
   - 테스트: (a) 제목 줄 앞의 문장은 무시하고 뒤의 문장을 고른다 (b) 제목 줄이 없으면 None (c) 제목 꼴 셋 「5  일반공급 (「주택공급에 관한 규칙」 제27조)」 「8. 일반공급」 「3  일반공급 (「주택공급에 관한 규칙」제27조) 신청자격」 (d) 「일반공급 신청자격 기본요건」처럼 번호 없는 줄은 제목 줄이 아니다
3. 규칙 3 문장 정규식이 「거주자에 우선」도 받는다(2026000402 20쪽 「단, 경쟁이 있을 경우 익산시 거주자에 우선 공급합니다.」). 테스트가 있다. 기존 테스트 「거주자 말고 다른 것의 우선 문장은 무시」는 계속 통과한다
4. `rule_lines`(규칙별 후보 줄 수)가 규칙 3을 `_block_rule_3`과 같은 범위(제목 줄 아래)로 센다. 테스트가 있다
5. 기존 규칙 3 테스트는 가짜 쪽에 일반공급 절 제목 줄을 넣어 고친다. 테스트가 확인하는 동작(문장 줄 + 다음 줄, 줄을 넘는 문장 등)은 그대로다
6. 149건을 main(`a51fe89`)과 이 브랜치로 각각 돌려 공고마다 규칙·쪽·묶음 글자 수·글이 든 줄 수를 비교한 표를 `reports/resident-bound.md`에 쓴다(바뀐 공고만 행으로, 맨 위에 합계). 같은 리포트에 규칙 3 공고마다 일반공급 절 제목 줄의 쪽·줄과 고른 문장의 쪽·줄을 적는다. 비교 코드는 repo에 둔다(위치는 기존 리포트 코드 관례를 따른다). main 쪽 값은 코드를 고치기 전(Task 0)에 같은 비교 코드로 149건을 재서 `reports/resident-bound-before.json`으로 커밋해 둔다. 새 워크트리를 만들지 않는다. 리포트 맨 위에 재현 명령을 적는다
7. `check-pdf-labels`를 다시 돌려 `reports/pdf-labels.md`를 고친다. `eval-pdf --set test`(재는 30건)와 `eval-pdf --set tune`(다듬는 50건)을 한 번씩 다시 돌린다. LLM 설명은 고치지 않는다. 응답 캐시(`data/llm/`)가 있어 묶음이 그대로인 공고는 OpenAI를 다시 부르지 않는다
8. `docs/concepts.md`: 규칙 1 행(상한 추가)·규칙 3 행(일반공급 절 제목 줄 아래, 「거주자에」)을 고치고 「일반공급 절 제목 줄」 행(Kickoff 때 main이 더해 둠)의 「정의한 파일·줄」 칸을 채운다. 그 행의 뜻 칸은 바꾸지 않는다. 줄 번호는 이 브랜치 코드 기준. README에서 규칙 1·3을 설명한 곳이 있으면 같이 고친다 <!-- style-exempt -->
9. `uv run pytest` 통과, `uv run ruff check`·`uv run ruff format --check` 통과. 새 테스트는 `data/raw`를 읽지 않고 가짜 쪽 텍스트만 쓴다

## 실패 징후

1. **jw 기준 — 규칙 1 길이 상한.** 잴 값: 규칙 1 묶음 중 글이 든 줄이 5개를 넘는 묶음 수, 상한에 걸려 잘린 공고, 잘린 묶음에 필요한 줄이 남았나. baseline: 상한 없음, 가장 긴 묶음 2026000310 30줄(1829자)·2026000293 26줄(1231자), 셋째부터 4줄 이하 <!-- style-exempt -->
   - 통과: 5줄을 넘는 묶음 0이고, 잘린 공고가 2026000310·2026000293 둘뿐이며, 2026000310 묶음에 「①지역 : 해당지역 거주자(남양주시」 줄이, 2026000293 묶음에 「해당지역 거주자 (강릉시 6개월 이상」 줄이 남았다
   - 다시 잰다: 5줄을 넘는 묶음은 0인데 잘린 공고가 3~5건이다. 잘린 공고마다 잘린 묶음 전문을 리포트에 적는다
   - 미완: 5줄을 넘는 묶음이 하나라도 있다, 또는 잘린 공고가 6건 이상이다, 또는 위 두 줄 중 하나가 묶음에서 빠졌다
2. **jw 기준 — 해당지역 거주자 우선 문장의 위치.** 잴 값: 규칙 3을 쓰는 공고마다 고른 문장이 일반공급 절 제목 줄 아래에 있나, 그리고 PDF 전체를 넘기는 공고 수/149. baseline: 규칙 3 공고 3건 중 제목 줄 아래 문장을 고른 공고 1건(2026000401), 전체 0건
   - 통과: 규칙 3을 쓰는 공고 모두 제목 줄 아래 문장을 골랐고, 2026000274는 20쪽 「… 군산시 거주자에게 우선 공급함」, 2026000402는 20쪽 「… 익산시 거주자에 우선 공급합니다」, 2026000401은 9쪽 그대로이며, PDF 전체를 넘기는 공고가 0건이다
   - 다시 잰다: 제목 줄 아래 문장만 골랐지만 PDF 전체를 넘기는 공고가 1~2건이다(제목 줄을 못 찾았거나 절 안에 문장이 없음). 공고마다 이유와 그 공고의 일반공급 절 제목·문장으로 보이는 줄을 리포트에 적는다
   - 미완: 규칙 3이 제목 줄보다 앞의 문장을 고른 공고가 하나라도 있다, 또는 PDF 전체를 넘기는 공고가 3건 이상이다
   - 목차 쪽의 「5 일반공급」 같은 줄이 첫 제목 줄로 잡혀 앞쪽 문장을 고르면 이 항목의 미완이다. 그 공고를 리포트에 적는다
3. **정답 근거 줄이 묶음 밖인 칸.** 잴 값: `check-pdf-labels`의 `QUOTE_OUTSIDE_BLOCK` 칸 수. baseline: 1칸(2026000116)
   - 정상: 1칸이고 그 칸이 2026000116이다
   - 다시 본다: 2칸. 늘어난 칸의 묶음 규칙·쪽과 정답 근거 줄·쪽을 리포트에 나란히 적는다. 정답을 고치지 않는다
   - 미완: 3칸 이상
4. **LLM 거주지 값.** 잴 값: 거주지 맞은 칸. baseline: 다듬는 50건 50/50, 재는 30건 30/30
   - 정상: 둘 다 그대로
   - 다시 잰다: 어느 쪽이든 1칸 줄었다. 그 칸의 묶음 규칙·묶음 글·LLM 값·정답을 리포트에 적는다
   - 미완: 어느 쪽이든 2칸 이상 줄었다

## 이번에 안 하는 것

- 규칙 1에서 %가 없으면 규칙 2·3으로 넘기는 것 — 규칙 1 묶음 137건 중 117건에 %가 없고 정답은 `해당지역 100%`다(설계 사실 2)
- 규칙 3이 문장 뒤 한 줄만 붙이는 것, 일반공급 절 끝에서 찾기를 멈추는 것, 2026000116 괄호 문장(설계 §이번에 안 하는 것)
- 규칙 순서·규칙 2·쪽을 넘는 묶음의 쪽 번호
- 정답 파일 변경

## 파일

- `src/cheongyak_extract/pdf_fields.py` (`_block_rule_1`·`_block_rule_3`·`_SENTENCE_RE`·`rule_lines`, 새 일반공급 절 제목 정규식)
- `tests/test_pdf_fields.py`
- `reports/resident-bound.md`(새로), `reports/pdf-labels.md`, `reports/pdf-fields-tune-2.md`, `reports/pdf-resident-test.md`
- `docs/concepts.md`, README

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

0. 비교 코드를 만들고 지금 코드로 149건을 재서 `reports/resident-bound-before.json`을 커밋한다(통과 기준 6의 main 쪽 값)
1. 규칙 1 상한(통과 기준 1). 테스트 먼저 → `_block_rule_1`에 글이 든 줄 5개 상한 <!-- style-exempt -->
2. 규칙 3 일반공급 절 한정 + 「거주자에」 + `rule_lines`(통과 기준 2~5). 테스트 먼저. 기존 규칙 3 테스트의 가짜 쪽에 제목 줄을 넣는다
3. 149건 비교 리포트 `reports/resident-bound.md`(통과 기준 6). 실패 징후 1·2를 여기서 잰다
4. `check-pdf-labels`, `eval-pdf --set test`, `eval-pdf --set tune`(통과 기준 7). 실패 징후 3·4
5. `docs/concepts.md`·README(통과 기준 8)
6. Pre-PR checks, 커밋 전 리뷰, PR

## Pre-PR checks

Pre-PR checks (all required — do not assume pass, show output):
1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 120 uv run python -m cheongyak_extract check-pdf-labels --out /tmp/x.md; echo EXIT=$?` (청약홈·OpenAI를 부르지 않는다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.
Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함); PR via `gh pr create --assignee @me` (personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다.

내장 `/code-review`를 여기 쓰지 말 것 — 헤드리스 세션에는 없다.

## Done criteria

- [ ] 통과 기준 1~9가 전부 참이다. Actions는 PR을 연 뒤 `gh pr checks`로 확인한다. main과 충돌해 Actions가 안 돌면 충돌을 풀지 말고 그 사실을 PR 본문 맨 위에 적은 채 끝낸다
- [ ] 실패 징후 1~4를 측정해 값을 PR 본문에 적었다. 잰 값과 그 값이 든 구간 이름을 그대로 적고, 그 구간의 할 일을 했다. 판정은 jw 몫이다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(실패 징후 1·2의 값)
- [ ] plan·리포트·PR 본문은 `docs/concepts.md` 용어 절의 말을 쓴다. 표에 없는 새 이름을 짓지 않고 풀어 쓴다
- [ ] 정답 파일(`labels/`)을 바꾸지 않았다(`git diff main -- labels/`가 비어 있다)
- [ ] 청약홈을 부르지 않았다. OpenAI는 Task 4의 `eval-pdf` 두 번에서만 불렀다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`·`data/llm`(심볼릭 링크)·`.env`·`.venv`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#184] fix: 거주지 묶음 규칙 1에 길이 상한을 두고 규칙 3 문장을 일반공급 절 안에서 찾는다` <!-- style-exempt -->
- [ ] Notion `PR` 프로퍼티를 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/41341e61-65c0-8158-9ce5-d0fc60f8a7f8 -
  ```
