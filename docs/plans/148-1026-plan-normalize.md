# #148 정규화 — 구현 계획

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
**Notion:** #148 https://app.notion.com/p/40441e6165c08183a93bd9429f8dfb46
**설계:** /Users/jw/prv/.wt/148-normalize/docs/plans/148-1026-design-normalize.md (먼저 읽는다)

## jw 기준

정규화를 거친 문자열을 만들어 문자열 간 비교 퀄리티를 높인다

## 통과 기준

1. 필드 종류별 정규화 함수가 있고, `report.metrics()`의 정확도 비교가 정답·추출값 양쪽을 정규화한 뒤
   비교한다. 리포트에 찍히는 값과 저장 값은 원본 그대로다
2. 모의 추출값 24쌍(공고 3건 × 8필드)이 `tests/fixtures/pdf_forms.json`에 있다
   - 값은 PDF 텍스트에서 복사한 꼴 그대로이고, 쪽 번호가 붙어 있다. 정답을 보고 고치지 않는다
   - 테스트가 각 값이 그 쪽 텍스트에 실제로 있는지(공백만 무시) 확인한다
3. 측정 명령 하나가 24쌍의 일치 수를 정규화 전(`strip()` 비교)과 후로 나란히 출력한다:
   `uv run python -m cheongyak_extract measure-normalize`
   - 결과를 `reports/normalize.md`에 쓴다. 안 맞는 쌍은 정답·모의값·정규형을 같이 적는다
4. 설계 문서 §정규화 결과가 같아지면 안 되는 것의 5개 경우가 테스트로 있고 통과한다
5. stub으로 `run --n 3`을 다시 돌려도 모든 필드 정확도 0%·빈 칸 100%다
   (정규화가 빈 값을 다른 값과 같게 만들지 않는다). 네트워크 없이 `data/raw/`로 돌릴 수 있으면 그쪽을 쓴다
6. `uv run pytest` 통과, GitHub Actions pytest green

## 이번에 안 하는 것

- 금액 단위 — 지금 정답 필드에 금액이 없다
- 추출 자체(LLM) — #147
- 정답이 PDF와 실제로 다른 경우를 고치는 것 — #149. 여기서는 그런 쌍을 리포트에 「정답 쪽 차이」로 적기만 한다
- 새 공고 수집. 청약홈에 요청을 보내지 않는다. `data/raw/`(받아 둔 3건, 심볼릭 링크)만 쓴다
- 정규화를 추출 출력에 미리 적용하는 것. 비교 직전에만 쓴다

## 실패 징후

1. **jw 기준 — 정규화로 비교 품질이 올랐나.** 잴 값: 모의 추출값 24쌍 중 정답과 일치하는 쌍 수, 정규화 전과 후.
   정규화 전은 `strip()` 비교다. 착수 전 실측으로는 정답이 PDF에 글자 그대로 있는 것이 6/24(공급위치·공급규모 × 3)라
   정규화 전 값도 6 근처로 본다
   - 통과: 정규화 후 22/24 이상, 그리고 §정규화 결과가 같아지면 안 되는 것 5개 테스트 전부 통과
   - 다시 잰다: 정규화 후 18~21. 안 맞는 쌍마다 원인을 「정규화 부족」과 「정답 쪽 차이(값 자체가 다르다)」로 나눠
     리포트에 적고, 정규화 부족인 것만 고친 뒤 다시 잰다
   - 미완: 정규화 후 17 이하 / 같아지면 안 되는 경우가 하나라도 같아진다 / 정규화 전 값을 출력하지 않는다
2. **모의 추출값을 정답에 맞춰 만들었다** — 모의값이 PDF 해당 쪽에 없으면 미완. 2번 통과 기준의 테스트가 이것을 잡는다
3. **stub 정확도가 0%가 아니다** — 하나라도 0%보다 크면 정규화가 빈 값을 채운 것이다. 미완

## 파일

