import opendssdirect as dss
import pytest

from src.week3_opendss_analysis import (
    create_base_circuit,
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
