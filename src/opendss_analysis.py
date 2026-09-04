"""Build and inspect the Week 3 OpenDSS circuit."""

import opendssdirect as dss
import math
from dataclasses import dataclass
from enum import Enum 
from collections.abc import Sequence
import pandas as pd

try:
    from .opendss_models import (
        FeederMetrics,
        LineLoadingAssessment,
        LoadingStatus,
        VoltageAssessment,
    )
except ImportError:
    from opendss_models import (
        FeederMetrics,
        LineLoadingAssessment,
        LoadingStatus,
        VoltageAssessment,
    )

# CktElement.Powers() returnns alternating real and reactive
# power for each phase and terminal
# ex> Terminal 1: [P_A, Q_A, P_B, Q_B, P_C, Q_C]
# Terminal 2: [P_A, Q_A, P_B, Q_B, P_C, Q_C]

# math.hypot(P,Q) calculates magnitude directly
# = sqrt(P^2 + Q^2)
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
    #noramp: normal amp(A), emeramp: emergency amp(A) rating
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
        "x0=0.8 "
        "normamps=100 "
        "emergamps=125"
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

def add_replay_resources()-> None:
    """Add the PV system and battery used for dispatch replay"""

    dss.Text.Command(
        "New PVSystem.RooftopPV "
        "bus1=load_bus.1.2.3 "
        "phases=3 "
        "conn=wye "
        "kv=12.47 "
        "kVA=30 "
        "Pmpp=30 "
        "irradiance=0 "
        "pf=1.0 "
        "%CutIn=0 "
        "%CutOut=0"
    )

    dss.Text.Command(
        "New Storage.Battery "
        "bus1=load_bus.1.2.3 "
        "phases=3 "
        "conn=wye "
        "kv=12.47 "
        "kVA=5 "
        "kWrated=5 "
        "kWhrated=20 "
        "%stored=50 "
        "%reserve=10 "
        "%EffCharge=95 "
        "%IdlingkW=0 "
        "DispMode=EXTERNAL "
        "state=IDLING"
    )

    dss.Solution.Solve()

def replay_dispatch_timeseries(
        dispatch_data: pd.DataFrame,
)-> pd.DataFrame:
    """Replay an optimizer dispatch schedule through OpenDSS"""

    required_columns = {
        "timestamp",
        "load_kw",
        "pv_kw",
        "battery_net_injection_kw",
        "grid_net_import_kw",
        "battery_soc_kWh",
    }

    missing_columns = (
        required_columns - set(dispatch_data.columns)
    )

    if missing_columns:
        raise ValueError(
            "Dispatch replay is missing required column: "
            f"{sorted(missing_columns)}"
        )

    if dispatch_data.empty:
        raise ValueError(
            "Dispatch replay data must not be empty."
        )

    create_base_circuit()
    add_replay_resources()

    replay_records = []

    for _, dispatch_row in dispatch_data.iterrows():
        apply_dispatch_operating_point(
            dispatch_row
        )

        feeder_metrics = calculate_feeder_metrics()

        dss.Circuit.SetActiveBus("load_bus")
        voltage_values = dss.Bus.puVmagAngle()

        if voltage_values is None:
            raise RuntimeError(
                "OpenDSS did not return load-bus voltages."
            )

        phase_voltages_pu = voltage_values[0::2]

        receiving_end_real_power_kw = (
            feeder_metrics.input_real_power_kw
            - feeder_metrics.real_loss_kw
        )

        scheduled_grid_import_kw = float(
            dispatch_row["grid_net_import_kw"]
        )

        replay_records.append(
            {
                "timestamp": dispatch_row["timestamp"],
                "converged": bool(
                    dss.Solution.Converged()
                ),
                "minimum_voltage_pu": min(
                    phase_voltages_pu
                ),
                "maximum_voltage_pu": max(
                    phase_voltages_pu
                ),
                "maximum_current_a": max(
                    feeder_metrics.phase_currents_a
                ),
                "source_real_power_kw": (
                    feeder_metrics.input_real_power_kw
                ),
                "feeder_real_loss_kw": (
                    feeder_metrics.real_loss_kw
                ),
                "scheduled_grid_import_kw": (
                    scheduled_grid_import_kw
                ),
                "receiving_end_real_power_kw": (
                    receiving_end_real_power_kw
                ),
                "grid_import_error_kw": (
                    receiving_end_real_power_kw
                    - scheduled_grid_import_kw
                ),
            }
        )


    return pd.DataFrame(replay_records)

