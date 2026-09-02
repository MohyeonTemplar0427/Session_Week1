"""Build and inspect the Week 3 OpenDSS circuit."""

import opendssdirect as dss
import math
from dataclasses import dataclass

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

if __name__ == "__main__":

    circuit_name, phase_voltages_pu = create_base_circuit()

    dss.Circuit.SetActiveElement("Line.Feeder")

    # CktElement.Powers() returnns alternating real and reactive
    # power for each phase and terminal
    # ex> Terminal 1: [P_A, Q_A, P_B, Q_B, P_C, Q_C]
    # Terminal 2: [P_A, Q_A, P_B, Q_B, P_C, Q_C]
    feeder_powers_kw_kvar = (
        dss.CktElement.Powers()
    )

    source_terminal_real_power_kw = sum(
        feeder_powers_kw_kvar[0:6:2]
    )

    source_terminal_reactive_power_kvar = sum(
        feeder_powers_kw_kvar[1:6:2]
    )
    # math.hypot(P,Q) calculates magnitude directly
    # = sqrt(P^2 + Q^2)
    source_apparent_power_kva = math.hypot(
        source_terminal_real_power_kw,
        source_terminal_reactive_power_kvar
    )

    source_power_factor = (
        source_terminal_real_power_kw
        / source_apparent_power_kva
    )

    feeder_currents_magnitude_and_angle = (
        dss.CktElement.CurrentsMagAng()
    )

    # Cktelement.Losses returns two values,
    # [real loss in watts, reactive loss in vars]
    # Be careful that we must divide by 1000 before comparing
    # with kW

    feeder_losses_w_var = (
        dss.CktElement.Losses()
    )

    feeder_real_loss_kw = (
        feeder_losses_w_var[0] / 1000
    )

    feeder_reactive_loss_kvar = (
        feeder_losses_w_var[1] / 1000
    )

    feeder_real_loss_percent = (
        feeder_real_loss_kw
        / source_terminal_real_power_kw
        * 100
    )

    #extract phase A, B, and C current magnitudes from termianl 1
    source_terminal_currents_a = (
        feeder_currents_magnitude_and_angle[0:6:2]
    )

    line_resistance_ohm = 0.2

    phase_resistive_losses_w = [
        (current_a ** 2) * line_resistance_ohm
        for current_a in source_terminal_currents_a
    ]

    calculated_real_loss_kw = (
        sum(phase_resistive_losses_w) / 1000
    )

    loss_difference_w = abs(
        feeder_real_loss_kw
        - calculated_real_loss_kw
    ) * 1000

    print("\nFeeder source-terminal currents (A): "
          f"{[
              round(value, 4)
              for value in source_terminal_currents_a
          ]}"
          )

    dss.Circuit.SetActiveBus("source_bus")
    
    source_phase_voltages_pu = (
        dss.Bus.puVmagAngle()[0::2]
    )
    
    voltage_drop_percent = [
        (source_voltage - load_voltage) * 100
            for source_voltage, load_voltage in zip(
                source_phase_voltages_pu,
                phase_voltages_pu,
            )
        ]



    #Print Calls---------------------------------------------------
    print(f"\nActive circuit: {circuit_name}")

    print(f"Buses: {dss.Circuit.AllBusNames()}")

    print(f"Loads: {dss.Loads.AllNames()}")

    print(
        "Load-bus phase voltages (pu): "
        f"{[round(value, 4) for value in phase_voltages_pu]}"
    )

    print(
        "\nSolution converged: "
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
        "\nFeeder input real power (kW): "
        f"{source_terminal_real_power_kw:.4f}"
    )

    print(
        "Feeder input reactive power (kvar): "
        f"{source_terminal_reactive_power_kvar:.4f}"
    )

    print(
        "\nFeeder real-power loss (kW): "
        f"{feeder_real_loss_kw:.4f}"
    )

    print(
        "Feeder reactive-power absorption (kvar): "
        f"{feeder_reactive_loss_kvar:.4f}"
    )

    print(
        "Feeder real-power loss (%): "
        f"{feeder_real_loss_percent:.4f}"
    )

    print(
        "\nCalculated (I^2)R loss (kW): "
        f"{calculated_real_loss_kw:.4f}"
    )

    print(
        "OpenDSS versus (I^2)R difference (W): "
        f"{loss_difference_w:.4f}"
    )

    print(
        "\n Source apparent power (kVA): "
        f" {source_apparent_power_kva:.4f}"
    )

    print(
        "Source power factor: "
        f"{source_power_factor:.4f}"
    )