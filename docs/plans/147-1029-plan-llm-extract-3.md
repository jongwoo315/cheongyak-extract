# #147 LLM 추출 세 번째 시도 — 구현 계획

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
**설계:** /Users/jw/prv/.wt/147-llm-extract-3/docs/plans/147-1029-design-llm-extract-3.md (먼저 읽는다. 결정 근거와 착수 때 확인한 사실이 거기 있다)
**두 번째 시도:** 닫힌 PR #4, 브랜치 `feat/147-llm-extract-2`(커밋 `188417b`). 반려 이유는 `docs/decisions.md`의 「#147 LLM 추출 (두 번째 시도)」 행

## jw 기준

추출 성능은 90.6% 이상을 유지하고 다른 값으로 채운 비율이 7% 미만으로 떨어진다

## 통과 기준

1. 두 번째 시도 코드(`188417b`의 `src/`·`tests/`·`pyproject.toml`·`uv.lock`·`.gitignore`)가 이 브랜치에 있고 테스트가 통과한다
2. `pdf_text.pages()`에 텍스트 방식 인자가 있다: T0(`sort=True`만), T1(T0 + 그 쪽 `find_tables()` 표를 `to_markdown()`으로 뒤에 붙임). `eval`에서 고를 수 있다. #148 측정(`measure-normalize`)은 기존 순서를 그대로 써서 `reports/normalize.md` 결과(23/24)가 바뀌지 않는다
   - T1 테스트: 표가 있는 작은 PDF fixture에서 표 markdown이 붙고, 표가 없는 쪽은 T0와 같다
   - 근거 문장 확인은 LLM에 준 쪽 텍스트(T1이면 표 markdown 포함)에 건다
3. 리포트에 방식별 입력 토큰 합계가 나온다
4. 리포트 셋이 커밋돼 있다
   - `reports/extract-tune-0.md` — 두 번째 시도 프롬프트 그대로, 다듬는 공고 29건, T0 vs T1, A·B·C안
   - `reports/extract-tune.md` — 프롬프트 수정마다 한 줄(수정 번호·바꾼 것·맞음/비움/다른 값으로 채움), 다듬는 공고 29건
   - `reports/extract-new.md` — 고정 뒤 받은 공고 20건
   - (다시 잴 때만) `reports/extract-new2.md`
5. 테스트는 API를 부르지 않는다. 고정 시점 응답을 `tests/fixtures/llm/<pbno>.json`에 다시 녹화하고 재생 테스트가 그 프롬프트로 받은 것인지 확인한다(두 번째 시도 리뷰 지적 17)
6. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green

## 이번에 안 하는 것

