"""Build and inspect the Week 3 OpenDSS circuit."""

import opendssdirect as dss
import math
from dataclasses import dataclass

# CktElement.Powers() returnns alternating real and reactive
# power for each phase and terminal
# ex> Terminal 1: [P_A, Q_A, P_B, Q_B, P_C, Q_C]
# Terminal 2: [P_A, Q_A, P_B, Q_B, P_C, Q_C]

# math.hypot(P,Q) calculates magnitude directly
# = sqrt(P^2 + Q^2)


#frozen = True makes the class immutable
@dataclass(frozen=True)
class FeederMetrics:
    """Electrical measurements for the active feeder line"""
    phase_currents_a: tuple[float, ...]
    input_real_power_kw: float
    input_reactive_power_kvar: float
    apparent_power_kva: float
    power_factor: float
    real_loss_kw: float
    reactive_absorption_kvar: float


def create_base_circuit() -> tuple[str, list[float]]:
    """Create an empty three-phase microgrid circuit."""

    dss.Text.Command("Clear")

    dss.Text.Command(
        "New Circuit.Microgrid "
        "basekv=12.47 "
        "pu=1.0 "
        "phases=3 "
        "bus1=source_bus"
    )

    dss.Text.Command(
        "New Line.Feeder "
        "bus1=source_bus.1.2.3 "
        "bus2=load_bus.1.2.3 "
        "phases=3 "
        "length=1 "
        "units=km "
        "r1=0.2 "
        "x1=0.4 "
        "r0=0.4 "
        "x0=0.8"
    )

    dss.Text.Command(
        "New Load.Building "
        "bus1=load_bus.1.2.3 "
        "phases=3 "
        "conn=wye "
        "model=1 "
        "kv=12.47 "
        "kw=500 "
        "pf=0.95"
    )
    dss.Text.Command("Set VoltageBases=[12.47]")
    dss.Text.Command("CalcVoltageBases")

    dss.Solution.Solve()
    if not dss.Solution.Converged():
        raise RuntimeError(
            "OpenDSS power flow did not converge."
        )

    dss.Circuit.SetActiveBus("load_bus")

    voltage_magnitudes_and_angles =(
        dss.Bus.puVmagAngle()
    )
    #[magnitude, angle, magnitude, angle, magnitude, angle]
    phase_voltages_pu = (
        voltage_magnitudes_and_angles[0::2]
    )
    ## pu(power unit) tells how healthy a voltage is relative to
    ## what that equipment expects

    return dss.Circuit.Name(), phase_voltages_pu

def calculate_feeder_metrics(
        line_name: str = "Line.Feeder",
) -> FeederMetrics:
    """Calculate electrical metrics for an OpenDSS line."""

    element_found = (
        dss.Circuit.SetActiveElement(line_name)
    )

    if not element_found:
        raise ValueError(
            f"OpenDSS line waas not found {line_name}"
        )

    number_of_conductors = (
        dss.CktElement.NumConductors()
    )

    if number_of_conductors is None:
        raise RuntimeError("Active OpenDSS element has no conductor count.")

    terminal_value_count = (
        number_of_conductors * 2
    )

    current_values = (
        dss.CktElement.CurrentsMagAng()
    )

    phase_currents_a = tuple(
        current_values[
            0:terminal_value_count:2
        ]
    )

    power_values = dss.CktElement.Powers()

    input_real_power_kw = sum(
        power_values[0:terminal_value_count:2]
    )

    input_reactive_power_kvar = sum(
        power_values[1:terminal_value_count:2]
    )

    apparent_power_kva = math.hypot(
        input_real_power_kw,
        input_reactive_power_kvar,
    )

    power_factor = (
        input_real_power_kw
        / apparent_power_kva
        if apparent_power_kva > 0
        else 0.0
    )

    loss_values = dss.CktElement.Losses()

    return FeederMetrics(
        phase_currents_a = phase_currents_a,
        input_real_power_kw=input_real_power_kw,
        input_reactive_power_kvar=(
            input_reactive_power_kvar
        ),
        apparent_power_kva=apparent_power_kva,
        power_factor=power_factor,
        real_loss_kw=loss_values[0]/1000,
        reactive_absorption_kvar=(
            loss_values[1] / 1000
        ),
    )

