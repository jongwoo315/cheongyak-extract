"""청약홈 목록·상세·공고문 PDF 수집. 요청은 순서대로, 사이마다 2초 쉰다."""

import re
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup

from cheongyak_extract.pdf_text import pdf_problem

BASE = "https://www.applyhome.co.kr/ai/aia"
LIST_URL = f"{BASE}/selectAPTLttotPblancListView.do?pageIndex=1"
DETAIL_URL = f"{BASE}/selectAPTLttotPblancDetail.do"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PAUSE_SECONDS = 2
RETRY_PAUSES = (5, 15)  # 5xx·타임아웃·연결 끊김이면 이만큼 쉬고 다시 보낸다. 2초 대신이다
BLOCK_CODES = (403, 429)
MAX_BLOCKS_IN_A_ROW = 3
ALWAYS_SKIP = {"2026000531"}  # 공고문 링크가 없는 공고(설계 §다듬는 데 쓰는 공고와 재는 공고)


class Skipped(Exception):
    """이 공고는 PDF를 못 받아 건너뛴다. 메시지가 리포트에 적힐 이유다."""


class BadPdf(Skipped):
    """받은 PDF가 열리지 않는다. 수집 대상이 아닌 공고와 달리 오류로 센다(설계 §오류)."""


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


def is_pdf(name: str | None, body: bytes) -> bool:
    return bool(name and name.lower().endswith(".pdf")) or body.startswith(b"%PDF-")


def _request(
    client: httpx.Client,
    method: str,
    url: str,
    kind: str,
    pause: Callable[[float], None],
    retries: Counter[str],
    **kwargs,
) -> httpx.Response:
    """요청 앞에 2초 쉰다. 5xx·타임아웃·연결 끊김이면 RETRY_PAUSES만큼 쉬고 다시 보낸다.

    403·429·그 밖의 4xx는 다시 보내지 않고 바로 raise_for_status로 올린다.
    다시 보낸 횟수는 retries[kind]에 센다. 다 실패하면 마지막 예외(상태 오류 포함)를 올린다.
    """
    for attempt in range(len(RETRY_PAUSES) + 1):
        if attempt:
            retries[kind] += 1
        pause(PAUSE_SECONDS if attempt == 0 else RETRY_PAUSES[attempt - 1])
        try:
            resp = client.request(method, url, **kwargs)
        except httpx.TransportError:
            if attempt == len(RETRY_PAUSES):
                raise
            continue
        if resp.status_code >= 500 and attempt < len(RETRY_PAUSES):
            continue
        resp.raise_for_status()
        return resp
    raise AssertionError("unreachable")  # 마지막 시도는 위에서 돌려주거나 올린다


def download(
    client: httpx.Client,
    hmno: str,
    pbno: str,
    honm: str,
    raw_dir: Path,
    pause: Callable[[float], None] = time.sleep,
    retries: Counter[str] | None = None,
) -> Path:
    """상세 HTML과 공고문 PDF를 raw_dir/<pbno>/에 쓰고 그 디렉터리를 돌려준다."""
    retries = Counter() if retries is None else retries
    form = {"houseManageNo": hmno, "pblancNo": pbno, "houseNm": honm}
    resp = _request(client, "POST", DETAIL_URL, "detail", pause, retries, data=form)
    out = raw_dir / pbno
    out.mkdir(parents=True, exist_ok=True)
    (out / "detail.html").write_text(resp.text, encoding="utf-8")

    links = pdf_links(resp.text)
    if not links:
        raise Skipped("상세에 공고문 링크 없음")
    for url in links:
        pdf = _request(client, "GET", url, "pdf", pause, retries)
        name = filename_from_disposition(pdf.headers.get("content-disposition"))
        if not is_pdf(name, pdf.content):
            continue
        # 끊긴 바이트가 notice.pdf로 남으면 다음 실행이 건너뛴다(#147 리뷰 defer 7)
        part = out / "notice.pdf.part"
        part.write_bytes(pdf.content)
        if problem := pdf_problem(part):
            part.unlink()
            raise BadPdf(f"열리지 않는 PDF: {problem}")
        part.replace(out / "notice.pdf")
        return out
    raise Skipped("첨부가 PDF가 아님")


