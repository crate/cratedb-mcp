import os

import httpx
import pytest

from cratedb_mcp import tool
from cratedb_mcp.tool import query_sql


def test_times_come_back_as_iso_8601_text_except_inside_objects():
    result = query_sql(
        "SELECT '2025-02-06T05:15:36.123Z'::TIMESTAMPTZ, '2025-02-06T05:15:36'::TIMESTAMP, "
        "'1969-07-20T20:17:40Z'::TIMESTAMPTZ, NULL::TIMESTAMPTZ, "
        "['2025-01-01T00:00:00Z'::TIMESTAMPTZ, NULL], "
        "date_trunc('day', '2025-02-06T05:15:36Z'::TIMESTAMPTZ), "
        "'+10000-01-01'::TIMESTAMP, {seen = '2025-01-01T00:00:00Z'::TIMESTAMPTZ}"
    )
    assert result.rows == [
        [
            "2025-02-06T05:15:36.123Z",
            "2025-02-06T05:15:36",
            "1969-07-20T20:17:40Z",
            None,
            ["2025-01-01T00:00:00Z", None],
            "2025-02-06T00:00:00Z",
            "+10000-01-01T00:00:00",
            {"seen": 1735689600000},
        ]
    ]


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("'9999-12-31T23:59:59.999Z'::TIMESTAMPTZ", "9999-12-31T23:59:59.999Z"),
        ("'+10000-01-01T00:00:00Z'::TIMESTAMPTZ", "+10000-01-01T00:00:00Z"),
        ("'0001-01-01T00:00:00Z'::TIMESTAMPTZ", "0001-01-01T00:00:00Z"),
        ("'0000-12-31T23:59:59.999Z'::TIMESTAMPTZ", "+00000-12-31T23:59:59.999Z"),
        ("'-0001-12-31'::DATE", "-00001-12-31"),
        ("CAST(9223372036854775807 AS TIMESTAMP)", "+292278994-08-17T07:12:55.807"),
        ("CAST(-9223372036854775808 AS TIMESTAMP)", "-292275055-05-16T16:47:04.192"),
    ],
    ids=["last-of-9999", "first-of-10000", "first-of-1", "last-before-1", "date", "max", "min"],
)
def test_years_outside_1_to_9999_come_back_signed_with_five_digits(value, text):
    assert query_sql(f"SELECT {value}").rows == [[text]]


def test_dates_come_back_as_iso_8601_text():
    result = query_sql(
        "SELECT '2025-07-01'::DATE, '2025-07-01T12:30:00Z'::TIMESTAMPTZ::DATE, "
        "['2025-07-01'::DATE, NULL], NULL::DATE"
    )
    assert result.rows == [["2025-07-01", "2025-07-01", ["2025-07-01", None], None]]


def test_a_date_with_a_time_of_day_comes_back_in_the_form_of_a_timestamp():
    answer = {"cols": ["d"], "col_types": [24], "rows": [[1751373000000]]}
    assert tool.typed_answer(answer) == {"cols": ["d"], "rows": [["2025-07-01T12:30:00Z"]]}


def test_numeric_values_come_back_as_their_digits_and_other_numbers_as_numbers():
    result = query_sql(
        "SELECT 12345678901234567890.123::NUMERIC, 483.60::NUMERIC(12, 2), 0.0000001::NUMERIC, "
        "1000::NUMERIC, NULL::NUMERIC, [1.5::NUMERIC, 2], [0.10::NUMERIC(4, 2)], "
        "{amount = 1.5::NUMERIC}, "
        "0.1::DOUBLE, 1.5::REAL, 9223372036854775807::BIGINT, 'POINT (9.7 47.4)'::GEO_POINT"
    )
    assert result.rows == [
        [
            "12345678901234567890.123",
            "483.60",
            "1.0E-7",
            "1000",
            None,
            ["1.5", "2"],
            ["0.10"],
            {"amount": 1.5},
            0.1,
            1.5,
            9223372036854775807,
            [9.7, 47.4],
        ]
    ]


def test_answer_without_a_numeric_column_holds_plain_floats(answer_with):
    answer = {"cols": ["d", "a"], "col_types": [6, [100, 6]], "rows": [[0.1, [2.5]]]}
    answer_with(lambda request: httpx.Response(200, json=answer))
    ((double, (element,)),) = tool.query_cratedb("SELECT d, a FROM doc.t")["rows"]
    assert [type(double), type(element)] == [float, float]


def test_character_cap_counts_times_as_text(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "60"})
    result = query_sql(
        "SELECT ts FROM generate_series('2025-01-01T00:00:00Z'::TIMESTAMPTZ, "
        "'2025-01-01T00:09:00Z'::TIMESTAMPTZ, '1 minute'::INTERVAL) AS t(ts)"
    )
    assert result.rows == [["2025-01-01T00:00:00Z"], ["2025-01-01T00:01:00Z"]]
    assert result.truncated is True
