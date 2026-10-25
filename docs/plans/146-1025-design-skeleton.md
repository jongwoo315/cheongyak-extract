# #146 skeleton — 설계

**Notion:** #146 https://app.notion.com/p/skeleton-3-PDF-stub-40441e6165c08153a151f96bd75450a4

## 목적

청약 모집공고문 PDF에서 필드를 뽑는 시스템의 입력부터 리포트까지를 한 번 끝까지 돌린다.
추출 단계는 stub이다. 이후 티켓(#147~#152)은 이 흐름을 유지한 채 stub 하나씩을 실제
구현으로 바꾼다. 핵심 산출물은 모델 호출 코드가 아니라 필드별 eval 리포트다
(Dev Scraps 「AI 엔지니어와 백엔드 엔지니어의 산출물 비교」 예시 2).

## 흐름

```
fetch (목록 → 상세 HTML → 공고문 PDF)  →  data/raw/<pbno>/{detail.html, notice.pdf}
pdf_text (쪽마다 텍스트)                →  list[str]
extract (stub: 전 필드 빈 값)           →  {field: Extraction(value, evidence, page)}
truth (상세 HTML 표 → 정답 필드)        →  {field: str | None}
compare + report (필드별 지표 표)       →  stdout + reports/skeleton.md
```

## 설계 결정

| 결정 | 고른 것 | 이유 |
| --- | --- | --- |
| 패키지 관리 | uv + Python 3.11 | cheongyak-rag와 같다. 같은 기기에서 도구를 하나로 둔다 |
| PDF 텍스트 | pymupdf | cheongyak-rag가 이미 쓴다. 쪽 번호를 그대로 준다 |
| HTML 파싱 | beautifulsoup4 | 표 6개를 caption으로 찾고 th/td 쌍을 읽는다. stdlib `html.parser`로 표를 직접 걷는 코드는 rowspan에서 깨지기 쉽다 |
| HTTP | httpx | cheongyak-rag와 같다 |
| extract() 반환형 | 필드마다 `Extraction(value, evidence, page)` | #147(LLM)이 근거 문장과 쪽 번호를 같이 낸다. 지금 모양을 정해 두면 #147은 함수 본문만 바꾼다 |
| 비교 | 문자열 정확 일치 (strip만) | 정규화는 #148의 stub 자리다. 여기서 하면 #148이 바꿀 것이 없다 |
| 원본 데이터 | `data/raw/`는 커밋하지 않는다 | 공고문 PDF는 재배포 대상이 아니다. 테스트는 `tests/fixtures/`의 작은 파일로 돌린다 |

## 리포트 지표 (필드마다, 공고 N건 기준)

| 열 | 정의 | stub에서 기대값 |
| --- | --- | --- |
| 정답 있음 | 정답이 빈 값이 아닌 공고 수 | 1 이상 |
| 정확도 | 정답 있음 중 추출값 == 정답 | 0% |
| 빈 칸 | 정답 있음 중 추출값이 빈 값 | 100% |
| 지어낸 값 | 추출값이 있고 근거 문장이 PDF 텍스트에 없는 수 | 0 |
| 비어야 하는데 채움 | 정답이 빈 공고 중 추출값이 채워진 수 | 0 |
| 근거 위치 맞음 | 근거 쪽 번호가 있는 것 중 그 쪽 텍스트에 근거 문장이 있는 비율 | 분모 0 → `—` |

## 열린 질문 (루프가 실물을 보고 정한다)

- 정답 필드 목록: 상세 HTML 표 6개에서 값이 한 칸으로 읽히는 필드만 고른다. 표 안의 반복 행
  (주택형별 공급세대수 등)은 이번 범위가 아니다
- 공고 3건 고르는 법: 목록 1쪽 위에서부터, 공고문 PDF 링크가 있는 APT 공고 3건

## 이용약관 (2026-10-25 확인)

- 청약홈 메인 하단에 이용약관 링크가 없다. 있는 것은 개인정보처리방침·이메일 추출방지정책·
  보안프로그램 등이다
- `robots.txt`는 200으로 오지만 본문이 「요청한 URL을 찾을 수 없다」 HTML이다(실제 파일 없음)
- 웹 검색으로도 청약홈 약관의 수집 금지 조항을 찾지 못했다
- 그래서 요청량을 최소로 둔다: 공고 3건이면 목록 1회 + 상세 3회 + PDF 3회, 요청 사이 2초 이상
