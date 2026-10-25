# cheongyak-extract

청약 모집공고문 PDF에서 구조화된 필드를 뽑고, 청약홈 상세 페이지 표 값을 정답으로 필드별 eval 리포트를 낸다.

## 실행

```bash
uv run python -m cheongyak_extract run --n 3
```

명령 하나로 아래 흐름이 끝까지 돌고, 필드별 리포트 표가 stdout과 `reports/skeleton.md`에 나온다.
요청은 순서대로 보내고 사이마다 2초 쉰다. 받은 원본은 `data/raw/`에 두며 커밋하지 않는다.

## 흐름

```
fetch (목록 → 상세 HTML → 공고문 PDF)  →  data/raw/<pbno>/{detail.html, notice.pdf}
pdf_text (쪽마다 텍스트)                →  list[str]
extract (stub: 전 필드 빈 값)           →  {field: Extraction(value, evidence, page)}
truth (상세 HTML 표 → 정답 필드)        →  {field: str | None}
compare + report (필드별 지표 표)       →  stdout + reports/skeleton.md
```

## 현재 상태

- 추출은 아직 stub이다. 모든 필드를 빈 값으로 돌려주므로 정확도 0%, 빈 칸 100%가 정상이다
- 첫 실행 결과: [reports/skeleton.md](reports/skeleton.md)
- 이후 티켓이 stub을 하나씩 실제 구현으로 바꾼다. LLM 추출은 #147이다

## 테스트

```bash
uv run pytest
```

네트워크 없이 돈다. 수집 코드는 `httpx.MockTransport`로, PDF는 테스트 안에서 pymupdf로 만든다.