def apply_dispatch_operating_point(
        dispatch_row: pd.Series,
        *,
        pv_rated_kw: float = 30.0,
        battery_capacity_kWh: float = 20.0,
        zero_tolerance_kw: float = 1e-6,
)-> None:
    """Apply one optimizer dispatch row to the OpenDSS circuit"""

    required_columns = {
        "load_kw",
        "pv_kw",
        "battery_net_injection_kw",
        "battery_soc_kWh",
    }

    missing_columns = (
        required_columns - set(dispatch_row.index)
    )

    if missing_columns:
        raise ValueError(
            "Dispatch row is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    load_kw = float(dispatch_row["load_kw"])
    pv_kw = float(dispatch_row["pv_kw"])
    battery_net_injection_kw = float(
        dispatch_row["battery_net_injection_kw"]
    )
    battery_soc_kWh = float(
        dispatch_row["battery_soc_kWh"]
    )

    if not 0.0 <= pv_kw <= pv_rated_kw:
        raise ValueError(
            "PV power must be set between zero and its rating."
        )

    if not 0.0 <= battery_soc_kWh <= battery_capacity_kWh:
        raise ValueError(
            "Battery Energy must be between zero and capacity."
        )
    
    # irradiance is effectively a normalized solar availability
    # value because OpenDSS defines 1.0 as the reference irradiance of 1kW/m^2
    # Temperature derating or inverter efficiency curve will be 
    # introduced for later use
    pv_irradiance = pv_kw / pv_rated_kw

    battery_soc_percent = (
        battery_soc_kWh
        / battery_capacity_kWh
        * 100
    )

    if battery_net_injection_kw > zero_tolerance_kw:
        battery_state = "DISCHARGING"
    elif battery_net_injection_kw < -zero_tolerance_kw:
        battery_state = "CHARGING"
    else:
        battery_state = "IDLING"
        battery_net_injection_kw = 0.0

    dss.Text.Command(
        "Edit Load.Building "
        f"kW={load_kw}"
    )

    dss.Text.Command(
        "Edit PVSystem.RooftopPV "
        f"irradiance={pv_irradiance}"
    )

    dss.Text.Command(
        "Edit Storage.Battery "
        "DispMode=EXTERNAL "
        f"%stored={battery_soc_percent} "
        f"state={battery_state} " 
        f"kW={battery_net_injection_kw}"
    )

    dss.Solution.Solve()

    return None

    
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

def classify_line_loading(
        current_a: float,
        normal_amps: float,
        emergency_amps: float,
) -> LoadingStatus:
    """Classify current against line amp ratings."""

    if normal_amps <= 0:
        raise ValueError(
            "Normal amp rating must be positive."
        )

    if emergency_amps < normal_amps:
        raise ValueError(
            "Emergency rating must be at least the normal rating."
        )

    if current_a <= normal_amps:
        return LoadingStatus.NORMAL

    if current_a <= emergency_amps:
        return LoadingStatus.EMERGENCY

    return LoadingStatus.ABOVE_EMERGENCY

def assess_line_loading(
    phase_currents_a: Sequence[float],
    *,
    normal_amps: float,
    emergency_amps: float,
) -> LineLoadingAssessment:
    """Assess phase currents agsint line ratings."""
    if not phase_currents_a:
        raise ValueError(
            "At least one phase current is required."
        )
    
    maximum_current_a = max(phase_currents_a)

    status = classify_line_loading(
        current_a=maximum_current_a,
        normal_amps=normal_amps,
        emergency_amps=emergency_amps,
    )

    return LineLoadingAssessment(
        maximum_current_a=maximum_current_a,
        normal_rating_a = normal_amps,
        emergency_rating_a=emergency_amps,
        normal_loading_percent=(
            maximum_current_a / normal_amps * 100
        ),
        emergency_loading_percent=(
            maximum_current_a / emergency_amps * 100
        ),
        status=status,
    )

def assess_voltage_limits(
    phase_voltages_pu: Sequence[float],
    *,
    minimum_limit_pu: float = 0.95,
    maximum_limit_pu: float = 1.05,
) -> VoltageAssessment:
    """Assess phase-voltage magnitudes against limits."""

    if not phase_voltages_pu:
        raise ValueError(
            "At least one phase voltage is required"
        )

    if minimum_limit_pu >= maximum_limit_pu:
        raise ValueError(
            "Minimum voltage limit must be below the maximum voltage limit."
        )

    minimum_voltage_pu = min(phase_voltages_pu)
    maximum_voltage_pu = max(phase_voltages_pu)
    within_limits = (
        minimum_voltage_pu >= minimum_limit_pu
        and maximum_voltage_pu <= maximum_limit_pu
    )

    return VoltageAssessment(
        minimum_voltage_pu=minimum_voltage_pu,
        maximum_voltage_pu=maximum_voltage_pu,
        within_limits=within_limits,
    )




# Main() ----------------------------------------------------------
def main ()-> None:
    """Run and report the base OpenDSS feeder analysis."""

    circuit_name, load_phase_voltages_pu = (
        create_base_circuit()
    )
    # add battery and PV
    add_replay_resources()

    # Select the feeder and collect its reusable
    # current, power, power-factor, and loss metrics
    feeder_metrics = calculate_feeder_metrics()

    dss.Circuit.SetActiveElement("Line.Feeder")

    feeder_normal_amps = (
        dss.CktElement.NormalAmps()
    )

    feeder_emergency_amps = (
        dss.CktElement.EmergAmps()
    )

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

    voltage_assessment = assess_voltage_limits(
        load_phase_voltages_pu
    )

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

    if (
        feeder_normal_amps is None
        or feeder_emergency_amps is None
    ):
        raise ValueError(
            "Feeder amp ratings are missing"
        )

    loading_assessment = assess_line_loading(
        feeder_metrics.phase_currents_a,
        normal_amps=feeder_normal_amps,
        emergency_amps=feeder_emergency_amps,
    )


    # Print Call_______________________________________________________

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

    print(
        "Feeder normal rating (A): "
        f"{loading_assessment.normal_rating_a}"
    )

    print(
        "Feeder emergency rating (A): "
        f"{loading_assessment.emergency_rating_a}"
    )

    print(
        "\nMaximum feeder phase current (A): "
        f"{loading_assessment.maximum_current_a:.4f}"
    )

    print(
        "Feeder normal loading (%): "
        f"{loading_assessment.normal_loading_percent:.4f}"
    )

    print(
        "Feeder emergency loading (%): "
        f"{loading_assessment.emergency_loading_percent:.4f}"
    )

    print(
        "Feeder loading status: "
        f"{loading_assessment.status.value}"
    )

    print(
        "\nMinimum load-bus voltage (pu): "
        f"{voltage_assessment.minimum_voltage_pu:.4f}"
    )

    print(
        "Maximum load-bus voltage (pu): "
        f"{voltage_assessment.maximum_voltage_pu:.4f}"
    )

    print(
        "Load-bus voltage within limits: "
        f"{voltage_assessment.within_limits}"
    )

    print(f"\nPV systems: {dss.PVsystems.AllNames()}")
    print(f"Storage units: {dss.Storages.AllNames()}")


if __name__ == "__main__":
    main()