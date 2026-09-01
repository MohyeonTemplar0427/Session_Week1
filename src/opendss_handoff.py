""" Create explicit dispatch schedules for later OpenDSS replay. """

import pandas as pd
import pytest

REQUIRED_DISPATCH_COLUMNS = {
    "timestamp",
    "load_kw",
    "pv_kw",
    "battery_charge_kw",
    "battery_discharge_kw",
    "grid_import_kw",
    "grid_export_kw",
    "battery_soc_kWh",
}

def create_opendss_handoff(
    dispatch_data: pd.DataFrame,
    *,
    timestep_minutes: int = 15,
    expected_timezone: str = "America/Los_Angeles",
) -> pd.DataFrame:
    """Create an OpenDSS-ready dispatch table with documented signs."""

    missing_columns = (
        REQUIRED_DISPATCH_COLUMNS
        - set(dispatch_data.columns)
    )

    if missing_columns:
        raise ValueError(
            "OpenDSS handoff is missing required columns: "
            f"{sorted(missing_columns)}"
        )
    if dispatch_data.empty:
        raise ValueError(
        "OpenDSS handoff data must not be empty."
    )

    timestamps = dispatch_data["timestamp"]

    if not pd.api.types.is_datetime64_any_dtype(
        timestamps
    ):
        raise ValueError(
        "OpenDSS timestamps must use a "
        "pandas datetime dtype."
    )

    if timestamps.dt.tz is None:
        raise ValueError(
        "OpenDSS timestamps must be timezone-aware."
    )

    if str(timestamps.dt.tz) != expected_timezone:
        raise ValueError(
        f"Expected OpenDSS timezone "
        f"{expected_timezone}, but received "
        f"{timestamps.dt.tz}."
    )

    if not timestamps.is_unique:
        raise ValueError(
        "OpenDSS handoff contains duplicate timestamps."
    )

    if not timestamps.is_monotonic_increasing:
        raise ValueError(
        "OpenDSS handoff timestamps are not increasing."
    )

    expected_timestep = pd.Timedelta(
        minutes=timestep_minutes
    )

    time_differences = (
        timestamps
        .diff()
        .dropna()   
    )

    if not (
        time_differences == expected_timestep
    ).all():
        raise ValueError(
            "OpenDSS handoff timestamps are not continuous "
            f"{timestep_minutes}-minute intervals."
    )
    

    handoff = dispatch_data[
        [
            "timestamp",
            "load_kw",
            "pv_kw",
            "battery_charge_kw",
            "battery_discharge_kw",
            "grid_import_kw",
            "grid_export_kw",
            "battery_soc_kWh",
        ]
    ].copy()



    handoff["battery_net_injection_kw"] = (
        handoff["battery_discharge_kw"]
        - handoff["battery_charge_kw"]
    )

    handoff["grid_net_import_kw"] = (
        handoff["grid_import_kw"]
        - handoff["grid_export_kw"]
    )

    return handoff


