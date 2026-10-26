"""공고문 쪽별 텍스트에서 필드를 뽑는다."""

import re
from dataclasses import dataclass


def _blank(s: str | None) -> bool:
    return not (s or "").strip()


@dataclass(frozen=True)
class Extraction:
    value: str | None
    evidence: str | None
    page: int | None  # 1부터

    def __post_init__(self) -> None:
        if _blank(self.value):
            if not _blank(self.evidence) or self.page is not None:
                raise ValueError("값이 없는데 근거나 쪽이 있다")
        elif _blank(self.evidence) or self.page is None:
            raise ValueError("값이 있는데 근거나 쪽이 없다")
        elif self.page < 1:
            raise ValueError(f"쪽은 1부터다: {self.page}")


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def grounded(evidence: str | None, text: str) -> bool:
    """근거 문장이 text 안에 있다. PDF는 줄이 끊기므로 양쪽 공백을 모두 지우고 비교한다."""
    if _blank(evidence):
        return False
    return _squash(evidence) in _squash(text)


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

# 필드마다 정규화 종류를 하나 붙인다. 종류별 함수는 normalize.py에 있다.
KIND = {
    "공급위치": "주소",
    "공급규모": "세대수",
    "모집공고일": "날짜",
    "당첨자 발표일": "날짜",
    "계약일": "기간",
    "시행사": "회사명",
    "시공사": "회사명",
    "입주예정월": "월",
}


# stub: #147에서 LLM 추출로 바꾼다
def extract(pages: list[str]) -> dict[str, Extraction]:
    return {f: Extraction(None, None, None) for f in FIELDS}
