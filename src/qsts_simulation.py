"""Run the Week 3 OpenDSS QSTS dispatch replay."""

from pathlib import Path

import pandas as pd

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

    dispatch_data = pd.read_csv(
        dispatch_path,
        parse_dates=["timestamp"],
    )

    replay_results = replay_dispatch_timeseries(
        dispatch_data
    )

    replay_results.to_csv(
        output_path,
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

if __name__ == "__main__":
    main()