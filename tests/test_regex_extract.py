from cheongyak_extract.extract import EMPTY, FIELDS
from cheongyak_extract.regex_extract import regex_extract

PAGE1 = """\
GTX운정중앙역 시티프라디움 4단지 입주자모집공고
■ 금회 입주자모집공고일인 2026. 10. 23. 기준입니다.
■ 우선공급 대상자는 금회 당첨자발표일인 2026. 11. 11.을 기준으로 당첨자로 전산관리됩니다.
"""
LOCATION_LINE = (
    "■ 공급위치  : 경기도 파주시 파주운정3지구 주상복합 4블록(경기도 파주시 동패동 400-7번지 일원)"
)
SCALE_LINE = (
    "■ 공급규모  : 아파트 지하 4층, 지상 45층 총472세대 중 사전당첨 취소자 우선공급 114세대, "
    "일반분양 358세대[특별공급 230세대"
)
PAGE2 = f"""\
{LOCATION_LINE}
{SCALE_LINE}
■ 입주시기  : 2030년 07월 예정(정확한 입주일자는 추후 통보함)
■ 정당계약 : 2026.11.25.(수) ~ 11.29.(일)
  구분           사업주체                                   시공사
  상호         ㈜넥스트건설            주식회사 시티건설            주식회사 시티
"""


def test_every_field_is_a_key_even_when_nothing_is_found():
    got = regex_extract(["아무 라벨도 없는 쪽"])
    assert tuple(got) == FIELDS
    assert all(v == EMPTY for v in got.values())


def test_empty_pages_give_all_empty():
    assert all(v == EMPTY for v in regex_extract([]).values())


def test_each_field_gets_value_evidence_and_page_of_the_matching_line():
    got = regex_extract([PAGE1, PAGE2])
    expected = {
        "공급위치": (LOCATION_LINE.split(" : ")[1], 2),
        "공급규모": ("358세대", 2),
        "모집공고일": ("2026. 10. 23.", 1),
        "당첨자 발표일": ("2026. 11. 11.", 1),
        "계약일": ("2026.11.25. ~ 2026.11.29.", 2),
        "시행사": ("㈜넥스트건설", 2),
        "시공사": ("주식회사 시티건설, 주식회사 시티", 2),
        "입주예정월": ("2030년 07월", 2),
    }
    for field, (value, page) in expected.items():
        ex = got[field]
        assert (ex.value, ex.page) == (value, page), field
        assert ex.evidence and ex.evidence in [PAGE1, PAGE2][page - 1], field


def test_evidence_is_the_whole_line_the_pattern_hit():
    ex = regex_extract([PAGE2])["공급위치"]
    assert ex.evidence == LOCATION_LINE


def test_supply_scale_without_general_sale_takes_the_last_household_count():
    page = "■ 공급규모  : 아파트 지하 3층, 지상 29층 7개동 총 525세대 중 조합원취소분 39세대\n"
    assert regex_extract([page])["공급규모"].value == "39세대"


def test_supply_scale_label_with_detail_suffix():
    page = (
        "■ 공급규모 및 내역  : 지하 3층, 지상 1층~29층 아파트 9개동 총 1,128세대 및 부대복리시설\n"
    )
    assert regex_extract([page])["공급규모"].value == "1,128세대"


def test_supply_scale_total_only():
    page = "■ 공급규모  : 아파트 지하 2층, 지상 29층 10개동 총 992세대\n"
    assert regex_extract([page])["공급규모"].value == "992세대"


def test_supply_scale_keeps_thousands_comma():
    page = "■ 공급규모  : 총 2,706세대 중 일반분양 1,289세대(조합원 1,260세대 제외)\n"
    assert regex_extract([page])["공급규모"].value == "1,289세대"


def test_contract_period_with_both_years():
    page = "정당계약 2026.11.16.(월) ~ 2026.11.18.(수)\n"
    assert regex_extract([page])["계약일"].value == "2026.11.16. ~ 2026.11.18."


def test_announcement_date_on_label_line_of_schedule_table():
    page = "                  당첨자발표                             2026.11.26.(목) 16:00 이후\n"
    assert regex_extract([page])["당첨자 발표일"].value == "2026.11.26."


def test_move_in_month_from_table_row_without_colon():
    page = " 입주예정시기                          2027. 05. 말(예정)\n"
    assert regex_extract([page])["입주예정월"].value == "2027. 05"


def test_first_hit_wins_and_page_follows_it():
    pages = [
        "앞쪽\n",
        "최초 입주자모집공고일은 2026.10.16.입니다\n",
        "입주자모집공고일 2026.01.01.\n",
    ]
    got = regex_extract(pages)
    assert (got["모집공고일"].value, got["모집공고일"].page) == ("2026.10.16.", 2)


def test_labels_without_value_stay_empty():
    page = "■ 공급위치  :\n당첨자발표일은 추후 공지합니다\n입주예정월 미정\n"
    got = regex_extract([page])
    assert got["공급위치"] == EMPTY
    assert got["당첨자 발표일"] == EMPTY
    assert got["입주예정월"] == EMPTY


def test_company_row_needs_a_business_owner_header_above():
    page = "  상호         ㈜가나다          ㈜라마바\n"
    got = regex_extract([page])
    assert got["시행사"] == EMPTY
    assert got["시공사"] == EMPTY


def test_company_row_supervision_table_is_not_taken_as_business_owner():
    page = "  구 분     건축감리     전기감리\n  회사명     ㈜가나다     ㈜라마바\n"
    got = regex_extract([page])
    assert got["시행사"] == EMPTY
    assert got["시공사"] == EMPTY


def test_company_with_pdf_artifact_for_the_corporation_mark_is_restored():
    # ㈜가 PDF 텍스트에서 `주(   )`로 풀려 나온다. 안의 공백이 칸 구분으로 읽히면 안 된다
    page = "  구분   사업주체  시공업체\n  상호명   케이비부동산신탁주(   )    ㈜ 포스코이앤씨\n"
    got = regex_extract([page])
    assert got["시행사"].value == "케이비부동산신탁(주)"
    assert got["시공사"].value == "㈜ 포스코이앤씨"


def test_business_owner_label_line_is_the_fallback_when_there_is_no_company_row():
    page = "  사업주체              서울주택도시개발공사\n"
    got = regex_extract([page])
    assert got["시행사"].value == "서울주택도시개발공사"
    assert got["시공사"] == EMPTY


def test_company_row_wins_over_an_earlier_business_owner_label_line():
    page = "  사업주체     ㈜앞줄\n  구분   사업주체  시공사\n  상호   ㈜표회사    ㈜시공\n"
    assert regex_extract([page])["시행사"].value == "㈜표회사"


def test_single_company_cell_gives_only_the_business_owner():
    page = "  구분    사업주체\n  상호      ㈜반도건설\n"
    got = regex_extract([page])
    assert got["시행사"].value == "㈜반도건설"
    assert got["시공사"] == EMPTY