```
src/cheongyak_extract/normalize.py   종류별 함수 + normalize(field, value) -> str | None
src/cheongyak_extract/extract.py     FIELDS 옆에 필드 종류 표(dict) — 한 곳에서만 정한다
src/cheongyak_extract/report.py      정확도 비교만 정규형으로 바꾼다
src/cheongyak_extract/__main__.py    measure-normalize 하위 명령
tests/fixtures/pdf_forms.json        {pbno: {field: {"value": ..., "page": n}}}
tests/test_normalize.py              종류별 + 같아지면 안 되는 5개
reports/normalize.md                 측정 결과 (커밋한다)
```

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

### Task 1 — 모의 추출값 fixture
- `data/raw/<pbno>/notice.pdf`를 `pdf_text.pages()`로 읽어 8필드마다 PDF에 적힌 꼴을 찾아 옮긴다. 쪽 번호를 같이 적는다
  - 여러 곳에 나오면 1쪽 「단지 주요정보」 표 쪽을 우선한다
  - PDF에서 못 찾은 필드는 `null`로 두고 리포트에 적는다. 지어내지 않는다
- 테스트: 각 값이 그 쪽 텍스트에 있다(공백 무시)
- 커밋: `test: PDF에 적힌 꼴 그대로의 모의 추출값 24쌍 추가`

### Task 2 — 측정 명령, 정규화 전 값
- `measure-normalize`가 지금 비교(`strip()` 일치)로 24쌍 일치 수를 낸다. 정규화 함수가 아직 없으니 전·후가 같은 값이다
- 이 시점 숫자를 커밋 메시지 본문에 남긴다
- 커밋: `feature: 정규화 효과 측정 명령`

### Task 3 — 날짜·기간·월
- 날짜: `2026-10-23 (헤럴드경제신문)`, `2026.10.23.(금)` → `2026-10-23`
- 기간: `2026-11-23 ~ 2026-11-25`, `2026.11.23.(월)~\n2026.11.25.(수)` → `2026-11-23~2026-11-25`
- 월: `2029.08`, `2029년08월`, `2029년 8월` → `2029-08`
- 커밋: `feature: 날짜·기간·월 정규화`

### Task 4 — 회사명·세대수·주소
- 회사명: `(주)`·`㈜`·`주식회사` 제거, 공백 제거. 여러 회사면 `,`로 나눠 정렬한 목록
- 세대수: `358세대`, `358 세대`, `총 358세대` → `358`
- 주소: 공백·괄호 앞뒤 공백 정리만
- 커밋: `feature: 회사명·세대수·주소 정규화`

### Task 5 — 비교에 연결
- `report.metrics()` 정확도 비교를 `normalize(field, ...)` 양쪽 비교로 바꾼다. 빈 값 판정은 원본 기준 그대로
- 같아지면 안 되는 5개 테스트, stub 정확도 0% 테스트
- `measure-normalize`를 다시 돌려 `reports/normalize.md`를 쓴다
- 커밋: `feature: 정확도 비교를 정규형으로 바꾼다`

### Task 6 — 18~21이면 원인 분류 후 고치기 (실패 징후 1 「다시 잰다」)
- 22 이상이면 이 Task는 건너뛰고 그 사실을 PR 본문에 적는다

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 120 uv run python -m cheongyak_extract measure-normalize; echo EXIT=$?`
   - `run --n 3`은 청약홈에 요청을 보낸다. 받아 둔 `data/raw/`로 돌리는 경로가 없으면 이번에는 다시 돌리지 않고, 통과 기준 5는 테스트로 확인한다
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~6이 전부 참이다. 6은 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1·2·3을 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫)
- [ ] `reports/normalize.md`가 커밋돼 있고 PR 본문에 그 표를 그대로 붙였다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과(정규화 전 n/24 → 후 m/24)
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] 백그라운드 shell에서 `ls`를 부르지 않는다(이 기기에서 `eza`로 alias돼 있어 #146에서 끝나지 않고 세션을 붙잡았다). 필요하면 `/bin/ls`
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] `data/raw`(심볼릭 링크)를 커밋하지 않았다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#148] feature: 비교 전에 정답과 추출값을 같은 꼴로 정규화한다`
- [ ] Notion `PR` 프로퍼티를 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-8183-a93b-d9429f8dfb46 -
  ```
