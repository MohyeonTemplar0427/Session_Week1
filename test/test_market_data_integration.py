import pandas as pd
import pytest

from results import ExperimentResult
from market_data_integration import (
    calculate_normalized_kpis,
    calculate_sensitivity_metrics,
    calculate_daily_metrics,
    merge_complete_time_series,
)

def test_calculate_normalized_kpis():

    result = ExperimentResult(
        no_battery_cost=100.0,
        no_battery_emissions=200.0,

        synthetic_real_cost=0.0,
        synthetic_real_emissions=0.0,

        real_market_cost=90.0,
        real_market_emissions=180.0,

        cost_savings=10.0,
        emissions_reduction=20.0,

        real_market_degradation_cost=4.0,
        real_market_total_operating_cost=94.0,
        operating_cost_savings=6.0,

        synthetic_usage={},
        real_market_usage={
            "equivalent_full_cycles": 2.0,
        },

        weighted_charge_price=0.0,
        weighted_discharge_price=0.0,
        weighted_charge_carbon=0.0,
        weighted_discharge_carbon=0.0,

        daily_summary=pd.DataFrame(),
    )

    kpis = calculate_normalized_kpis(
        result=result,
        number_of_days=4,
    )

    assert kpis[
        "cost_savings_percentage"
    ] == pytest.approx(6.0)

    assert kpis[
        "emissions_reduction_percentage"
    ] == pytest.approx(10.0)

    assert kpis[
        "average_daily_cost_savings"
    ] == pytest.approx(1.5)

    assert kpis[
        "average_daily_emissions_reduction"
    ] == pytest.approx(5.0)

    assert kpis[
        "equivalent_full_cycles_per_day"
    ] == pytest.approx(0.5)


def test_calculate_sensitivity_metrics():

    comparison_table = pd.DataFrame(
        {
            "carbon_weight": [
                0.0,
                0.2,
                0.5,
            ],
            "total_operating_cost": [
                50.0,
                51.0,
                55.0,
            ],
            "emissions_reduction": [
                2.0,
                4.0,
                8.0,
            ],
            "battery_throughput_kWh": [
                10.0,
                20.0,
                40.0,
            ],
            "equivalent_full_cycles": [
                0.5,
                1.0,
                2.0,
            ],
        }
    )

    result = calculate_sensitivity_metrics(
        comparison_table
    )
    assert result.loc[
        1,
        "change_in_operating_cost"
    ] == pytest.approx(1.0)

    assert result.loc[
        1,
        "additional_emissions_reduction"
    ] == pytest.approx(2.0)

    assert result.loc[
        1,
        "additional_throughput_kWh"
    ] == pytest.approx(10.0)

    assert result.loc[
        1,
        "additional_EFC"
    ] == pytest.approx(0.5)

    assert result.loc[
        1,
        "extra_throughput_per_kgCO2"
    ] == pytest.approx(5.0)

    assert result.loc[
        1,
        "marginal_cost_per_kgCO2"
    ] == pytest.approx(0.5)

    assert result.loc[
        2,
        "change_in_operating_cost"
    ] == pytest.approx(4.0)

    assert result.loc[
        2,
        "additional_emissions_reduction"
    ] == pytest.approx(4.0)

    assert result.loc[
        2,
        "additional_throughput_kWh"
    ] == pytest.approx(20.0)

    assert result.loc[
        2,
        "marginal_cost_per_kgCO2"
    ] == pytest.approx(1.0)

    assert pd.isna(
        result.loc[
            0,
            "change_in_operating_cost"
        ]
    )

def test_calculate_daily_metrics():

    timestamps = pd.date_range(
        start="2026-08-25 00:00",
        periods=4,
        freq="15min",
        tz="America/Los_Angeles",
    )

    data = pd.DataFrame(
        {
            "timestamp": timestamps,
            "grid_import_kw": [
                4.0,
                4.0,
                4.0,
                4.0,
            ],
            "price_per_kWh": [
                0.10,
                0.10,
                0.10,
                0.10,
            ],
            "gCO2/kWh": [
                200.0,
                200.0,
                200.0,
                200.0,
            ],
            "battery_charge_kw": [
                2.0,
                2.0,
                0.0,
                0.0,
            ],
            "battery_discharge_kw": [
                0.0,
                0.0,
                1.0,
                1.0,
            ],
        }
    )

    result = calculate_daily_metrics(
        data=data,
        degradation_cost_per_kWh=0.03,
        timestep_hours=0.25,
    )

    assert len(result) == 1

    assert result.loc[
        0,
        "grid_import_kWh"
    ] == pytest.approx(4.0)

    assert result.loc[
        0,
        "grid_cost"
    ] == pytest.approx(0.40)

    assert result.loc[
        0,
        "emissions_kgCO2"
    ] == pytest.approx(0.8)

    assert result.loc[
        0,
        "charge_kWh"
    ] == pytest.approx(1.0)

    assert result.loc[
        0,
        "discharge_kWh"
    ] == pytest.approx(0.5)

    assert result.loc[
        0,
        "throughput_kWh"
    ] == pytest.approx(1.5)

    assert result.loc[
        0,
        "degradation_cost"
    ] == pytest.approx(0.045)



def test_merge_complete_time_series_rejects_duplicate_timestamps():
    timestamp = pd.Timestamp(
        "2026-08-25 00:00",
        tz="America/Los_Angeles",
    )

    left_data = pd.DataFrame(
        {
            "timestamp": [
                timestamp,
                timestamp + pd.Timedelta(minutes=15),
            ],
            "load_kw": [
                4.0,
                5.0,
            ],
        }
    )

    right_data = pd.DataFrame(
        {
            "timestamp": [
                timestamp,
                timestamp,
            ],
            "price_per_kWh": [
                0.10,
                0.20,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="Price merge requires unique timestamps",
    ):
        merge_complete_time_series(
            left_data,
            right_data,
            right_name="Price",
        )




def test_merge_complete_time_series_rejects_missing_interval():
    timestamps = pd.date_range(
        start="2026-08-25 00:00",
        periods=3,
        freq="15min",
        tz="America/Los_Angeles",
    )

    left_data = pd.DataFrame(
        {
            "timestamp": timestamps,
            "load_kw": [
                4.0,
                5.0,
                6.0,
            ],
        }
    )

    right_data = pd.DataFrame(
        {
            "timestamp": timestamps[:2],
            "price_per_kWh": [
                0.10,
                0.20,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="does not cover exactly the same timestamps",
    ):
        merge_complete_time_series(
            left_data,
            right_data,
            right_name="Price",
        )

