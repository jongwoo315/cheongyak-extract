from cheongyak_extract import resident_bound as rb

BLOCK = ["2순위 : ①지역\n■ ①지역 : 해당지역 거주자\n\n둘째 줄\n■ 끝"]


def test_snap_records_rule_page_chars_and_text_lines_of_the_chosen_block():
    got = rb.snap({"A": BLOCK, "B": ["표지"]})
    assert got["A"]["rule"] == 1 and got["A"]["page"] == 1
    assert got["A"]["lines"] == 2  # 빈 줄은 안 센다
    assert got["A"]["chars"] == len(got["A"]["text"])
    assert got["B"] == {"rule": None, "page": None, "chars": 0, "lines": 0, "text": ""}
