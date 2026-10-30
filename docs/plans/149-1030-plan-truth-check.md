# #149 청약홈 정답과 공고문 PDF 값 20건 대조 — 구현 계획

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
**Notion:** #149 https://app.notion.com/p/40441e6165c0812ea53cda4e197412df
**설계:** /Users/jw/prv/.wt/149-truth-check/docs/plans/149-1030-design-truth-check.md (먼저 읽는다. 착수 때 확인한 사실, PDF 값을 적는 규칙, 같다고 보는 기준이 거기 있다)
**흐름:** 이미 있다(#146). 이 티켓은 `run`·`eval` 흐름을 바꾸지 않는다. 그 흐름이 정답으로 믿는 HTML 값을 따로 검사하는 명령(`check-truth`)을 더한다

## jw 기준

공고 20건을 열어서 html값과 pdf값을 비교하고 90%이상 일치한다

## 통과 기준

1. `labels/pdf-values-20.json`: 공고 20건(`reports/extract-new.md` 맨 위 목록) × 필드 8개 = 160칸. 칸마다 `value`·`quote`·`page`·`note`. 적는 규칙은 설계 §PDF 값은 누가 어떻게 적나
   - 형태: `{"<pbno>": {"<필드>": {"value": str|null, "quote": str|null, "page": int|null, "note": str|null}}}`
   - 같지 않은 칸에는 `note` 첫머리에 원인 하나를 적는다: `표기 차이:` / `정정:` / `다른 값:` / `PDF에 없음:`. 원인은 비교를 돌린 뒤에 적는다(Task 4)
2. `src/cheongyak_extract/truth_check.py`(새 파일)
   - 라벨 파일을 읽어 칸마다 HTML 정답(`truth.parse_truth`)과 PDF 값을 `normalize.normalize`로 비교한다
   - `quote`가 있는 칸은 `extract.grounded(quote, pages[page-1])`로 근거를 검사한다. `pages`는 `pdf_text.pages(path)`(sort=True)
   - 칸 수가 160이 아니거나 필드·공고가 빠지면 에러를 낸다(빈 파일이 「0/0」으로 깨끗해 보이지 않게)
3. `check-truth` 하위 명령: `reports/truth-check.md`를 쓴다. 청약홈과 OpenAI에 요청하지 않는다
   - 맨 위: 정규화 뒤 같은 칸 n/160(%), 근거를 그 쪽에서 못 찾은 칸 수
   - 같지 않은 칸 원인별 수, 「표기 차이」를 같은 칸으로 쳤을 때 비율(참고)
   - 필드별 같은 칸 수
   - 같지 않은 칸 전부: 공고·필드·HTML 값·PDF 값·쪽·`note`
   - LLM·정규식 다시 읽기 표(설계 §LLM·정규식 점수를 다시 읽는 표): #147 LLM이 정답과 다른 값으로 채운 6칸, #150 정규식이 정답과 다른 값으로 채운 15칸 각각 추출값이 PDF 값과 같은지. 합계 줄(LLM 6칸 중 PDF 값과 같은 칸 k, 정규식 15칸 중 m)
4. `README.md`에 `check-truth` 사용법과 결과 한 줄
5. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green. 테스트는 `data/raw/`를 읽지 않는다(작은 fixture를 만든다)

## 이번에 안 하는 것

- eval 정답을 PDF 값으로 바꾸는 것, 기존 리포트(`reports/extract-*.md`, `reports/regex-*.md`, `reports/regex-vs-llm.md`)를 고치는 것
- 정규화 규칙 수정. 「표기 차이」 칸이 나와도 `normalize.py`를 고치지 않는다
- 20건 밖의 공고, PDF에만 있는 필드(#152), 결정 기록(#153)
- LLM·청약홈 호출

## 실패 징후

1. **jw 기준 — HTML 값과 PDF 값이 같은 칸 비율.** 잴 값: `reports/truth-check.md` 맨 위 「정규화 뒤 같은 칸 n/160」. baseline 없음 — 이번이 첫 측정이다
   - 통과: 144칸 이상(90% 이상)이고 근거를 그 쪽에서 못 찾은 칸 0
   - 다시 잰다: 근거를 그 쪽에서 못 찾은 칸이 1칸 이상. 그 칸의 `quote`·`page`를 PDF 텍스트에서 다시 복사해 고치고 다시 센다. 두 번째에도 남으면 그 칸 목록을 PR 본문에 적는다
   - 미달: 143칸 이하(90% 미만). 같지 않은 칸 원인별 수와 필드별 표를 PR 본문에 그대로 옮긴다
2. **같지 않은 칸 중 「표기 차이」 비율.** 정규화가 못 맞춘 것이지 HTML이 틀린 것이 아니다. 같지 않은 칸의 절반을 넘으면 본 수치보다 정규화 쪽 문제가 크다는 뜻이라 PR 본문에 그 칸들을 따로 표로 적는다
3. **PDF 값 파일이 HTML을 보고 적혔나.** `labels/pdf-values-20.json`을 처음 커밋한 커밋이 `check-truth`를 실데이터로 처음 돌린 커밋(`reports/truth-check.md` 첫 커밋)보다 앞이어야 한다. 순서가 반대면 미완이다
4. **LLM·정규식 다시 읽기.** LLM 6칸 중 PDF 값과 같은 칸, 정규식 15칸 중 PDF 값과 같은 칸. baseline 없음 — 값만 적는다

## 파일

- `labels/pdf-values-20.json`(새 파일)
- `src/cheongyak_extract/truth_check.py`(새 파일), `src/cheongyak_extract/__main__.py`(`check-truth`)
- `tests/test_truth_check.py`, `tests/test_main.py`, 필요하면 `tests/fixtures/`의 작은 HTML·PDF
- `reports/truth-check.md`, `README.md`

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. **`truth_check` 비교 코드** — 통과 기준 2. fixture: 공고 1건·필드 몇 개짜리 HTML·라벨·쪽 텍스트를 주입한다(같은 칸, 정규화로 같아지는 칸, 다른 칸, PDF에 없음, 근거를 못 찾는 칸). 160칸 검사는 칸 수를 인자로 받아 테스트에서 작게 준다
2. **`check-truth` 명령과 리포트** — 통과 기준 3. LLM·정규식 다시 읽기 표는 `compare.parse_llm_new`·`compare.regex_cells`를 쓴다
3. **PDF 값 160칸 적기** — 통과 기준 1. 이 Task 동안 `detail.html`과 `reports/`의 기존 리포트를 열지 않는다. PDF 텍스트는 `pdf_text.pages`로 뽑아 읽는다. `note`의 원인 접두어는 아직 적지 않는다(정정을 PDF에서 직접 본 경우만 `정정:`). `labels/pdf-values-20.json`만 커밋한다
4. **실데이터로 측정** — `uv run python -m cheongyak_extract check-truth`. 실패 징후 1이 「다시 잰다」면 그 칸만 고쳐 다시 돌린다. 같지 않은 칸마다 `note` 첫머리에 원인을 적고 다시 돌린다. `labels/pdf-values-20.json`과 `reports/truth-check.md`를 커밋한다. 이 Task에서 PDF `value`를 HTML에 맞춰 바꾸지 않는다 — 바꿀 수 있는 것은 근거 검사에 걸린 칸의 `quote`·`page`와 `note`뿐이다
5. **README** — 통과 기준 4

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 120 uv run python -m cheongyak_extract check-truth; echo EXIT=$?`
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~5가 전부 참이다. 5의 Actions는 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1~4를 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫). 3은 두 커밋 해시를 적는다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(같은 칸 n/160, 근거를 못 찾은 칸 수, 같지 않은 칸 원인별 수). PDF 값은 jw가 아니라 구현 루프가 읽어 적었다는 사실을 같이 적는다
- [ ] OpenAI API와 청약홈을 부르지 않았다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있어 #146에서 끝나지 않고 세션을 붙잡았다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data`(심볼릭 링크, main 체크아웃의 `data/`를 가리킨다)·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지)
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#149] feature: 청약홈 정답과 공고문 PDF 값을 20건 대조한다`
- [ ] Notion `PR` 프로퍼티를 새 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-812e-a53c-da4e197412df -
  ```
