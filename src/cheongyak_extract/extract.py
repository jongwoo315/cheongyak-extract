"""공고문 쪽별 텍스트에서 필드를 뽑는다."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Extraction:
    value: str | None
    evidence: str | None
    page: int | None


# 상세 HTML 표에서 한 칸 값으로 읽히는 필드. 정답(truth.py)과 같은 키를 쓴다.
FIELDS = (
    "공급위치",
    "공급규모",
    "모집공고일",
    "당첨자 발표일",
    "계약일",
    "시행사",
    "시공사",
    "입주예정월",
)


# stub: #147에서 LLM 추출로 바꾼다
def extract(pages: list[str]) -> dict[str, Extraction]:
    return {f: Extraction(None, None, None) for f in FIELDS}
