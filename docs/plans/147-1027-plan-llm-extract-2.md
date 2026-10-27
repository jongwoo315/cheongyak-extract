# #147 LLM 추출 두 번째 시도 — 구현 계획

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
**설계:** /Users/jw/prv/.wt/147-llm-extract-2/docs/plans/147-1027-design-llm-extract-2.md (먼저 읽는다. 결정 근거와 착수 때 확인한 사실이 거기 있다)
**첫 시도:** 닫힌 PR #3, 브랜치 `feat/147-llm-extract`(커밋 `ea3e0e8`). 반려 이유는 `docs/decisions.md`의 #147 행

## jw 기준

앞선 pr #3에서 언급된 사실(근거 문장을 PDF에서 찾지 못해 코드가 비운 18칸 중 16칸은 LLM 값이 맞았다, 신탁 사업 4건에서 LLM은 시행사로 위탁자를 골랐다. 청약홈 정답은 수탁자인 신탁사다, 청약홈 목록에 공고가 10건뿐이라, 처음 본 공고로 잴 수 있는 것은 최대 6건이었다)을 바탕으로 이번에는 extract()가 필드마다 값을 정확히 판정한다

## 통과 기준

1. 첫 시도 코드(`ea3e0e8`의 `src/`·`tests/`·`pyproject.toml`·`uv.lock`·`.gitignore`)가 이 브랜치에 있고 테스트가 통과한다
2. `pdf_text.pages()`가 기본으로 `sort=True` 텍스트를 준다. #148 측정(`measure-normalize`)은 기존 순서를 그대로 써서 `reports/normalize.md` 결과(23/24)가 바뀌지 않는다
3. 목록 2쪽부터 PDF 있는 공고를 지정한 수만큼 받는 명령이 있다: `uv run python -m cheongyak_extract fetch --start-page 2 --n 20`
   - `data/raw/`에 `notice.pdf`가 이미 있는 공고와 2026000531은 건너뛴다
   - 요청 사이 2초. 403·429가 3번 연속이면 멈추고 그때까지 받은 공고 번호를 출력한다
   - `httpx.MockTransport` 테스트
4. 값을 남기는 조건 A·B·C안(설계 §값을 남기는 조건)이 `extract()`의 인자로 있고, 각각 테스트가 있다. `eval`이 같은 응답에 세 안을 모두 걸어 리포트에 나란히 적는다
5. 리포트 네 개가 커밋돼 있다
   - `reports/extract-tune-0.md` — 첫 시도 프롬프트 그대로, 다듬는 공고 9건, PDF 텍스트 기본 순서 vs `sort=True`
   - `reports/extract-tune.md` — 프롬프트 수정마다 한 줄(수정 번호·바꾼 것·안별 맞음/비움/틀리게 채움), 다듬는 공고 9건
   - `reports/extract-new.md` — 프롬프트 고정 뒤 받은 공고 20건
   - (다시 잴 때만) `reports/extract-new2.md`
6. 테스트는 API를 부르지 않는다. 프롬프트 고정 시점의 다듬는 공고 응답을 `tests/fixtures/llm/<pbno>.json`에 다시 녹화하고 재생 테스트가 있다
7. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green

## 이번에 안 하는 것

