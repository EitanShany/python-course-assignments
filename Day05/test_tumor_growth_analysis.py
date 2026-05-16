import math

import pandas as pd

from tumor_growth_analysis import (
    calculate_general_summary,
    calculate_mouse_growth,
    calculate_response_summary,
    classify_response,
    create_long_table,
    find_day_columns,
    normalize_mouse_id,
    standard_error_of_mean,
)


def test_standard_error_of_mean():
    assert math.isclose(standard_error_of_mean([100, 120]), 10.0, rel_tol=0.001)
    assert standard_error_of_mean([100]) == 0.0
    assert math.isnan(standard_error_of_mean([]))


def test_classify_response():
    assert classify_response(50, threshold=50) == "Responder"
    assert classify_response(51, threshold=50) == "Non-responder"
    assert classify_response(float("nan"), threshold=50) == "Unclassified"


def test_normalize_mouse_id():
    assert normalize_mouse_id(28.0) == 28
    assert normalize_mouse_id("28") == 28
    assert normalize_mouse_id("28A") == "28A"


def test_find_day_columns_supports_numbers_and_day_text():
    df = pd.DataFrame(
        {
            "Group": ["A"],
            "mouse": [1],
            0: [100],
            "Day 3": [120],
            "notes": ["ok"],
        }
    )

    assert find_day_columns(df) == {0: 0, 3: "Day 3"}


def test_create_long_table():
    df = pd.DataFrame(
        {
            "Group": ["A"],
            "mouse": [1],
            0: [100],
            3: [120],
            6: [None],
        }
    )
    day_columns = {0: 0, 3: 3, 6: 6}

    long_df = create_long_table(df, day_columns)

    assert len(long_df) == 2
    assert list(long_df["Day"]) == [0, 3]
    assert list(long_df["Tumor Volume"]) == [100.0, 120.0]


def test_calculate_mouse_growth_classifies_response():
    df = pd.DataFrame(
        {
            "Group": ["A", "A"],
            "mouse": [1, 2],
            0: [100, 100],
            3: [120, 160],
            6: [140, 180],
        }
    )
    day_columns = {0: 0, 3: 3, 6: 6}

    mouse_growth, errors = calculate_mouse_growth(df, day_columns, threshold=50)

    assert errors.empty

    mouse_1 = mouse_growth[mouse_growth["Mouse"] == 1].iloc[0]
    assert mouse_1["Percent Growth"] == 40
    assert mouse_1["Response"] == "Responder"

    mouse_2 = mouse_growth[mouse_growth["Mouse"] == 2].iloc[0]
    assert mouse_2["Percent Growth"] == 80
    assert mouse_2["Response"] == "Non-responder"


def test_missing_day_0_creates_error():
    df = pd.DataFrame(
        {
            "Group": ["A"],
            "mouse": [1],
            0: [None],
            3: [120],
        }
    )
    day_columns = {0: 0, 3: 3}

    mouse_growth, errors = calculate_mouse_growth(df, day_columns, threshold=50)

    assert mouse_growth.empty
    assert len(errors) == 1
    assert "Missing Day 0" in errors.iloc[0]["Issue"]


def test_general_summary_mean_and_sem():
    long_df = pd.DataFrame(
        {
            "Group": ["A", "A"],
            "Mouse": [1, 2],
            "Day": [0, 0],
            "Tumor Volume": [100, 120],
        }
    )

    summary = calculate_general_summary(long_df)

    assert len(summary) == 1
    assert summary.iloc[0]["Mean TV"] == 110
    assert math.isclose(summary.iloc[0]["SEM"], 10.0, rel_tol=0.001)
    assert summary.iloc[0]["n"] == 2


def test_response_summary():
    mouse_growth = pd.DataFrame(
        {
            "Group": ["A", "A", "B", "B"],
            "Mouse": [1, 2, 3, 4],
            "Response": ["Responder", "Non-responder", "Responder", "Responder"],
        }
    )

    summary = calculate_response_summary(mouse_growth)

    group_a = summary[summary["Group"] == "A"].iloc[0]
    group_b = summary[summary["Group"] == "B"].iloc[0]

    assert group_a["Responders"] == 1
    assert group_a["Non-responders"] == 1
    assert group_a["Responder %"] == 50

    assert group_b["Responders"] == 2
    assert group_b["Non-responders"] == 0
    assert group_b["Responder %"] == 100