# Main() ----------------------------------------------------------
def main ()-> None:
    """Run and report the base OpenDSS feeder analysis."""

    circuit_name, load_phase_voltages_pu = (
        create_base_circuit()
    )

    # Select the feeder and collect its reusable
    # current, power, power-factor, and loss metrics
    feeder_metrics = calculate_feeder_metrics()

    #Bus methods read the currently active bus.
    dss.Circuit.SetActiveBus("source_bus")

    #puVmagAngle() alternates magnitude and angle.
    # [0::2] selects only phase-voltage magnitudes.
    source_phase_voltages_pu = (
        dss.Bus.puVmagAngle()[0::2]
    )

    # Pair corresponding source and load phases
    # multiplying the per-unit difference by 100
    # converts it to percent of base voltage.
    voltage_drop_percent = [
        (source_voltage - load_voltage) * 100
        for source_voltage, load_voltage in
        zip(
            source_phase_voltages_pu,
            load_phase_voltages_pu,
        )
    ]

    feeder_real_loss_percent = (
        feeder_metrics.real_loss_kw
        / feeder_metrics.input_real_power_kw
        * 100
        if feeder_metrics.input_real_power_kw != 0
        else 0.0
    )

    # Independently verity the OpenDSS real loss using the per-phase I^R relationship
    line_resistance_ohm = 0.2

    phase_resistive_losses_w = [
        (current_a ** 2) * line_resistance_ohm
        for current_a
        in feeder_metrics.phase_currents_a
    ]

    calculated_real_loss_kw = (
        sum(phase_resistive_losses_w) / 1000
    )

    loss_difference_w = abs(
        feeder_metrics.real_loss_kw
        - calculated_real_loss_kw
    ) * 1000

    print(f"\nActive circuit: {circuit_name}")
    print(f"Buses: {dss.Circuit.AllBusNames()}")
    print(f"Loads: {dss.Loads.AllNames()}")
    print(
        "Load-bus phase voltages (pu): "
        f"{[
            round(value, 4)
            for value in load_phase_voltages_pu
        ]}"
    )

    print(
        "Solution converged: " 
        f"{dss.Solution.Converged()}"
    )

    print(
        "Feeder voltage drop by phase (%): " 
        f"{[
            round(value, 4)
            for value in voltage_drop_percent
        ]}"
    )

    print(
        "\nFeeder source-terminal currents (A): "
        f"{[
            round(value,4)
            for value in feeder_metrics.phase_currents_a
        ]}"
    )

    print(
        "Feeder input real power (kW): "
        f"{feeder_metrics.input_real_power_kw:.4f}"
    )

    print(
        "Feeder input reactive power (kvar): "
        f"{feeder_metrics.input_reactive_power_kvar:.4f}"
    )

    print(
        "\nFeeder real-power loss (kW): "
        f"{feeder_metrics.real_loss_kw:.4f}"
    )

    print(
        "Feeder reactive-power absorption (kvar): "
        f"{feeder_metrics.reactive_absorption_kvar:.4f}"
    )

    print(
        "Feeder real-power loss (%): "
        f"{feeder_real_loss_percent:.4f}"
    )

    print(
        "\nCalculated I^2R loss (kW): "
        f"{calculated_real_loss_kw:.4f}"
    )

    print(
        "OpenDSS versus I^2R difference (W): "
        f"{loss_difference_w:.4f}"
    )

    print(
        "\nSource apparent power (kVA): "
        f"{feeder_metrics.apparent_power_kva:.4f}"
    )

    print(
        "Source power factor: "
        f"{feeder_metrics.power_factor:.4f}"
    )

if __name__ == "__main__":
    main()