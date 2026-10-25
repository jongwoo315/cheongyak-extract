"""청약홈 목록·상세·공고문 PDF 수집. 요청은 순서대로, 사이마다 2초 쉰다."""

import re
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

BASE = "https://www.applyhome.co.kr/ai/aia"
LIST_URL = f"{BASE}/selectAPTLttotPblancListView.do?pageIndex=1"
DETAIL_URL = f"{BASE}/selectAPTLttotPblancDetail.do"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PAUSE_SECONDS = 2


class Skipped(Exception):
    """이 공고는 PDF를 못 받아 건너뛴다. 메시지가 리포트에 적힐 이유다."""


def make_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)


def parse_list(html: str) -> list[tuple[str, str, str]]:
    """목록 HTML -> [(houseManageNo, pblancNo, houseNm), ...]"""
    soup = BeautifulSoup(html, "html.parser")
    return [
        (tr["data-hmno"], tr["data-pbno"], tr["data-honm"]) for tr in soup.select("tr[data-pbno]")
    ]


def pdf_links(detail_html: str) -> list[str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    return [a["href"] for a in soup.select("a[href*='getAtchmnfl.do']")]


def filename_from_disposition(header: str | None) -> str | None:
    # 응답마다 `filename="..."`과 `filename*=UTF-8''...` 두 꼴이 섞여 온다
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", header or "")
    return unquote(m.group(1)) if m else None


def download(
    client: httpx.Client,
    hmno: str,
    pbno: str,
    honm: str,
    raw_dir: Path,
    pause: Callable[[float], None] = time.sleep,
) -> Path:
    """상세 HTML과 공고문 PDF를 raw_dir/<pbno>/에 쓰고 그 디렉터리를 돌려준다."""
    pause(PAUSE_SECONDS)
    resp = client.post(DETAIL_URL, data={"houseManageNo": hmno, "pblancNo": pbno, "houseNm": honm})
    resp.raise_for_status()
    out = raw_dir / pbno
    out.mkdir(parents=True, exist_ok=True)
    (out / "detail.html").write_text(resp.text, encoding="utf-8")

    links = pdf_links(resp.text)
    if not links:
        raise Skipped("상세에 공고문 링크 없음")
    for url in links:
        pause(PAUSE_SECONDS)
        pdf = client.get(url)
        pdf.raise_for_status()
        name = filename_from_disposition(pdf.headers.get("content-disposition"))
        if name and name.lower().endswith(".pdf"):
            (out / "notice.pdf").write_bytes(pdf.content)
            return out
    raise Skipped("첨부가 PDF가 아님")
