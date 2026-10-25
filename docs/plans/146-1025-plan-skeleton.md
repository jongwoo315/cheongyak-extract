# #146 skeleton — 구현 계획

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
**Notion:** #146 https://app.notion.com/p/skeleton-3-PDF-stub-40441e6165c08153a151f96bd75450a4
**설계:** /Users/jw/prv/.wt/146-skeleton/docs/plans/146-1025-design-skeleton.md (먼저 읽는다)

## jw 기준

명령 하나로 1~5가 돌고 리포트가 나온다. stub이므로 정확도 0%, 빈칸 100%가 정상이다

## 통과 기준

1. `uv run python -m cheongyak_extract run --n 3` 한 번으로 아래 1~5가 끝나고 exit code 0이다
   1. 공고 3건의 상세 HTML과 공고문 PDF를 받아 `data/raw/<pblancNo>/`에 둔다
   2. PDF에서 쪽마다 텍스트를 뽑는다
   3. `extract()` stub이 모든 필드를 빈 값으로 반환한다
   4. 상세 HTML 표를 정답 필드로 파싱한다
   5. 필드별 리포트 표를 stdout에 출력하고 `reports/skeleton.md`에 쓴다
2. 리포트 열: 필드 / 정답 있음 / 정확도 / 빈 칸 / 지어낸 값 / 비어야 하는데 채움 / 근거 위치 맞음
   (정의는 설계 문서 §리포트 지표)
3. 모든 필드에서 정확도 0%, 빈 칸 100%, 지어낸 값 0, 비어야 하는데 채움 0
4. 모든 필드에서 정답 있음이 1 이상이다 (정답 파싱이 조용히 비면 빈 칸 100%가 공허하게 참이 된다)
5. `uv run pytest`가 네트워크 없이 통과한다. 끝까지 도는 테스트 1개 포함(fixture 입력 → 리포트)
6. GitHub Actions에서 같은 pytest가 green이다

## 이번에 안 하는 것

- LLM 추출 — #147
- 날짜·금액·세대수 정규화. 비교는 `strip()` 뒤 문자열 일치만 — #148
- 정답 수동 대조 — #149
- 공고 수 확대 — #151. `--n`은 받지만 3건 넘게 돌려 보지 않는다
- 표 안의 반복 행(주택형별 공급세대수, 공급금액 행) — 한 칸 값 필드만 다룬다
- 재시도·백오프·동시 요청. 요청은 순서대로, 사이마다 `time.sleep(2)`
- 잔여세대·오피스텔 등 APT 분양 목록 밖의 공고

## 실패 징후

1. **jw 기준 — 명령 하나로 끝까지 돌고 stub 값이 나오나**
   - 통과: 명령 1회, exit 0, 공고 3건 처리, 모든 필드 정확도 0%·빈 칸 100%·정답 있음 ≥ 1
   - 다시 잰다: 처리된 공고가 3건 미만(PDF 링크 없음, 다운로드 실패). 목록에서 다음 APT 공고로 바꿔
     3건을 채운 뒤 다시 돌린다. 건너뛴 공고와 이유를 리포트 아래에 적는다
   - 미완: 명령이 둘 이상 필요하다 / 어느 필드든 정확도 > 0% 또는 빈 칸 < 100% (stub인데 그러면
     비교나 정답 파싱이 틀렸다) / 어느 필드든 정답 있음 = 0
2. **정답 필드 수가 너무 적다** — 3개 미만이면 미완. 3~5개면 리포트 아래에 표에서 읽지 못한
   caption과 이유를 적는다. 6개 이상이면 정상
3. **테스트가 네트워크를 탄다** — `pytest`가 applyhome에 요청하면 미완. 수집 코드 테스트는 가짜
   응답(`httpx.MockTransport`)으로 한다

## 파일 구조

```
pyproject.toml            uv, Python 3.11, src 레이아웃
.python-version           3.11
src/cheongyak_extract/
  __init__.py
  __main__.py             CLI: `run --n N`
  fetch.py                목록 파싱, 상세 POST, PDF 다운로드, filename 추출
  pdf_text.py             pages(path) -> list[str]
  extract.py              Extraction dataclass, FIELDS, extract(pages) stub
  truth.py                parse_truth(html) -> dict[str, str | None]
  report.py               compare(), metrics(), render_markdown()
  pipeline.py             run(n, client) — 1~5를 잇는다
tests/
  fixtures/               작은 목록 HTML·상세 HTML 1개씩(실물에서 잘라낸 것), PDF는 테스트에서 pymupdf로 생성
  test_fetch.py test_pdf_text.py test_extract.py test_truth.py test_report.py test_pipeline.py
.github/workflows/test.yml  uv로 pytest
reports/skeleton.md       실제 3건으로 돌린 결과 (커밋한다)
```

의존성: `httpx`, `pymupdf`, `beautifulsoup4` / dev: `pytest`, `ruff`.

## 데이터 경로 (확인된 것)

