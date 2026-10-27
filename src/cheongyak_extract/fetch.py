"""청약홈 목록·상세·공고문 PDF 수집. 요청은 순서대로, 사이마다 2초 쉰다."""

import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
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
BLOCK_CODES = (403, 429)
MAX_BLOCKS_IN_A_ROW = 3
ALWAYS_SKIP = {"2026000531"}  # 공고문 링크가 없는 공고(설계 §다듬는 데 쓰는 공고와 재는 공고)


class Skipped(Exception):
    """이 공고는 PDF를 못 받아 건너뛴다. 메시지가 리포트에 적힐 이유다."""


def list_url(page: int) -> str:
    return f"{BASE}/selectAPTLttotPblancListView.do?pageIndex={page}"


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


class FetchResult(NamedTuple):
    fetched: list[str]  # 이번에 받은 공고 번호
    skipped: list[tuple[str, str]]  # (pblancNo, 이유)
    stopped: str | None  # n건을 못 채우고 멈춘 이유. 채웠으면 None


def fetch_notices(
    client: httpx.Client,
    raw_dir: Path,
    start_page: int,
    n: int,
    pause: Callable[[float], None] = time.sleep,
) -> FetchResult:
    """목록 start_page쪽부터 PDF가 있는 공고를 n건 받는다.

    notice.pdf가 이미 있는 공고와 ALWAYS_SKIP은 요청 없이 건너뛴다. 403·429(목록 요청 포함)가
    MAX_BLOCKS_IN_A_ROW번 연속이면 멈춘다. 그 사이에 막힘이 아닌 결과(받음·링크 없음·500·
    타임아웃)가 한 번이라도 끼면 연속이 끊긴다. 멈춤 메시지의 코드는 마지막 막힘의 코드다.
    목록 요청이 막힘이 아닌 이유로 실패하면 바로 멈춘다.
    """
    fetched: list[str] = []
    skipped: list[tuple[str, str]] = []
    seen: set[str] = set()
    blocks = 0
    page = start_page
    while len(fetched) < n:
        pause(PAUSE_SECONDS)
        try:
            listing = client.get(list_url(page))
            listing.raise_for_status()
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code not in BLOCK_CODES:
                return FetchResult(fetched, skipped, f"목록 {page}쪽 요청 실패: {e}")
            blocks += 1
            if blocks == MAX_BLOCKS_IN_A_ROW:
                return FetchResult(fetched, skipped, f"{code} {blocks}번 연속")
            continue  # 같은 쪽을 다시 요청한다
        except httpx.HTTPError as e:
            return FetchResult(fetched, skipped, f"목록 {page}쪽 요청 실패: {e}")
        blocks = 0
        rows = [r for r in parse_list(listing.text) if r[1] not in seen]
        if not rows:
            return FetchResult(fetched, skipped, "목록 끝")
        for hmno, pbno, honm in rows:
            if len(fetched) == n:
                break
            seen.add(pbno)
            if pbno in ALWAYS_SKIP or (raw_dir / pbno / "notice.pdf").exists():
                continue
            try:
                download(client, hmno, pbno, honm, raw_dir, pause)
            except Skipped as e:
                skipped.append((pbno, str(e)))
                blocks = 0
                continue
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                skipped.append((pbno, f"다운로드 실패: {code}"))
                if code in BLOCK_CODES:
                    blocks += 1
                    if blocks == MAX_BLOCKS_IN_A_ROW:
                        return FetchResult(fetched, skipped, f"{code} {blocks}번 연속")
                else:
                    blocks = 0
                continue
            except httpx.HTTPError as e:
                skipped.append((pbno, f"다운로드 실패: {e}"))
                blocks = 0
                continue
            fetched.append(pbno)
            blocks = 0
        page += 1
    return FetchResult(fetched, skipped, None)
