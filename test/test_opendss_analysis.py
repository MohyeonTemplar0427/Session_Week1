import opendssdirect as dss
import pytest

from src.opendss_analysis import (
    create_base_circuit,
    calculate_feeder_metrics,
    create_base_circuit
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