- 정규식 baseline(#150), PDF에만 있는 필드(#152), 정답 수동 대조(#149), 150건 확대(#151)
- 모델 비교. `gpt-5.4-mini` 그대로
- 정규화 규칙 수정. 값의 꼴은 프롬프트에서 맞춘다
- PDF 안 글자 위치가 흩어진 칸(2026000508 `(주)`)을 고치는 것
- 표 영역을 본문에서 지우는 방식, 새 의존성(`pymupdf4llm` 등)
- 재는 공고 결과를 보고 프롬프트·텍스트 방식·값을 남기는 조건을 바꾸는 것. 바꾸면 `extract-new.md`를 무효로 적고 PR 본문 맨 위에 그 사실을 쓴다
- 다른 값으로 채운 칸을 원인별로 기준에서 빼는 것. 원인은 참고로만 적는다
- 프롬프트에 공고 번호나 특정 회사명을 넣는 것

## 실패 징후

칸 = 공고 하나 × 필드 하나, 청약홈 정답이 있는 칸만 센다. 칸은 맞음(정규화 뒤 정답과 같다) / 비움 / 다른 값으로 채움(값이 있는데 정답과 다르다) 셋 중 하나다. 비율의 분모는 정답 있는 칸 수다.

1. **jw 기준 — 재는 공고 20건에서 맞은 칸 비율과 다른 값으로 채운 칸 비율.** 잴 값: `reports/extract-new.md`. 비교 대상: 두 번째 시도(다른 공고 20건 160칸, 맞음 90.6%, 다른 값으로 채움 8.75%)
   - 통과: 맞은 칸 90.6% 이상, 그리고 다른 값으로 채운 칸 7% 미만
   - 다시 잰다: 맞은 칸 85% 이상 90.6% 미만, 또는 다른 값으로 채운 칸 7% 이상 8.75% 이하. 고정한 설정 그대로 공고 10건을 더 받아 `reports/extract-new2.md`를 쓰고 합친 수치를 PR 본문에 적는다
   - 미완: 맞은 칸 85% 미만 / 다른 값으로 채운 칸 8.75% 초과 / 재는 공고가 10건 미만
2. **표를 붙이면 회사 필드에서 다른 값으로 채운 칸이 줄었나.** 잴 값: `extract-tune-0.md`, 다듬는 공고 29건, 두 번째 시도 프롬프트, C안. 시행사·시공사의 다른 값으로 채운 칸 수, T0 vs T1
   - 줄었다: T1이 T0의 절반 이하
   - 다시 본다: 절반 초과, T0보다 적다. 남은 칸의 표 markdown을 PR 본문에 적는다
   - 효과 없음: T0 이상. 고르는 규칙(설계 §PDF 텍스트에 표를 덧붙이는 방식)대로 정하고, T0로 가면 그 사실을 PR 본문 맨 위에 적는다
3. **표를 붙여 입력이 얼마나 늘었나.** 잴 값: 다듬는 공고 29건 입력 토큰 합계, T1 ÷ T0
   - 정상: 1.5배 이하
   - 적는다: 1.5~2배. 표가 많은 공고 3건을 PR 본문에 적는다
   - 다시 본다: 2배 초과. 공고 하나가 모델 입력 한도에 걸리는지 PR 본문에 적는다
4. **고른 조건으로 비운 칸이 많나.** 잴 값: 재는 공고에서 LLM이 값을 준 칸 중 고른 안의 조건으로 비운 칸 비율
   - 정상: 10% 미만
   - 다시 본다: 10~25%. 비운 칸 사례 3개를 PR 본문에 적는다
   - 미완: 25% 초과
5. **다듬는 공고에만 맞춘 것인가.** 잴 값: 맞은 칸 비율 차이(다듬는 29건 − 재는 20건)
   - 정상: 5%p 미만
   - 지켜본다: 5~10%p. 어느 필드에서 벌어졌는지 PR 본문에 적는다
   - 과적합 의심: 10%p 이상. PR 본문 맨 위에 적는다
6. **프롬프트 수정 횟수.** 3번을 넘기지 않는다. 3번째 뒤에도 다듬는 공고에서 기준 1의 통과 구간에 못 들어가면 그 상태로 고정하고 PR 본문에 적는다

## 파일

| 파일 | 할 일 |
| --- | --- |
| `src/`·`tests/`·`pyproject.toml`·`uv.lock`·`.gitignore` | Task 1에서 `188417b`에서 가져온다 |
| `src/cheongyak_extract/pdf_text.py` | 텍스트 방식 T0·T1 |
| `src/cheongyak_extract/pipeline.py`, `__main__.py` | `eval`에 텍스트 방식 인자 |
| `src/cheongyak_extract/extract.py` | 값의 꼴(날짜·회사 여럿·입주예정월), 시행사 정의 |
| `src/cheongyak_extract/report.py` | 방식별 입력 토큰 합계 |
| `tests/fixtures/` | 표가 있는 작은 PDF, 고정 시점 LLM 응답 |
| `README.md` | 흐름과 `eval` 텍스트 방식 인자. 판단 기록 절은 건드리지 않는다 |

다듬는 공고 29건:
2026000518 2026000530 2026000532 2026000517 2026000496 2026000502 2026000514 2026000513 2026000509
2026000508 2026000507 2026000495 2026000373 2026000455 2026000492 2026000491 2026000471 2026000469 2026000466
2026000464 2026000458 2026000402 2026000267 2026000498 2026000468 2026000463 2026000444 2026000386 2026000453

`data/llm/`에 두 번째 시도 응답 캐시 86개를 미리 넣어 두었다(git 밖). 두 번째 시도 프롬프트 + T0 텍스트는 다듬는 29건 모두 API를 부르지 않는다. 캐시가 없는 공고가 있으면 그 번호를 리포트에 적고 API를 부른다.

착수 때 main이 두 번째 시도 브랜치에서 캐시만으로 29건을 `eval`했다(쓸 수 없는 키로 돌려 API를 안 부른 것을 확인). C안 232칸 중 맞음 211(90.9%), 비움 4, 다른 값으로 채움 17(7.3%). Task 4에서 같은 값이 나와야 한다.

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. **두 번째 시도 코드 가져오기** — `git checkout 188417b -- src tests pyproject.toml uv.lock .gitignore` 후 `uv sync`, `uv run pytest`. 커밋 메시지에 `188417b`를 적는다
2. **텍스트 방식 T0·T1** — 통과 기준 2. 기본값은 T0(두 번째 시도 동작). `measure-normalize`를 다시 돌려 23/24가 그대로인지 확인한다
3. **리포트에 방식별 입력 토큰** — 통과 기준 3
4. **표 효과 측정** — 두 번째 시도 프롬프트 그대로, 다듬는 공고 29건을 T0(캐시)와 T1(API)로 `eval`해 `reports/extract-tune-0.md`를 쓴다. A·B·C안을 나란히 적는다. 실패 징후 2·3을 여기서 잰다. 고르는 규칙대로 텍스트 방식을 정하고 기본값을 바꾼다
5. **프롬프트 다듬기와 고정 — 다듬는 공고 29건만 쓴다.** 수정마다 29건을 `eval`하고 `reports/extract-tune.md`에 한 줄을 더한다. 최대 3번
   - 값의 꼴: 날짜 `YYYY-MM-DD`, 기간 `YYYY-MM-DD ~ YYYY-MM-DD`(끝 날짜에 연도가 없으면 시작 날짜의 연도), 회사 여럿은 `, `로 잇고 사업자번호·법인번호는 넣지 않는다, 입주예정월 `YYYY.MM`
   - 시행사 정의: 다듬는 공고에서 청약홈 정답과 공고문 사업주체 칸을 대조해 다시 쓴다(설계 §시행사 정의를 다시 쓴다). 대조 결과 표를 `extract-tune.md`에 남긴다
   - 값을 남기는 조건은 다듬는 공고 29건에서 다시 고른다. 고르는 규칙: 맞은 칸이 두 번째 시도 설정(T0 + 두 번째 시도 프롬프트 + C안)의 다듬는 29건 값 이상인 안 중 다른 값으로 채운 칸이 가장 적은 것. 동률이면 C안 → A안 → B안
   - 마지막 수정의 응답을 `tests/fixtures/llm/`에 다시 녹화하고 재생 테스트를 고친다
   - 이 커밋이 고정 시점이다. 커밋 메시지에 「프롬프트 고정」, 고른 텍스트 방식, 고른 안을 쓴다
6. **재는 공고 받기와 측정 — 한 번만.** `fetch --start-page 2 --n 20`, 받은 공고 번호로 `eval --out reports/extract-new.md`
   - 받은 20건이 다듬는 29건과 겹치지 않는지 확인해 PR 본문에 적는다
   - 실패 징후 1이 「다시 잰다」면 `fetch`로 10건을 더 받아 `reports/extract-new2.md`를 쓴다
   - 이 Task 뒤로 `extract.py`·`pdf_text.py`를 고치지 않는다
7. **README**

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 600 uv run python -m cheongyak_extract eval --pbno 2026000518 2026000530 2026000532 --out /tmp/smoke.md; echo EXIT=$?` (캐시가 있으면 API를 안 부른다)
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~6이 전부 참이다. 6의 Actions는 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1~6을 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫)
- [ ] 재는 공고에서 다른 값으로 채운 칸 전부를 PR 본문 표로 적었다: 공고·필드·정답·추출값·근거가 된 PDF 원문 줄·원인(참고)
- [ ] 다듬는 공고 29건에서 두 번째 시도 설정과 고정한 설정의 맞음·비움·다른 값으로 채움을 나란히 PR 본문에 적었다(같은 공고끼리 비교. 다듬는 데 쓴 공고라는 사실을 같이 적는다)
- [ ] `reports/extract-*.md`가 커밋돼 있고 PR 본문에 `extract-tune.md`·`extract-new.md` 표를 그대로 붙였다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(재는 공고 n건 m칸 중 맞음·비움·다른 값으로 채움 비율, 필드별 맞은 칸 비율, 두 번째 시도 수치와 나란히. 두 번째 시도는 다른 공고에서 잰 값이라는 사실을 같이 적는다)
- [ ] 프롬프트 고정 커밋(Task 5)이 재는 공고 받기(Task 6)보다 앞이다. PR 본문에 두 커밋 해시를 적는다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있어 #146에서 끝나지 않고 세션을 붙잡았다). 필요하면 `/bin/ls`
- [ ] 오래 걸리는 명령(`fetch`, API 부르는 `eval`)은 foreground에서 `timeout`을 걸어 돌린다. 백그라운드로 돌리면 끝날 때까지 기다린 뒤 shell을 정리한다
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`(심볼릭 링크)·`data/llm/`·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지). API 키가 어떤 파일에도 없다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#147] feature: extract()를 LLM 추출로 바꾼다 (세 번째 시도)`. 본문에 닫힌 PR #3·#4 링크
- [ ] Notion `PR` 프로퍼티를 새 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-81b8-9e3f-f954da162fc9 -
  ```
