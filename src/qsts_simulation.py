"""Run the Week 3 OpenDSS Quasai Static Time Series dispatch replay."""
## Package import
from pathlib import Path
import pandas as pd


try:
    from.qsts_analysis import(
        create_no_battery_replay_schedule,
        create_qsts_scenario_comparison,
    )
except ImportError:
    from qsts_analysis import(
        create_no_battery_replay_schedule,
        create_qsts_scenario_comparison,
    )

try:
    from .opendss_analysis import(
        replay_dispatch_timeseries
    )
except ImportError:
    from opendss_analysis import (
        replay_dispatch_timeseries,
    )


def main() -> None:
    """Load, replay, summarize, and save the dispatch schedule."""

    project_root = Path(__file__).resolve().parents[1]

    dispatch_path = (
        project_root
        / "results"
        /
        "week2_opendss_handoff_combined_real_15min.csv"
    )

    output_path = (
        project_root
        / "results"
        /
        "week3_qsts_simulation_results.csv"
    )

    no_battery_output_path = (
        project_root
        / "results"
        / "week3_qsts_no_battery_results.csv"
    )

    comparison_output_path = (
        project_root
        / "results"
        / "week3_qsts_scenario_comparison.csv"
    )

    dispatch_data = pd.read_csv(
        dispatch_path,
        parse_dates=["timestamp"],
    )

    replay_results = replay_dispatch_timeseries(
        dispatch_data
    )

    no_battery_dispatch = (
        create_no_battery_replay_schedule(
            dispatch_data
        )
    )

    no_battery_results = (
        replay_dispatch_timeseries(
            no_battery_dispatch
        )
    )

    scenario_comparison = (
        create_qsts_scenario_comparison(
            {
                "optimized": replay_results,
                "no_battery": no_battery_results,
            },
            timestep_hours=0.25
        )
    )

    timestep_hours = 0.25

    optimized_loss_kWh = (
        replay_results["feeder_real_loss_kw"].sum()
        * timestep_hours
    )

    no_battery_loss_kWh = (
        no_battery_results["feeder_real_loss_kw"].sum()
        * timestep_hours
    )

    loss_reduction_kWh = (
        no_battery_loss_kWh
        - optimized_loss_kWh
    )

    loss_reduction_percentage = (
        loss_reduction_kWh
        / no_battery_loss_kWh
        * 100
        if no_battery_loss_kWh != 0
        else 0.0
    )

    replay_results.to_csv(
        output_path,
        index=False,
    )

    no_battery_results.to_csv(
        no_battery_output_path,
        index=False,
    )

    scenario_comparison.to_csv(
        comparison_output_path,
        index=False,
    )

    print(
        f"Replayed intervals: {len(replay_results)}"
    )
    print(
        "Converged intervals: "
        f"{int(replay_results["converged"].sum())}"
    )
    print(
        "Minimum voltage(pu): "
        f"{replay_results['minimum_voltage_pu'].min():.6f}"
    )
    print(
        "Maximum_voltage (pu): "
        f"{replay_results['maximum_voltage_pu'].max():.6f}"
    )
    print(
        "Maximum feeder current (A): "
        f"{replay_results['maximum_current_a'].max():.6f}"
    )
    print(
        "Maximum grid-import error (kW): "
        f"{replay_results['grid_import_error_kw'].abs().max():.9f}"
    )

    print(f"Saved results: {output_path}")



    print("\n=== QSTS Scenario Comparison ===")

    print(
        "Optimized minimum voltage (pu): "
        f"{replay_results['minimum_voltage_pu'].min():.6f}"
    )
    print(
        "No-battery minimum voltage (pu): "
        f"{no_battery_results['minimum_voltage_pu'].min():.6f}"
    )

    print(
        "Optimized maximum current (A): "
        f"{replay_results['maximum_current_a'].max():.6f}"
    )
    print(
        "No-battery maximum current (A): "
        f"{no_battery_results['maximum_current_a'].max():.6f}"
    )

    print(
        "Optimized feeder-loss energy (kWh): "
        f"{optimized_loss_kWh:.6f}"
    )
    print(
        "No-battery feeder-loss energy (kWh): "
        f"{no_battery_loss_kWh:.6f}"
    )

    print(
        "Feeder-loss energy reduction (kWh): "
        f"{loss_reduction_kWh:.6f}"
    )
    print(
        "Feeder-loss energy reduction (%): "
        f"{loss_reduction_percentage:.3f}"
    )

    print("\n=== QSTS Scenario Summary ===")
    print(
        scenario_comparison.to_string(
            index=False
        )
    )

    print(
        f"Saved no-battery results: "
        f"{no_battery_output_path}"
    )
    print(
        f"Saved scenario comparison: "
        f"{comparison_output_path}"
    )

if __name__ == "__main__":
    main()