출처: /Users/jw/prv/cheongyak-rag/docs/plans/0727-design-cheongyak-rag.md:62-136 (먼저 읽는다)

- 목록: `GET https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancListView.do?pageIndex=1`
  - `<tr data-pbno data-hmno data-honm>`에서 세 값을 읽는다
- 상세: `POST https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do`
  - form: `houseManageNo=<hmno>&pblancNo=<pbno>&houseNm=<honm>`
  - `<table>` 6개, caption: 입주자모집공고 주요정보 / 청약일정 / 공급대상 / 특별공급 공급대상 /
    공급금액, 2순위 청약금 / 기타사항
- PDF: 상세 HTML의 `<a href>`에 `https://static.applyhome.co.kr/ai/aia/getAtchmnfl.do?...` 절대 URL
  - Content-Type이 `application/octet-stream`이라 확장자는 `Content-Disposition`의 filename을
    URL 디코딩해 뽑는다. `.pdf`가 아니면 그 공고는 건너뛴다(실패 징후 1 「다시 잰다」)
- User-Agent는 일반 브라우저 문자열. 요청 사이 `time.sleep(2)`

## Tasks (TDD — 테스트 먼저, 실패 확인, 구현, 통과, 커밋. Task 하나 = 커밋 하나)

### Task 1 — 프로젝트 뼈대
- `uv init`이 아니라 위 파일 구조대로 직접 만든다. `pyproject.toml`은 cheongyak-rag
  (/Users/jw/prv/cheongyak-rag/pyproject.toml) 형식을 따른다(hatchling, `pythonpath = ["src"]`, ruff 100)
- `uv sync` 후 빈 테스트 1개로 `uv run pytest`가 도는지 확인
- 커밋: `init: uv 프로젝트 뼈대`

### Task 2 — 실물 fixture 저장 (네트워크는 이 Task와 Task 8에서만)
- 목록 1쪽과 상세 1건을 실제로 받아 `tests/fixtures/list.html`, `tests/fixtures/detail.html`에 둔다
  - 테스트에 필요 없는 부분(스크립트, 헤더·푸터)은 잘라 작게 만든다. 표 6개와 PDF 링크는 남긴다
- 상세 HTML을 보고 정답 필드 목록을 정한다 — 표 6개에서 한 칸 값으로 읽히는 것만
  (예: 공급위치, 공급규모, 모집공고일, 당첨자 발표일, 계약일, 시행사, 시공사, 입주예정월).
  실물에 없는 필드는 넣지 않는다
- 커밋: `test: 청약홈 목록·상세 fixture 추가`

### Task 3 — fetch.py
- 테스트: `parse_list(html)` → `[(hmno, pbno, honm), ...]` / `pdf_links(detail_html)` → URL 목록 /
  `filename_from_disposition(header)` → URL 디코딩된 파일명(`attachment; filename="...%EA%B3%A0..."`) /
  `download(...)`가 `httpx.MockTransport` 응답을 `data/raw/<pbno>/`에 쓴다
- 커밋: `feature: 청약홈 목록·상세·공고문 수집`

### Task 4 — pdf_text.py
- 테스트: pymupdf로 2쪽짜리 PDF를 만들어 `pages()`가 쪽별 텍스트 2개를 내는지
- 커밋: `feature: PDF 쪽별 텍스트 추출`

### Task 5 — extract.py stub
- `Extraction(value: str | None, evidence: str | None, page: int | None)`, `FIELDS` 튜플(Task 2에서 정한 것)
- `extract(pages: list[str]) -> dict[str, Extraction]` — 모든 필드 `Extraction(None, None, None)`
- 함수 위 한 줄: `# stub: #147에서 LLM 추출로 바꾼다`
- 커밋: `feature: extract stub`

### Task 6 — truth.py
- 테스트: `tests/fixtures/detail.html`로 `parse_truth()`가 FIELDS 전부를 키로 갖고, 값은 fixture에서
  눈으로 확인한 문자열과 같다(테스트에 기대값을 박는다)
- 커밋: `feature: 상세 HTML 표를 정답 필드로 파싱`

### Task 7 — report.py
- 테스트: 손으로 만든 정답·추출값 몇 건으로 각 지표 계산이 설계 문서 정의와 맞는지
  (정확도 분모 = 정답 있음, 근거 위치 맞음 분모 0이면 `—`)
- `render_markdown()`은 마크다운 표 문자열
- 커밋: `feature: 필드별 eval 리포트`

### Task 8 — pipeline + CLI + 끝까지 도는 테스트
- `run(n, client, raw_dir, report_path)`가 1~5를 잇는다. `__main__`은 `run --n 3`을 파싱해 실제
  `httpx.Client`로 부른다
- 끝까지 도는 테스트: MockTransport가 fixture 목록·상세와 테스트에서 만든 PDF를 돌려주고, 결과
  리포트에서 모든 필드 정확도 0%·빈 칸 100%·정답 있음 ≥ 1을 assert
