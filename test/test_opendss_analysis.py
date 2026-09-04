import opendssdirect as dss
import pytest
import pandas as pd
from pathlib import Path

from src.opendss_analysis import (
    LoadingStatus,
    assess_line_loading,
    assess_voltage_limits,
    calculate_feeder_metrics,
    calculate_transformer_metrics,
    classify_line_loading,
    create_base_circuit,
    add_replay_resources,
    apply_dispatch_operating_point,
    replay_dispatch_timeseries,

)

def test_create_base_circuit_solves_balanced_feeder():
    circuit_name, phase_voltages_pu = (
        create_base_circuit()
    )

    assert circuit_name == "microgrid"
    assert dss.Solution.Converged()

    bus_names = dss.Circuit.AllBusNames()
    assert bus_names is not None
    assert set(bus_names) == {
        "pcc_bus",
        "service_bus",
        "load_bus",
    }

    assert dss.Loads.AllNames() == [
        "building",
    ]

    assert phase_voltages_pu == pytest.approx(
        [0.9716, 0.9716, 0.9716],
        abs=0.0001,
    )

def test_calculate_feeder_metrics_matches_balanced_feeder():
    # Arrange
    create_base_circuit()

    # Act
    metrics = calculate_feeder_metrics()

    # Assert
    assert metrics.phase_currents_a == pytest.approx(
        (651.4321, 651.4321, 651.4321),
        abs=0.0001,
    )

    assert metrics.input_real_power_kw == pytest.approx(
        502.4568,
        abs=0.0001,
    )

    assert metrics.real_loss_kw == pytest.approx(
        2.5462,
        abs=0.0001,
    )

    assert metrics.power_factor == pytest.approx(
        0.9476,
        abs=0.0001,
    )

def test_calculate_transformer_metrics_matches_base_case():
    create_base_circuit()

    metrics = calculate_transformer_metrics()

    assert metrics.input_real_power_kw == pytest.approx(
        506.3677,
        abs=0.0001,
    )

    assert metrics.input_reactive_power_kvar == pytest.approx(
        191.8896,
        abs=0.0001,
    )

    assert metrics.apparent_power_kva == pytest.approx(
        541.5070,
        abs=0.0001,
    )

    assert metrics.rated_power_kva == pytest.approx(
        750.0
    )

    assert metrics.loading_percent == pytest.approx(
        72.2009,
        abs=0.0001,
    )

    assert metrics.real_loss_kw == pytest.approx(
        3.9109,
        abs=0.0001,
    )

    assert metrics.reactive_absorption_kvar == pytest.approx(
        22.4885,
        abs=0.0001,
    )


#test with current_a values(24.3946, 110.0, and 130.0 )
@pytest.mark.parametrize(
    ("current_a", "expected_status"),
    [
        (24.3946, LoadingStatus.NORMAL),
        (110.0, LoadingStatus.EMERGENCY),
        (130.0, LoadingStatus.ABOVE_EMERGENCY,),
    ],
)

def test_classify_line_loading_regions(
    current_a,
    expected_status,
):
    result = classify_line_loading(
        current_a=current_a,
        normal_amps=100.0,
        emergency_amps=125.0,
    )

    assert result == expected_status


@pytest.mark.parametrize(
    (
        "phase_voltages_pu",
        "expected_minimum_pu",
        "expected_maximum_pu",
        "expected_within_limits",
    ),
    [
        (
            (0.98, 1.00, 0.99),
            0.98,
            1.00,
            True,
        ),
        (
            (0.94, 0.99, 1.00),
            0.94,
            1.00,
            False,
        ),
        (
            (1.00, 1.06, 1.01),
            1.00,
            1.06,
            False,
        ),
    ],
)

def test_assess_voltage_limits(
    phase_voltages_pu,
    expected_minimum_pu,
    expected_maximum_pu,
    expected_within_limits,
):
    result = assess_voltage_limits(
        phase_voltages_pu
    )

    assert result.minimum_voltage_pu == pytest.approx(
        expected_minimum_pu
    )

    assert result.maximum_voltage_pu == pytest.approx(
        expected_maximum_pu
    )

    assert(
        result.within_limits
        is expected_within_limits
    )

