"""Tests for QSTS analysis utilities."""

import pandas as pd
import pytest

from src.qsts_analysis import(
    create_no_battery_replay_schedule,
)

def test_create_no_battery_replay_schedule():
    dispatch_data = pd.DataFrame(
        {
            "load_kw": [10.0, 5.0],
            "pv_kw": [2.0, 8.0],
            "battery_charge_kw": [0.0, 2.0],
            "battery_discharge_kw": [3.0, 0.0],
            "battery_net_injection_kw": [3.0, -2.0],
            "grid_import_kw": [5.0, 0.0],
            "grid_export_kw": [0.0, 1.0],
            "grid_net_import_kw": [5.0, -1.0],
        }
    )

    result = create_no_battery_replay_schedule(
        dispatch_data
    )

    assert result["battery_charge_kw"].tolist() == [
        0.0,
        0.0,
    ]

    assert result["battery_discharge_kw"].tolist() == [
        0.0,
        0.0,
    ]

    assert result["battery_net_injection_kw"].tolist() == [
        0.0,
        0.0,
    ]

    assert result["grid_net_import_kw"].tolist() == (
        pytest.approx([8.0, -3.0])
    )

    assert result["grid_import_kw"].tolist() == (
        pytest.approx([8.0, 0.0])
    )

    assert result["grid_export_kw"].tolist() == (
        pytest.approx([0.0, 3.0])
    )