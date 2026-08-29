import os
import pandas as pd

from dotenv import load_dotenv, find_dotenv

import single_day_analysis as sda
import electricity_maps_data as emd
import gridstatus_data as gsd
import multi_day_analysis as mda



env_path = find_dotenv()

print(
    "Loading .env from:",
    env_path
)


load_dotenv(
    env_path, 
    override=True,
)

api_key = os.getenv(
    "ELECTRICITY_MAPS_API_KEY"
)


#Merge real market data from sda,
def merge_real_market_data(
        synthetic_data: pd.DataFrame,
        price_data: pd.DataFrame,
        carbon_data: pd.DataFrame,
) -> pd.DataFrame:

    base_data = synthetic_data.drop(
        columns = [
            "price_per_kWh",
            "gCO2/kWh",
        ]
    )

    merged_data = pd.merge(
        base_data,
        price_data,
        on="timestamp",
        how="inner",
    )

    merged_data = pd.merge(
        merged_data,
        carbon_data,
        on="timestamp",
        how="inner",
    )

    if len(merged_data) != len(
        synthetic_data
    ):
        raise ValueError("Timestamp mismatch caused rows to be lost during merge.")

    return merged_data

def calculate_cost_with_external_price(
        dispatch_data: pd.DataFrame,
        price_data: pd.DataFrame,
        timestep_hours: float = 0.25,
) -> float:

    merged_data = pd.merge(
        dispatch_data[
            [
                "timestamp",
                "grid_import_kw",
            ]
        ],
        price_data,
        on="timestamp",
        how="inner",
    )
    cost = (
        merged_data["grid_import_kw"]
        * timestep_hours
        * merged_data["price_per_kWh"]
    ).sum()

    return float(cost)



def create_real_dispatch_summary(
        dispatch_data: pd.DataFrame,
        market_data: pd.DataFrame,
) -> pd.DataFrame:

    market_signals = market_data[
        [
            "timestamp",
            "price_per_kWh",
            "gCO2/kWh",
        ]
    ].copy()

    dispatch = dispatch_data[
        [
            "timestamp",
            "battery_charge_kw",
            "battery_discharge_kw",
        ]
    ].copy()

    summary = pd.merge(
        market_signals,
        dispatch,
        on = "timestamp",
        how = "inner",
    )

    if len(summary) != len(dispatch_data):
        raise ValueError(
            "Timestamp mismatch during dispatch-summary merge."
        )

    return summary


## calculate the power-weighted average price and carbon intensity during charging and discharging
## value can be carbon intensity or unit electricity price
def calculate_power_weighted_average(
        data: pd.DataFrame,
        value_column: str,
        power_column: str,
) -> float:

    total_power = (
        data[power_column].sum()
    )

    if total_power <= 0:
        raise ValueError(
            "Total power must be greater than zero."
        )

    weighted_average = (
        (
            data[value_column]
            * data[power_column]
        ).sum()
        / total_power
    )

    return float(weighted_average)


def create_no_battery_dispatch(
        data: pd.DataFrame,
) -> pd.DataFrame:

    no_battery_data = data.copy()

    no_battery_data["grid_import_kw"] = (
        no_battery_data["net_load_kw"]
        .clip(lower=0)
    )

    no_battery_data["battery_charge_kw"] = 0.0
    no_battery_data["battery_discharge_kw"] = 0.0

    return no_battery_data


