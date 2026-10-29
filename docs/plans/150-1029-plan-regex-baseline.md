# #150 정규식 baseline과 LLM 비교 — 구현 계획

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
**Notion:** #150 https://app.notion.com/p/40441e6165c0815bb103f4464ecc26d1
**설계:** /Users/jw/prv/.wt/150-regex-baseline/docs/plans/150-1029-design-regex-baseline.md (먼저 읽는다. LLM 숫자를 어디서 읽는지, 왜 LLM을 다시 부르지 않는지가 거기 있다)
**흐름:** 이미 있다(#146). 추출 단계에 정규식 추출기를 하나 더 붙인다. 수집·정규화·채점·리포트는 그대로 쓴다

## jw 기준

정규식 baseline과 llm 성능을 서로 비교한다

## 통과 기준

1. `src/cheongyak_extract/regex_extract.py`의 `regex_extract(pages: list[str]) -> dict[str, Extraction]`이 `FIELDS` 8개를 모두 키로 돌려준다. 값이 있으면 근거는 패턴이 걸린 줄, 쪽은 그 줄이 있는 쪽(1부터)이다. 못 찾으면 `EMPTY`
   - 테스트: 라벨 뒤에 값이 있는 작은 쪽 텍스트에서 필드마다 값·근거·쪽이 나온다. 라벨이 없으면 비운다
   - 패턴에 공고 번호나 특정 회사명·지명을 넣지 않는다
2. `eval --extractor regex`가 정규식으로 같은 리포트를 쓴다. 기본은 `llm`. `regex`면 OpenAI 클라이언트를 만들지 않고 `OPENAI_API_KEY` 없이 동작한다(테스트로 확인)
3. 리포트 넷이 커밋돼 있다
   - `reports/regex-tune.md` — 다듬는 공고 29건(공고 목록은 `reports/extract-tune-0.md`). 규칙 수정마다 한 줄: 수정 번호·바꾼 것·맞음/비움/다른 값으로 채움. 최대 3번
   - `reports/regex-new.md` — 재는 공고 20건(공고 목록은 `reports/extract-new.md`). `eval --extractor regex` 출력
   - `reports/regex-more.md` — 남은 101건(`data/raw/`에서 PDF가 열리는 150건 중 위 49건을 뺀 것). 정규식만
   - `reports/regex-vs-llm.md` — 비교 표(아래 Task 4)
4. `uv run pytest` 통과, `uv run ruff check` 통과, GitHub Actions pytest green. 테스트는 OpenAI·청약홈에 요청하지 않는다

## 이번에 안 하는 것

- LLM을 다시 부르는 것. OpenAI API를 한 번도 부르지 않는다. LLM 숫자는 `reports/extract-new.md`·`reports/extract-tune.md`에서 읽는다
- 남은 101건에 LLM을 돌리는 것
- 정규식과 LLM을 섞는 방식, 정규화 규칙 수정, LLM 추출 코드 수정
- 표의 몇 번째 칸인지 세는 파서, 공고별 예외 규칙. baseline은 라벨 뒤 값을 줍는 단순한 패턴으로 둔다
- 재는 20건·남은 101건 결과를 보고 규칙을 고치는 것. 고치면 `regex-new.md`를 무효로 적고 PR 본문 맨 위에 그 사실을 쓴다
- 정답 수동 대조(#149), PDF 전용 필드(#152)

## 실패 징후

칸 = 공고 하나 × 필드 하나, 청약홈 정답이 있는 칸만 센다. 칸은 맞음(정규화 뒤 정답과 같다) / 비움 / 다른 값으로 채움 셋 중 하나다. 분모는 정답 있는 칸 수다.

1. **jw 기준 — 같은 칸에서 정규식과 LLM을 나란히 놓았나.** 잴 값: `reports/regex-vs-llm.md`. 비교 대상: `reports/extract-new.md`의 LLM(T0, C안) 160칸 — 맞음 154(96.25%), 비움 0, 다른 값으로 채움 6(3.75%)
   - 통과: 재는 20건에서 정규식의 정답 있는 칸이 160이고, 맞음·비움·다른 값으로 채움 세 수가 LLM과 같은 표에 나란히 있다. 필드별 맞은 칸도 나란히 있다. 정규식 규칙 고정 커밋이 재는 20건 측정보다 앞이다
   - 다시 잰다: 정규식 쪽 정답 있는 칸이 160이 아니다(공고를 건너뛰었거나 정답 파싱이 다르다). 이유를 찾아 같은 160칸이 되게 고친 뒤 다시 잰다. 규칙은 고치지 않는다
   - 미완: 공고 목록이 `reports/extract-new.md`와 다르다, 규칙 고정 커밋이 측정 커밋보다 뒤다, 또는 OpenAI API를 불렀다
2. **다듬는 29건과 재는 20건의 차이.** 정규식의 다듬는 29건 맞은 칸 비율 − 재는 20건 맞은 칸 비율. 비교 대상: LLM은 94.4% − 96.25% = −1.85%p
   - 10%p 미만: 적어 둔다
   - 10%p 이상 20%p 미만: 남은 101건 맞은 칸 비율을 같이 적고 필드별로 어디서 벌어졌는지 PR 본문에 적는다
   - 20%p 이상: 규칙이 다듬는 29건에 맞춰졌을 수 있다. 차이가 가장 큰 필드 둘의 패턴과 재는 20건에서 놓친 칸 원문 줄을 PR 본문에 적는다
3. **남은 101건 맞은 칸 비율.** 비교 대상: 정규식 재는 20건 맞은 칸 비율. 차이 10%p 미만이면 적어 둔다, 10%p 이상이면 필드별 표를 PR 본문에 적는다. 정답 있는 칸 수도 같이 적는다(101건 중 정답이 없는 칸이 있을 수 있다)
4. **칸마다 갈린 곳.** 재는 20건 160칸에서 (정규식 맞음, LLM 틀림)·(정규식 틀림, LLM 맞음)·(둘 다 틀림) 칸 수. LLM 칸 상태는 `extract-new.md`의 「틀리게 채운 칸」 표 6칸이 다른 값으로 채움이고 나머지 154칸이 맞음이다. 값만 적는다

## 파일

- `src/cheongyak_extract/regex_extract.py`(새 파일) — `regex_extract`
- `src/cheongyak_extract/pipeline.py` — `evaluate`가 추출 방식을 받는다(정규식이면 `regex_extract`, LLM이면 지금 그대로). `Doc`에 넣는 것은 그대로 쓴다. 토큰·A·B·C안 표는 정규식일 때 빠져도 된다
- `src/cheongyak_extract/__main__.py` — `eval --extractor {llm,regex}`, `regex`면 `make_ask`를 부르지 않는다
- `tests/test_regex_extract.py`, `tests/test_pipeline.py`, `tests/test_main.py`
- `reports/regex-*.md`, `README.md`

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

1. **정규식 추출기 첫 판** — 통과 기준 1. 다듬는 29건 PDF를 보고 필드마다 라벨 패턴을 정한다
2. **`eval --extractor regex`** — 통과 기준 2
3. **규칙 다듬기와 고정 — 다듬는 29건만 쓴다.** 수정마다 `eval --extractor regex --pbno <29건> --out <scratch 경로>`로 재고 `reports/regex-tune.md`에 한 줄을 더한다(수정 0 = Task 1 그대로). 최대 3번. 맞은 칸이 안 늘면 그 수정을 되돌리고 멈춘다
   - 이 커밋이 고정 시점이다. 커밋 메시지에 「정규식 규칙 고정」을 쓴다
4. **재는 20건·남은 101건 측정과 비교 표 — 한 번만**
   - `eval --extractor regex --pbno <재는 20건> --out reports/regex-new.md`
   - `eval --extractor regex --pbno <남은 101건> --out reports/regex-more.md`. 공고 번호는 `check-raw`로 PDF가 열리는 공고를 고른 뒤 위 49건을 뺀다
   - `reports/regex-vs-llm.md`: (1) 재는 20건 정규식·LLM 맞음·비움·다른 값으로 채움 표 (2) 필드별 맞은 칸 표 (3) 다듬는 29건 같은 표(LLM은 `extract-tune.md` 마지막 C안 줄) (4) 실패 징후 4의 칸 수와 그 칸 목록 (5) 남은 101건 정규식 결과(LLM 없음이라고 적는다). LLM 숫자는 손으로 옮기지 말고 리포트 파일을 읽는 작은 스크립트나 테스트된 함수로 만든다 — 옮기다 틀리면 비교 전체가 틀린다
   - 이 Task 뒤로 `regex_extract.py`를 고치지 않는다
5. **README** — `eval --extractor regex` 사용법과 비교 표 요약

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `env -u OPENAI_API_KEY timeout 300 uv run python -m cheongyak_extract eval --extractor regex --pbno 2026000494 2026000448 --out /tmp/smoke.md; echo EXIT=$?`
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~4가 전부 참이다. 4의 Actions는 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1~4를 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫)
- [ ] PR 본문에 `reports/regex-vs-llm.md`의 표 (1)·(2)를 그대로 붙였다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(재는 20건 160칸에서 정규식과 LLM의 맞음·비움·다른 값으로 채움 비율을 나란히. LLM 숫자는 #147 세 번째 시도 리포트에서 읽었고 다시 부르지 않았다는 사실을 같이 적는다)
- [ ] 정규식 규칙 고정 커밋(Task 3)이 측정 커밋(Task 4)보다 앞이다. PR 본문에 두 커밋 해시를 적는다
- [ ] OpenAI API를 부르지 않았다
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있어 #146에서 끝나지 않고 세션을 붙잡았다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data`(심볼릭 링크, main 체크아웃의 `data/`를 가리킨다)·`.env`를 커밋하지 않았다. 파일을 지정해 add한다(`git add -A` 금지)
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#150] feature: 정규식 baseline을 넣고 LLM과 비교한다`
- [ ] Notion `PR` 프로퍼티를 새 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-815b-b103-f4464ecc26d1 -
  ```