- 실제로 `uv run python -m cheongyak_extract run --n 3`을 한 번 돌려 `reports/skeleton.md`를 만든다
- 커밋: `feature: 명령 하나로 수집부터 리포트까지 연결`

### Task 9 — CI
- `.github/workflows/test.yml`: `astral-sh/setup-uv`, `uv sync`, `uv run pytest`
- 커밋: `add: GitHub Actions 테스트`

### Task 10 — README
- 실행 명령 한 줄, 흐름 그림(설계 문서 §흐름), `reports/skeleton.md` 링크, 「추출은 아직 stub」
- `## 판단 기록` 절은 건드리지 않는다(PR 게이트에서 따로 고친다)
- 커밋: `docs: README 실행 방법과 skeleton 리포트`

## Pre-PR checks (all required — do not assume pass, show output)

1. New env vars: `git diff main...HEAD` added lines matching `os\.environ\.get|os\.getenv|process\.env\.` — log any found.
2. Server boots — detached-safe, NO interactive Ctrl+C (no TTY in orch). Background + timeout + curl the port + kill. Never bare `runserver` (hangs the loop till ORCH_STUCK_SECS). Django → `source <venv>/bin/activate && cd web && (timeout 20 python manage.py runserver 127.0.0.1:8000 --noreload &) ; sleep 8; curl -sf http://127.0.0.1:8000/ -o /dev/null && echo BOOT_OK ; pkill -f runserver`; CDK → `cdk synth` (no server); Zappa/Lambda Django → same background+timeout with `PYENV_VERSION=<env> --settings=<app>.settings.local`; CLI/library → smoke-run the entrypoint (it must self-terminate); else project-specific.
   - 이 레포는 CLI다: `timeout 300 uv run python -m cheongyak_extract run --n 3; echo EXIT=$?`
3. Full test suite green (show pass/fail). If no runner: state `no tests — skipped`, do not silently pass.

Then: completeness via `sc:reflect` vs plan; code review via `superpowers:requesting-code-review` (fix all Critical/Important); commit (`~/prv` repo면 `docs/plans/`도 포함. `~/plab`·`~/work` repo는 `docs/plans/`를 커밋하지 않는다 — `rules/github.md` §회사 repo에 커밋하지 않는 것); PR via `gh pr create --assignee @me` (work title `[DEV-XXXX] type: 설명` + Summary/Changes/Test Plan/Jira; personal title + Summary/Changes/Notes, then update the Notion PR property). **PR을 만들면 이 루프는 끝난다** — 여기서 `pr-review-toolkit:review-pr`을 돌리지 말 것. 그 리뷰는 Phase C의 별도 세션이 맡는다. 여기서 돌리면 (a) 자기가 쓴 코드를 같은 컨텍스트가 리뷰하고 (b) PR 생성 후에도 커밋이 계속 얹혀 `orch ls`의 `done`이 완료를 뜻하지 않게 된다 (실측: PR 후 8분 이상 지속).

내장 `/code-review`를 여기 쓰지 말 것. 품질은 더 낫지만(다각도 finder + 후보별 독립 검증 CONFIRMED/PLAUSIBLE/REFUTED + failure_scenario 강제) **사람이 직접 치는 커맨드라 available-skills에 없다** — 헤드리스 세션에서 확인함. ralph가 호출하면 없는 스킬을 찾다 끝난다.

커밋 전 `superpowers:requesting-code-review`는 그대로 둔다 — 그건 커밋하기 전 자기 점검이고, Phase C는 커밋된 diff 전체를 새 컨텍스트가 다시 보는 것이라 겹치지 않는다.

## Done criteria

- [ ] 통과 기준 1~6이 전부 참이다. 6은 PR을 연 뒤 `gh pr checks`로 확인한다
- [ ] 실패 징후 1·2·3을 PR 본문에 측정값과 함께 적었다(어느 구간인지는 쓰지 않는다 — 판정은 jw 몫)
- [ ] `reports/skeleton.md`가 커밋돼 있고 PR 본문에 그 표를 그대로 붙였다
- [ ] PR 본문 맨 위에 `## 착수 전 기준 (jw)` 절 — 이 plan의 `## jw 기준` 원문 + 그 기준으로 잰 결과
- [ ] 커밋 메시지는 `rules/github.md` 접두사(`init` `feature` `add` `fix` `docs` `refactor` `test` `chore` `delete`) + `: ` + 한글. `type(scope):` 꼴 금지
- [ ] base 브랜치를 작업 브랜치에 merge·rebase하지 않았다
- [ ] PR: `gh pr create --base main --assignee @me`, 제목 `[#146] feature: 명령 하나로 수집부터 필드별 리포트까지 끝까지 돈다`
- [ ] Notion `PR` 프로퍼티를 PR URL로 갱신했다:
  ```bash
  python3 -c "import json,sys;print(json.dumps({'properties':{'PR':{'url':sys.argv[1]}}}))" "<PR_URL>" \
    | "$HOME/.claude/tools/notion-api/notion-api" PATCH /v1/pages/40441e61-65c0-8153-a151-f96bd75450a4 -
  ```
