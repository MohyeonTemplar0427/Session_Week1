"""Analyze OpenDSs Quasai Static Timeseries simulation results. """
import pandas as pd

def create_no_battery_replay_schedule(
        dispatch_data:pd.DataFrame,
)-> pd.DataFrame:
    """Create a counterfactual schedule with no battery operation"""
    required_column = {
        "load_kw",
        "pv_kw",
        "battery_net_injection_kw",
        "grid_net_import_kw",
    }

    missing_columns = (
        required_column - set(dispatch_data.columns)
    )

    if missing_columns:
        raise ValueError(
            "No-battery replay is missing required columns: " 
            f"{sorted(missing_columns)}"
        )

    no_battery_data = dispatch_data.copy()

    no_battery_data[
        "battery_net_injection_kw"
    ] = 0.0

    if "battery_charge_kw" in no_battery_data.columns:
        no_battery_data["battery_charge_kw"] = 0.0

    if "battery_discharge_kw" in no_battery_data.columns:
        no_battery_data["battery_discharge_kw"] = 0.0

    net_site_load_kw = (
        no_battery_data["load_kw"] - no_battery_data["pv_kw"]
    )

    no_battery_data["grid_net_import_kw"] = (
        net_site_load_kw
    )

    if "grid_import_kw" in no_battery_data.columns:
        no_battery_data["grid_import_kw"] = (
            net_site_load_kw.clip(lower=0.0)
        )

    if "grid_export_kw" in no_battery_data.columns:
        no_battery_data["grid_export_kw"] = (
            (-net_site_load_kw).clip(lower=0.0)
        )    
    return no_battery_data