def test_assess_line_loading_rejects_empty_currents():
    with pytest.raises(
        ValueError, match = "At least one phase current is required",):
        assess_line_loading(
            (),
            normal_amps=100.0,
            emergency_amps=125.0,
        )

def test_assess_line_loading_uses_maximum_phase():
    result = assess_line_loading(
        (80.0, 110.0, 90.0),
        normal_amps=100.0,
        emergency_amps=125.0,
    )

    assert result.maximum_current_a == pytest.approx(110.0)

    assert result.normal_loading_percent == pytest.approx(110.0)

    assert result.emergency_loading_percent == pytest.approx(88.0)

    assert result.status == LoadingStatus.EMERGENCY

def test_add_replay_resources_creates_pv_and_battery():
    create_base_circuit()

    add_replay_resources()

    assert dss.PVsystems.AllNames() == [
        "rooftoppv"
    ]
    assert dss.Storages.AllNames() == [
        "battery",
    ]

    dss.Text.Command(
        "? PVSystem.RooftopPV.kV"
    )
    pv_voltage_kv = float(
        dss.Text.Result()
    )

    dss.Text.Command(
        "? Storage.Battery.kV"
    )
    battery_voltage_kv = float(
        dss.Text.Result()
    )

    assert pv_voltage_kv == pytest.approx(
        0.48
    )

    assert battery_voltage_kv == pytest.approx(
        0.48
    )

    assert dss.Solution.Converged()

def test_apply_dispatch_operating_point_uses_real_dispatch_row():
    create_base_circuit()
    add_replay_resources()

    dispatch_row = pd.Series(
        {
            "load_kw": 25.0,
            "pv_kw": 24.944088,
            "battery_net_injection_kw": -4.308915,
            "battery_soc_kWh": 11.023367,
            "grid_net_import_kw": 4.364827
        }
    )

    apply_dispatch_operating_point(
        dispatch_row
    )

    dss.Text.Command("? Load.Building.kW")
    load_kw = float(dss.Text.Result())

    dss.Text.Command("? PVSystem.RooftopPV.irradiance")
    pv_irradiance = float(dss.Text.Result())

    dss.Text.Command("? Storage.Battery.kW")
    battery_kw = float(dss.Text.Result())

    dss.Text.Command("? Storage.Battery.%stored")
    battery_soc_percent = float(dss.Text.Result())

    feeder_metrics = calculate_feeder_metrics()

    receiving_end_real_power_kw = (
        feeder_metrics.input_real_power_kw
        - feeder_metrics.real_loss_kw
    )

    assert dss.Solution.Converged()
    assert load_kw == pytest.approx(25.0)
    assert pv_irradiance == pytest.approx(
        24.944088 / 30.0
    )
    assert battery_kw == pytest.approx(
        -4.308915
    )
    assert battery_soc_percent == pytest.approx(
        11.023367 / 20.0 * 100
    )

    assert receiving_end_real_power_kw == pytest.approx(
        dispatch_row["grid_net_import_kw"],
        abs = 0.001,
    )

def test_replay_dispatch_timeseries_meets_network_limits():
    project_root = Path(__file__).resolve().parents[1]

    dispatch_data = pd.read_csv(
        project_root
        / "results"
        /
        "week2_opendss_handoff_combined_real_15min.csv",
        parse_dates=["timestamp"],
    )

    replay = replay_dispatch_timeseries(
        dispatch_data
    )

    assert len(replay) == 192
    assert replay["converged"].all()
    assert(
        replay["grid_import_error_kw"].abs().max() < 0.002
    )

    assert(
        replay["minimum_voltage_pu"].min() >= 0.95
    )
    assert(
        replay["maximum_voltage_pu"].max() <= 1.05
    )
    assert(
        replay["maximum_current_a"].max() <= 800.0
    )

    
