import opendssdirect as dss
import pytest

from src.opendss_analysis import (
    LoadingStatus,
    create_base_circuit,
    calculate_feeder_metrics,
    classify_line_loading,
    assess_voltage_limits
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
        "source_bus",
        "load_bus",
    }

    assert dss.Loads.AllNames() == [
        "building",
    ]

    assert phase_voltages_pu == pytest.approx(
        [0.9988, 0.9988, 0.9988],
        abs=0.0001,
    )

def test_calculate_feeder_metrics_matches_balanced_feeder():
    # Arrange
    create_base_circuit()

    # Act
    metrics = calculate_feeder_metrics()

    # Assert
    assert metrics.phase_currents_a == pytest.approx(
        (24.3946, 24.3946, 24.3946),
        abs=0.0001,
    )

    assert metrics.input_real_power_kw == pytest.approx(
        500.3571,
        abs=0.0001,
    )

    assert metrics.real_loss_kw == pytest.approx(
        0.3571,
        abs=0.0001,
    )

    assert metrics.power_factor == pytest.approx(
        0.9498,
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