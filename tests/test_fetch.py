import io
import zipfile

import pytest

from networth.engine.fetch import read_french_csv, returns_to_levels

FRENCH_TEXT = """This file was created using the 202608 CRSP database.

  Average Value Weighted Returns -- Daily
,Agric,Trans
19260701,   1.00,  -99.99
19260702,  -2.00,   0.50

  Average Equal Weighted Returns -- Daily
,Agric,Trans
19260701,   9.00,   9.00
"""


def zipped(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("49_Industry_Portfolios_Daily.csv", text)
    return buf.getvalue()


def test_french_parse_keeps_only_value_weighted_table_as_decimals():
    df = read_french_csv(zipped(FRENCH_TEXT))
    assert list(df.columns) == ["Agric", "Trans"]
    assert len(df) == 2
    assert df["Agric"].tolist() == pytest.approx([0.01, -0.02])


def test_french_missing_marker_becomes_nan_and_levels_skip_it():
    df = read_french_csv(zipped(FRENCH_TEXT))
    levels = returns_to_levels(df["Trans"])
    assert len(levels) == 1
    assert levels.iloc[0] == pytest.approx(1.005)
