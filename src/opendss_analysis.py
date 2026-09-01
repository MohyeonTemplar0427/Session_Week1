"""Build and inspect the Week 3 OpenDSS circuit."""

import opendssdirect as dss

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

    print(f"Active circuit: {circuit_name}")

    print(f"Buses: {dss.Circuit.AllBusNames()}")

    print(f"Loads: {dss.Loads.AllNames()}")

    print(
        "Load-bus phase voltages (pu): "
        f"{[round(value, 4) for value in phase_voltages_pu]}"
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