def _has_readable_pdf(out: Path) -> bool:
    pdf = out / "notice.pdf"
    return pdf.exists() and pdf_problem(pdf) is None


class FetchResult(NamedTuple):
    fetched: list[str]  # 이번에 받은 공고 번호
    skipped: list[tuple[str, str]]  # (pblancNo, 이유)
    stopped: str | None  # n건을 못 채우고 멈춘 이유. 채웠으면 None
    retries: dict[str, int] = {}  # 다시 보낸 요청 수. 키는 list·detail·pdf


def fetch_notices(
    client: httpx.Client,
    raw_dir: Path,
    start_page: int,
    n: int,
    pause: Callable[[float], None] = time.sleep,
) -> FetchResult:
    """목록 start_page쪽부터 PDF가 있는 공고를 n건 받는다.

    열리는 notice.pdf가 이미 있는 공고와 ALWAYS_SKIP은 요청 없이 건너뛴다.
    5xx·타임아웃·연결 끊김은 요청마다 두 번까지 다시 보낸다(_request). 403·429(목록 요청 포함)가
    MAX_BLOCKS_IN_A_ROW번 연속이면 멈춘다. 그 사이에 막힘이 아닌 결과(받음·링크 없음·500·
    타임아웃)가 한 번이라도 끼면 연속이 끊긴다. 멈춤 메시지의 코드는 마지막 막힘의 코드다.
    목록 요청이 막힘이 아닌 이유로 실패하면 바로 멈춘다.
    """
    fetched: list[str] = []
    skipped: list[tuple[str, str]] = []
    retries: Counter[str] = Counter()
    seen: set[str] = set()
    blocks = 0
    page = start_page

    def finish(stopped: str | None) -> FetchResult:
        return FetchResult(fetched, skipped, stopped, dict(retries))

    while len(fetched) < n:
        try:
            listing = _request(client, "GET", list_url(page), "list", pause, retries)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code not in BLOCK_CODES:
                return finish(f"목록 {page}쪽 요청 실패: {e}")
            blocks += 1
            if blocks == MAX_BLOCKS_IN_A_ROW:
                return finish(f"{code} {blocks}번 연속")
            continue  # 같은 쪽을 다시 요청한다
        except httpx.HTTPError as e:
            return finish(f"목록 {page}쪽 요청 실패: {type(e).__name__}: {e}")
        blocks = 0
        rows = [r for r in parse_list(listing.text) if r[1] not in seen]
        if not rows:
            if not seen:  # 한 건도 못 본 채 비었다면 끝이 아니라 차단 페이지·마크업 변경이다
                return finish(f"목록 {page}쪽이 비어 있음(차단·마크업 변경 의심)")
            return finish("목록 끝")
        for hmno, pbno, honm in rows:
            if len(fetched) == n:
                break
            seen.add(pbno)
            if pbno in ALWAYS_SKIP or _has_readable_pdf(raw_dir / pbno):
                continue
            try:
                download(client, hmno, pbno, honm, raw_dir, pause, retries)
            except Skipped as e:  # BadPdf도 여기서 건너뜀으로 센다
                skipped.append((pbno, str(e)))
                blocks = 0
                continue
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                skipped.append((pbno, f"다운로드 실패: {code}"))
                if code in BLOCK_CODES:
                    blocks += 1
                    if blocks == MAX_BLOCKS_IN_A_ROW:
                        return finish(f"{code} {blocks}번 연속")
                else:
                    blocks = 0
                continue
            except httpx.HTTPError as e:
                skipped.append((pbno, f"다운로드 실패: {type(e).__name__}: {e}"))
                blocks = 0
                continue
            fetched.append(pbno)
            blocks = 0
        page += 1
    return finish(None)