def validate_integrated_market_data(
    data: pd.DataFrame,
    expected_rows: int,
    timestep_minutes: int = 15,
) -> None:

    required_columns = {
        "timestamp",
        "load_kw",
        "pv_kw",
        "net_load_kw",
        "price_per_kWh",
        "gCO2/kWh",
    }

    missing_columns = (
        required_columns
        - set(data.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    if len(data) != expected_rows:
        raise ValueError(
            f"Expected {expected_rows} rows, "
            f"but received {len(data)}."
        )

    if data.isna().any().any():
        raise ValueError(
            "Integrated market data contains missing values."
        )

    if not data["timestamp"].is_unique:
        raise ValueError(
            "Duplicate timestamps found."
        )

    if not data[
        "timestamp"
    ].is_monotonic_increasing:
        raise ValueError(
            "Timestamps are not increasing."
        )

    time_differences = (
        data["timestamp"]
        .diff()
        .dropna()
    )

    expected_timestep = pd.Timedelta(
        minutes=timestep_minutes
    )

    if not (
        time_differences
        == expected_timestep
    ).all():
        raise ValueError(
            "Integrated data does not have "
            "continuous 15-minute intervals."
        )

    if (
        data["gCO2/kWh"] < 0
    ).any():
        raise ValueError(
            "Carbon intensity cannot be negative."
        )

    print(
        "Integrated market data validation passed."
    )




# Main--------------------------------------------------------------------------------------------
if __name__ == "__main__":

    date = "2026-08-26"

    battery_parameters = {
    "capacity_kWh": 20.0,
    "initial_soc_kWh": 10.0,
    "min_soc_kWh": 2.0,
    "max_soc_kWh": 18.0,
    "max_charge_kw": 5.0,
    "max_discharge_kw": 5.0,
    "charge_efficiency": 0.95,
    "discharge_efficiency": 0.95,
    }

    carbon_weight = 0.20
    degradation_cost_per_kWh = 0.03

    synthetic_data = (
        sda.create_sample_dataframe(
            date = date
        )
    )

    raw_price_data = (
        gsd.get_caiso_real_time_prices(
            date
        )
    )

    price_data = (
        gsd.caiso_price_to_dataframe(
            raw_price_data
        )
    )

    gsd.validate_price_data(
        price_data,
        expected_rows=96,
    )

    carbon_data = (
        emd.get_multi_day_carbon_data(
            str(api_key),
            "US-CAL-CISO",
            date,
            1,
        )
    )

    real_market_data = (
        merge_real_market_data(
            synthetic_data,
            price_data,
            carbon_data,
        )
    )

    synthetic_optimized = (
        sda.run_combined_optimization(
            synthetic_data,
            battery_parameters,
            carbon_weight,
            degradation_cost_per_kWh,
        )
    )

    real_market_optimized = (
        sda.run_combined_optimization(
            real_market_data,
            battery_parameters,
            carbon_weight,
            degradation_cost_per_kWh,
        )
    )

    synthetic_schedule_real_cost = (
        calculate_cost_with_external_price(
            synthetic_optimized,
            price_data,
        )
    )

    real_market_schedule_real_cost = (
        calculate_cost_with_external_price(
            real_market_optimized,
            price_data,
        )
    )

    synthetic_schedule_real_emissions = (
        emd.calculate_emissions_with_external_carbon(
            synthetic_optimized, 
            carbon_data,
        )
    )

    real_market_schedule_real_emissions = (
        emd.calculate_emissions_with_external_carbon(
            real_market_optimized,
            carbon_data,
        )
    )

    synthetic_usage = (
        sda.calculate_battery_usage_metrics(
            synthetic_optimized,
            battery_parameters,
        )
    )

    real_market_usage = (
        sda.calculate_battery_usage_metrics(
            real_market_optimized,
            battery_parameters,
        )
    )

    dispatch_summary = (
        create_real_dispatch_summary(
            real_market_optimized,
            real_market_data,
        )
    )

    largest_charging = (
        dispatch_summary.nlargest(
            10,
            "battery_charge_kw",
        )
    )

    largest_discharging = (
        dispatch_summary.nlargest(
            10,
            "battery_discharge_kw"
        )
    )

    active_charging = dispatch_summary.loc[dispatch_summary["battery_charge_kw"] > 0.01].copy()

    active_discharging = dispatch_summary.loc[
        dispatch_summary["battery_discharge_kw"] > 0.01
    ].copy()

    weighted_charge_price = (
        calculate_power_weighted_average(
            active_charging,
            "price_per_kWh",
            "battery_charge_kw",
        )
    )

    weighted_discharge_price = (
        calculate_power_weighted_average(
            active_discharging,
            "price_per_kWh",
            "battery_discharge_kw",
        )
    )

    weighted_charge_carbon = (
        calculate_power_weighted_average(
            active_charging,
            "gCO2/kWh",
            "battery_charge_kw",
        )
    )

    weighted_discharge_carbon = (
        calculate_power_weighted_average(
            active_discharging,
            "gCO2/kWh",
            "battery_discharge_kw"
        )
    )

    no_battery_dispatch = (
        create_no_battery_dispatch(
            real_market_data
        )
    )

    no_battery_cost = (
        calculate_cost_with_external_price(
            no_battery_dispatch,
            price_data,
        )
    )

    no_battery_emissions = (
        emd.calculate_emissions_with_external_carbon(
            no_battery_dispatch,
            carbon_data,
        )
    )

    cost_savings = (
        no_battery_cost
        - real_market_schedule_real_cost
    )

    emissions_reduction = (
        no_battery_emissions
        - real_market_schedule_real_emissions
    )
    #gsd.get_multi_day_caiso_prices test -------------------------------------
    start_date = "2026-08-25"
    number_of_days = 2

    multi_day_price_data = (
        gsd.get_multi_day_caiso_prices(
            start_date,
            number_of_days,
        )
    )

    multi_day_synthetic_data = (
        mda.create_multi_day_dataframe(
            start_date,
            number_of_days
        )
    )

    multi_day_carbon_data = (
        emd.get_multi_day_carbon_data(
            str(api_key),
            "US-CAL-CISO",
            start_date,
            number_of_days
        )
    )

    multi_day_real_market_data = (
        merge_real_market_data(
            multi_day_synthetic_data,
            multi_day_price_data,
            multi_day_carbon_data
        )
    )

    multi_day_synthetic_optimized = (
        sda.run_combined_optimization(
            multi_day_synthetic_data,
            battery_parameters,
            carbon_weight,
            degradation_cost_per_kWh,
        )
    )

    multi_day_real_market_optimized = (
        sda.run_combined_optimization(
            multi_day_real_market_data,
            battery_parameters,
            carbon_weight,
            degradation_cost_per_kWh,
        )
    )

    multi_day_synthetic_real_cost = (
        calculate_cost_with_external_price(
            multi_day_synthetic_optimized,
            multi_day_price_data,
        )
    )

    multi_day_real_market_cost = (
        calculate_cost_with_external_price(
            multi_day_real_market_optimized,
            multi_day_price_data,
        )
    )

    multi_day_synthetic_real_emissions = (
        emd.calculate_emissions_with_external_carbon(
            multi_day_synthetic_optimized,
            multi_day_carbon_data,
        )
    )

    multi_day_real_market_emissions = (
        emd.calculate_emissions_with_external_carbon(
            multi_day_real_market_optimized,
            multi_day_carbon_data,
        )
    )

    multi_day_no_battery = (
        create_no_battery_dispatch(
            multi_day_real_market_data
        )
    )

    multi_day_no_battery_cost = (
        calculate_cost_with_external_price(
            multi_day_no_battery,
            multi_day_price_data,
        )
    )

    multi_day_no_battery_emissions = (
        emd.calculate_emissions_with_external_carbon(
            multi_day_no_battery,
            multi_day_carbon_data,
        )
    )
    multi_day_synthetic_usage = (
    sda.calculate_battery_usage_metrics(
        multi_day_synthetic_optimized,
        battery_parameters,
        )
    )

    multi_day_real_market_usage = (
        sda.calculate_battery_usage_metrics(
        multi_day_real_market_optimized,
        battery_parameters,
        )
    )

    multi_day_dispatch_summary = (
        create_real_dispatch_summary(
            multi_day_real_market_optimized,
            multi_day_real_market_data,
        )
    )

    multi_day_active_charging = (
        multi_day_dispatch_summary.loc[
            multi_day_dispatch_summary[
                "battery_charge_kw"
            ] > 0.01
        ].copy()
    )

    multi_day_active_discharging = (
        multi_day_dispatch_summary.loc[
            multi_day_dispatch_summary[
                "battery_discharge_kw"
            ] > 0.01
        ].copy()
    )

    multi_day_weighted_charge_price = (
        calculate_power_weighted_average(
            multi_day_active_charging,
            "price_per_kWh",
            "battery_charge_kw",
        )
    )

    multi_day_weighted_discharge_price = (
        calculate_power_weighted_average(
            multi_day_active_discharging,
            "price_per_kWh",
            "battery_discharge_kw",
        )
    )

    multi_day_weighted_charge_carbon = (
        calculate_power_weighted_average(
            multi_day_active_charging,
            "gCO2/kWh",
            "battery_charge_kw",
        )
    )

    multi_day_weighted_discharge_carbon = (
        calculate_power_weighted_average(
            multi_day_active_discharging,
            "gCO2/kWh",
            "battery_charge_kw",
        )
    )




    


    #Print Calls #################################################################################

    print(
    "\nSynthetic-signal schedule evaluated "
    "with real CAISO price:"
    )

    print(
        f"${synthetic_schedule_real_cost:.2f}"
    )

    print(
        "Real-market schedule evaluated "
        "with real CAISO price:"
    )

    print(
        f"${real_market_schedule_real_cost:.2f}"
    )

    print(
        "\nSynthetic-signal schedule evaluated "
        "with real carbon:"
    )

    print(
        f"{synthetic_schedule_real_emissions:.2f} kgCO2"
    )

    print(
        "\nReal-market schedule evaluated "
        "with real carbon:"
    )

    print(
        f"{real_market_schedule_real_emissions:.2f} kgCO2"
    )


    print(
    "\nSynthetic-signal battery usage:"
    )

    print(synthetic_usage)

    print(
    "\nReal-market battery usage:"
    )

    print(real_market_usage)

    print(
    "\nLargest real-market charging intervals:"
)

    print(
        largest_charging.to_string(
        index=False
        )
    )

    print(
        "\nLargest real-market discharging intervals:"
    )

    print(
        largest_discharging.to_string(
        index=False
        )
    )

    print(
    "\nActual charging intervals:"
)

    print(
        active_charging.to_string(
        index=False
        )
    )

    print(
        "\nActual discharging intervals:"
    )

    print(
        active_discharging.to_string(
        index=False
        )
    )


    print(
    "\nPower-weighted charging price:",
    f"${weighted_charge_price:.4f}/kWh",
)

    print(
        "Power-weighted discharging price:",
        f"${weighted_discharge_price:.4f}/kWh",
    )

    print(
        "\nPower-weighted charging carbon:",
        f"{weighted_charge_carbon:.2f} gCO2/kWh",
    )

    print(
        "Power-weighted discharging carbon:",
        f"{weighted_discharge_carbon:.2f} gCO2/kWh",
    )


    print(
    "\n=== Real-Market Performance Comparison ==="
)

    print(
        "\nNo battery:"
    )
    print(
        f"Cost: ${no_battery_cost:.2f}"
    )
    print(
        f"Emissions: "
        f"{no_battery_emissions:.2f} kgCO2"
    )


    print(
        "\nSynthetic-signal schedule:"
    )
    print(
        f"Cost: "
        f"${synthetic_schedule_real_cost:.2f}"
    )
    print(
        f"Emissions: "
        f"{synthetic_schedule_real_emissions:.2f} kgCO2"
    )


    print(
        "\nReal-market schedule:"
    )
    print(
        f"Cost: "
        f"${real_market_schedule_real_cost:.2f}"
    )
    print(
        f"Emissions: "
        f"{real_market_schedule_real_emissions:.2f} kgCO2"
    )

    print(
        "\nReal-market battery vs no battery:"
    )

    print(
        f"Cost savings: "
        f"${cost_savings:.2f}"
    )

    print(
        f"Emissions reduction: "
        f"{emissions_reduction:.2f} kgCO2"
    )

    print(
        "\nMulti-day CAISO prices:"
    )

    print(
        multi_day_price_data.head()
    )

    print(
        multi_day_price_data.tail()
    )

    print(
        "Shape:",
        multi_day_price_data.shape,
    )


    print(
    "\n=== Multi-Day Real-Market Data ==="
)

    print(
        multi_day_real_market_data.head()
    )

    print(
        multi_day_real_market_data.tail()
    )

    print(
        "Shape:",
        multi_day_real_market_data.shape,
    )

    print(
        "\n=== 2-Day Real-Market Comparison ==="
    )

    print(
        f"No battery: "
        f"${multi_day_no_battery_cost:.2f}, "
        f"{multi_day_no_battery_emissions:.2f} kgCO2"
    )

    print(
        f"Synthetic-signal schedule: "
        f"${multi_day_synthetic_real_cost:.2f}, "
        f"{multi_day_synthetic_real_emissions:.2f} kgCO2"
    )   

    print(
        f"Real-market schedule: "
        f"${multi_day_real_market_cost:.2f}, "
        f"{multi_day_real_market_emissions:.2f} kgCO2"
    )


    print(
        "\nSynthetic multi-day battery usage:"
    )   
    print(multi_day_synthetic_usage)

    print(
        "\nReal-market multi-day battery usage:"
    )

    print(multi_day_real_market_usage)


    print(
    "\n=== 2-Day Power-Weighted Dispatch Signals ==="
)

    print(
        "Charging price:",
        f"${multi_day_weighted_charge_price:.4f}/kWh",
    )

    print(
        "Discharging price:",
        f"${multi_day_weighted_discharge_price:.4f}/kWh",
    )

    print(
        "Charging carbon:",
        f"{multi_day_weighted_charge_carbon:.2f} gCO2/kWh",
    )

    print(
        "Discharging carbon:",
        f"{multi_day_weighted_discharge_carbon:.2f} gCO2/kWh",
    )


    validate_integrated_market_data(
        multi_day_real_market_data,
        expected_rows=number_of_days * 96,
    )
    
    sda.validate_dispatch(
        multi_day_real_market_optimized,
        battery_parameters,
    )
    
    sda.validate_dispatch(
        multi_day_synthetic_optimized,
        battery_parameters
    )
    
    