from cheongyak_extract import resident_bound as rb

BLOCK = ["2순위 : ①지역\n■ ①지역 : 해당지역 거주자\n\n둘째 줄\n■ 끝"]


def test_snap_records_rule_page_chars_and_text_lines_of_the_chosen_block():
    got = rb.snap({"A": BLOCK, "B": ["표지"]})
    assert got["A"]["rule"] == 1 and got["A"]["page"] == 1
    assert got["A"]["lines"] == 2  # 빈 줄은 안 센다
    assert got["A"]["chars"] == len(got["A"]["text"])
    assert got["B"] == {"rule": None, "page": None, "chars": 0, "lines": 0, "text": ""}


SENT = "경쟁이 있을 경우 울산광역시 거주자가 우선합니다."
RULE3 = {"C": ["표지", f"앞\n5  일반공급 (제27조)\n  {SENT}\n다음"]}


def test_compare_reports_changed_notices_and_where_the_rule_3_sentence_is():
    before = {"A": {"rule": 1, "page": 1, "chars": 99, "lines": 9, "text": "x"}} | rb.snap(RULE3)
    texts = {"A": BLOCK} | RULE3
    md = rb.compare(before, texts, "cmd", "abc")
    assert "바뀐 공고 1건" in md  # A만 다르다
    assert "| C | 규칙 3 | 규칙 3 | 2쪽 2줄 「5  일반공급 (제27조)」 | 2쪽 3줄 | 예 |" in md
    assert "PDF 전체를 넘기는 공고: 0/2" in md
