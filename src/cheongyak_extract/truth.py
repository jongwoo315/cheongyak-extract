"""상세 HTML 표에서 정답 필드를 읽는다. 값은 칸 안 공백만 하나로 접고 그대로 둔다."""

import re

from bs4 import BeautifulSoup, Tag

from cheongyak_extract.extract import FIELDS


def _text(el: Tag) -> str | None:
    return " ".join(el.get_text().split()) or None


def _table(soup: BeautifulSoup, caption: str) -> Tag | None:
    cap = soup.find("caption", string=re.compile(re.escape(caption)))
    return cap.find_parent("table") if cap else None


def parse_truth(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, str | None] = {}

    # 주요정보: 첫 칸이 라벨, 둘째 칸이 값
    if table := _table(soup, "주요정보"):
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) == 2 and (label := _text(tds[0])):
                found[label] = _text(tds[1])

    # 청약일정: th(row)가 라벨, 같은 줄 첫 td가 값
    if table := _table(soup, "청약일정"):
        for tr in table.select("tbody tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td and (label := _text(th)):
                found[label] = _text(td)

    # 기타사항: thead th가 라벨, tbody 첫 줄 같은 순서 td가 값
    if table := _table(soup, "기타사항"):
        labels = [_text(th) for th in table.select("thead th")]
        row = table.select_one("tbody tr")
        for label, td in zip(labels, row.find_all("td") if row else [], strict=False):
            if label:
                found[label] = _text(td)

    # 입주예정월은 표 밖 안내 문구에 있다
    for li in soup.find_all("li"):
        if m := re.search(r"입주예정월\s*:\s*(\S+)", li.get_text()):
            found["입주예정월"] = m.group(1)

    return {f: found.get(f) for f in FIELDS}