- 정규식 baseline(#150), PDF에만 있는 필드(#152), 정답 수동 대조(#149), 150건 확대(#151)
- 모델 비교. `gpt-5.4-mini` 그대로
- 정규화 규칙 수정. 정규화 때문에 틀린 칸은 리포트에 적기만 한다
- 다른 PDF 파서(`find_tables` 등)
- 재는 공고 결과를 보고 프롬프트·값을 남기는 조건·PDF 텍스트 방식을 바꾸는 것. 바꾸면 `extract-new.md`를 무효로 적고 PR 본문 맨 위에 그 사실을 쓴다
- 틀리게 채운 칸을 원인별로 기준에서 빼는 것. 원인은 참고로만 적는다

## 실패 징후

칸 = 공고 하나 × 필드 하나, 청약홈 정답이 있는 칸만 센다. 칸은 맞음(정규화 뒤 정답과 같다) / 비움 / 틀리게 채움(값이 있는데 정답과 다르다) 셋 중 하나다.

1. **jw 기준 — 재는 공고에서 필드마다 값이 정답과 같은가.** 잴 값: `reports/extract-new.md`의 맞은 칸 비율과 틀리게 채운 칸 비율, 그리고 필드별 맞은 칸 비율. 비교 대상: 첫 시도(처음 본 공고 40칸 중 맞음 62.5%, 틀리게 채움 3칸 7.5%)
   - 통과: 맞은 칸 85% 이상, 그리고 틀리게 채운 칸 4% 이하
   - 다시 잰다: 맞은 칸 70~84%, 또는 틀리게 채운 칸 4% 초과 8% 이하. 프롬프트는 그대로 두고 목록에서 공고 10건을 더 받아 `reports/extract-new2.md`를 쓰고 합친 수치를 PR 본문에 적는다
   - 미완: 맞은 칸 70% 미만 / 틀리게 채운 칸 8% 초과 / 재는 공고가 10건 미만
2. **`sort=True`가 근거 확인 실패를 줄였나.** 잴 값: `extract-tune-0.md`에서 같은 프롬프트로 근거를 그 쪽에서 못 찾아 비운 칸 수, 기본 순서 vs `sort=True`. 첫 시도 기본 순서 값은 9건 기준으로 다시 센다
   - 줄었다: `sort=True` 쪽이 기본 순서의 절반 이하
   - 다시 본다: 절반 초과, 기본 순서보다 적다. 남은 칸의 근거와 그 쪽 텍스트를 나란히 PR 본문에 적는다
   - 효과 없음: 기본 순서 이상. `sort=True`를 쓰지 않고 기본 순서로 되돌린 뒤 그 사실을 PR 본문 맨 위에 적는다
3. **고른 안에서 근거를 못 찾아 비운 칸이 많나.** 잴 값: 재는 공고에서 LLM이 값을 준 칸 중 고른 안의 조건으로 비운 칸 비율
   - 정상: 10% 미만
   - 다시 본다: 10~25%. 비운 칸 사례 3개를 PR 본문에 적는다
   - 미완: 25% 초과
4. **다듬는 공고에만 맞춘 것인가.** 잴 값: 맞은 칸 비율 차이(다듬는 9건 − 재는 공고)
   - 정상: 10%p 미만
   - 지켜본다: 10~20%p. 어느 필드에서 벌어졌는지 PR 본문에 적는다
   - 과적합 의심: 20%p 이상. PR 본문 맨 위에 적는다
5. **시행사 필드.** 잴 값: 재는 공고 중 신탁 방식 공고(PDF에 `수탁`·`위탁`이 시행사 문맥에 나오는 것)의 시행사 맞은 칸 수 / 그 공고 수. 신탁 방식 공고가 0건이면 그 사실을 적는다. 비교 대상: 첫 시도 0/4
6. **프롬프트 수정 횟수.** 5번을 넘기지 않는다. 5번째 뒤에도 다듬는 공고에서 기준 1의 통과 구간에 못 들어가면 그 상태로 고정하고 PR 본문에 적는다

## 파일

| 파일 | 할 일 |
| --- | --- |
| `src/`·`tests/`·`pyproject.toml`·`uv.lock`·`.gitignore` | Task 1에서 `ea3e0e8`에서 가져온다 |
| `src/cheongyak_extract/pdf_text.py` | `pages(path, sort=True)` |
| `src/cheongyak_extract/measure.py` | #148 측정이 `sort=False`를 쓰게 한다 |
| `src/cheongyak_extract/fetch.py`, `pipeline.py`, `__main__.py` | 목록 페이지 인자, `fetch` 하위 명령, 연속 실패 시 멈춤 |
| `src/cheongyak_extract/extract.py` | 값을 남기는 조건 A·B·C안 인자, 필드 정의(시행사 포함) |
| `src/cheongyak_extract/report.py` | 안별 비교 표, 필드별 맞은 칸 비율 |
| `tests/fixtures/llm/<pbno>.json` | 프롬프트 고정 시점 응답으로 다시 녹화(9건) |
| `README.md` | 흐름, `fetch`·`eval` 명령, `OPENAI_API_KEY`. 판단 기록 절은 건드리지 않는다 |

다듬는 공고 9건: 2026000518 2026000530 2026000532 2026000517 2026000496 2026000502 2026000514 2026000513 2026000509

`data/llm/`에 첫 시도 응답 캐시 21개를 미리 넣어 두었다(git 밖). 첫 시도 프롬프트 + 기본 순서 텍스트는 API를 부르지 않는다.

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. **첫 시도 코드 가져오기** — `git checkout ea3e0e8 -- src tests pyproject.toml uv.lock .gitignore` 후 `uv sync`, `uv run pytest`. 실패하는 테스트가 있으면 이 Task에서 고친다. 커밋 메시지에 `ea3e0e8`을 적는다
2. **`sort=True`** — 통과 기준 2. `measure-normalize`를 다시 돌려 23/24가 그대로인지 확인한다
3. **목록 페이지와 `fetch` 명령** — 통과 기준 3. 이 Task에서는 실제 요청을 보내지 않는다(테스트만)
4. **값을 남기는 조건 A·B·C안** — 통과 기준 4. 기본값은 A안(첫 시도 동작). 세 안 모두 같은 응답으로 테스트한다
5. **리포트** — 안별 비교 표, 필드별 맞은 칸 비율
6. **`sort=True` 효과 측정** — 첫 시도 프롬프트 그대로, 다듬는 공고 9건을 기본 순서(캐시)와 `sort=True`(API 호출)로 각각 `eval`해 `reports/extract-tune-0.md`를 쓴다. 실패 징후 2를 여기서 판정한다(효과 없음이면 Task 2를 되돌린다)
7. **프롬프트 다듬기와 고정 — 다듬는 공고 9건만 쓴다.** 수정마다 9건을 `eval`하고 `reports/extract-tune.md`에 한 줄을 더한다. 최대 5번
   - 필드 정의를 청약홈 상세 표 기준으로 다시 쓴다. 시행사는 「사업주체. 신탁 방식이면 사업을 맡은 신탁사(시행수탁자)」
   - 값을 남기는 조건은 설계 §값을 남기는 조건의 고르는 규칙으로 정하고, 기본값을 그 안으로 바꾼다
   - 마지막 수정의 응답을 `tests/fixtures/llm/`에 다시 녹화하고 재생 테스트를 고친다
   - 이 커밋이 고정 시점이다. 커밋 메시지에 「프롬프트 고정」과 고른 안을 쓴다
8. **재는 공고 받기와 측정 — 한 번만.** `fetch --start-page 2 --n 20`, 받은 공고 번호로 `eval --out reports/extract-new.md`
   - 실패 징후 1이 「다시 잰다」면 `fetch`로 10건을 더 받아 `reports/extract-new2.md`를 쓴다
   - 이 Task 뒤로 `extract.py`·`pdf_text.py`를 고치지 않는다
9. **README**

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 600 uv run python -m cheongyak_extract eval --pbno 2026000518 2026000530 2026000532 --out /tmp/smoke.md; echo EXIT=$?` (캐시가 있으면 API를 안 부른다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~7이 전부 참이다. 7의 Actions는 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1~6을 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫)
- [ ] 재는 공고에서 틀리게 채운 칸 전부를 PR 본문 표로 적었다: 공고·필드·정답·추출값·근거가 된 PDF 원문 줄·원인(참고)
- [ ] `reports/extract-*.md`가 커밋돼 있고 PR 본문에 `extract-tune.md`·`extract-new.md` 표를 그대로 붙였다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(재는 공고 n건 m칸 중 맞음·비움·틀리게 채움, 필드별 맞은 칸 비율, 첫 시도 수치와 나란히)
- [ ] 프롬프트 고정 커밋(Task 7)이 재는 공고 받기(Task 8)보다 앞이다. PR 본문에 두 커밋 해시를 적는다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있어 #146에서 끝나지 않고 세션을 붙잡았다). 필요하면 `/bin/ls`
- [ ] 오래 걸리는 명령(`fetch`, API 부르는 `eval`)은 foreground에서 `timeout`을 걸어 돌린다. 백그라운드로 돌리면 끝날 때까지 기다린 뒤 shell을 정리한다
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`(심볼릭 링크)·`data/llm/`·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#147] feature: extract()를 LLM 추출로 바꾼다 (두 번째 시도)`. 본문에 닫힌 PR #3 링크
- [ ] Notion `PR` 프로퍼티를 새 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-81b8-9e3f-f954da162fc9 -
  ```
