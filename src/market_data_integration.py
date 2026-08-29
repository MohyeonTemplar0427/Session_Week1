import os
import pandas as pd
from pathlib import Path
import json
from dotenv import load_dotenv, find_dotenv

import single_day_analysis as sda
import electricity_maps_data as emd
import gridstatus_data as gsd
import multi_day_analysis as mda
import time
from battery import Battery
from config import ExperimentConfig, to_optimizer_parameters

battery = Battery(
    capacity_kWh = 20.0,
    SOC_min = 0.1,
    SOC_max = 0.9,
    energy_kWh = 10.0,
    charge_efficiency = 0.95,
    discharge_efficiency = 0.95,
    max_charge_kw = 5.0,
    max_discharge_kw = 5.0,
)

RUNTIME_FILE = Path("data/runtime.json")

env_path = find_dotenv()

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

CAISO_CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "caiso"
)

RUNTIME_FILE = Path("data/previous_runtime.txt")

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


def load_previous_runtime() -> float | None:
    if not RUNTIME_FILE.exists():
        return None

    with open(RUNTIME_FILE, "r") as file:
        data = json.load(file)

    return float(data["runtime"])

def save_runtime(runtime:float) -> None:
    RUNTIME_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(RUNTIME_FILE, "w") as file:
        json.dump(
            {"runtime": runtime},
            file,
            indent = 4
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

##Running multi-day experiment with input parameters
def run_multi_day_experiment(
        start_date: str,
        number_of_days: int,
        api_key: str,
        battery_parameters: dict[str, float],
        carbon_weight: float,
        degradation_cost_per_kWh: float,
        sleep_seconds: float = 5.0
) -> None:

    multi_day_synthetic_data = (
        mda.create_multi_day_dataframe(
            start_date,
            number_of_days,
        )
    )

    multi_day_price_data = (
        gsd.get_caiso_real_time_prices_range(
            start_date=start_date,
            number_of_days=number_of_days,
            sleep_seconds=sleep_seconds,
        )
    )

    multi_day_carbon_data = (
        emd.get_multi_day_carbon_data(
            api_key,
            "US-CAL-CISO",
            start_date,
            number_of_days,
        )
    )

    multi_day_real_market_data = (
        merge_real_market_data(
            multi_day_synthetic_data,
            multi_day_price_data,
            multi_day_carbon_data,
        )
    )

    ## 2. Validate Integrated input data

    validate_integrated_market_data(
        multi_day_real_market_data,
        expected_rows = number_of_days * 96
    )

    # 3. Run optimization
    synthetic_optimized = (
        sda.run_combined_optimization(
            multi_day_synthetic_data,
            battery_parameters,
            carbon_weight,
            degradation_cost_per_kWh,
        )
    )

    real_market_optimized = (
        sda.run_combined_optimization(
            multi_day_real_market_data,
            battery_parameters,
            carbon_weight,
            degradation_cost_per_kWh,
        )
    )

    #4. Validate Optimized Dispatch

    sda.validate_dispatch(
        synthetic_optimized,
        battery_parameters
    )

    sda.validate_dispatch(
        real_market_optimized,
        battery_parameters,
    )

    #5. No-battery baseline

    no_battery_dispatch = (
        create_no_battery_dispatch(
            multi_day_real_market_data
        )
    )

    #6. Evaluate cost using Real CAISO Prices

    no_battery_cost = (
        calculate_cost_with_external_price(
            no_battery_dispatch,
            multi_day_price_data,
        )
    )

    synthetic_real_cost = (
        calculate_cost_with_external_price(
            synthetic_optimized,
            multi_day_price_data,
        )
    )

    real_market_cost = (
        calculate_cost_with_external_price(
            real_market_optimized,
            multi_day_price_data,
        )
    )

    #7. Evaluate emissions using Real carbon data

    no_battery_emissions =(
        emd.calculate_emissions_with_external_carbon(
            no_battery_dispatch,
            multi_day_carbon_data,
        )
    )

    synthetic_real_emissions = (
        emd.calculate_emissions_with_external_carbon(
            synthetic_optimized,
            multi_day_carbon_data,
        )
    )

    real_market_emissions = (
        emd.calculate_emissions_with_external_carbon(
            real_market_optimized,
            multi_day_carbon_data,
        )
    )

    # 8. Battery Usage

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

    #9. Analyze real-market dispatch
    dispatch_summary = (
        create_real_dispatch_summary(
            real_market_optimized,
            multi_day_real_market_data,
        )
    )

    active_charging = (
        dispatch_summary.loc[
            dispatch_summary[
                "battery_charge_kw"
            ] > 0.01
        ].copy()
    )

    active_discharging = (
        dispatch_summary.loc[
            dispatch_summary[
                "battery_discharge_kw"
            ] > 0.01
        ].copy()
    )

    weighted_charge_price = (
        calculate_power_weighted_average(
            active_charging,
            "price_per_kWh",
            "battery_charge_kw",
        )
    )

    weighted_discharge_price =(
        calculate_power_weighted_average(
            active_discharging,
            "price_per_kWh",
            "battery_discharge_kw"
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
            "battery_discharge_kw",
        )
    )

    # 10. Improvements vs no battery
    cost_savings = (
        no_battery_cost
        - real_market_cost
    )

    emissions_reduction = (
        no_battery_emissions
        - real_market_emissions
    )

    #11. Print Results

    print(
        f"\n=== {number_of_days}-Day "
        "Real-Market Experiment ==="
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
        f"Cost: ${synthetic_real_cost:.2f}"
    )

    print(
        f"Emissions: "
        f"{synthetic_real_emissions:.2f} kgCO2"
    )

    print(
        "\nReal-market schedule:"
    )

    print(
        f"Cost: ${real_market_cost:.2f}"
    )

    print(
        f"Emissions: "
        f"{real_market_emissions:.2f} kgCO2"
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
        "\nSynthetic battery usage:"
    )

    print(
        synthetic_usage
    )

    print(
        "\nReal-market battery usage:"
    )

    print(
        real_market_usage
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
        "\nMulti-day experiment completed."
    )

    return None



# Main--------------------------------------------------------------------------------------------
if __name__ == "__main__":

    if api_key is None:
        raise ValueError(
            "Electricity Maps API key not loaded."
        )

    battery = Battery(
        capacity_kWh = 20.0,
        SOC_min = 0.1,
        SOC_max = 0.9,
        energy_kWh = 10.0,
        charge_efficiency = 0.95,
        discharge_efficiency = 0.95,
        max_charge_kw = 5.0,
        max_discharge_kw = 5.0,
    )

    battery_parameters = to_optimizer_parameters(battery)

    config = ExperimentConfig(
        start_date="2026-08-25",
        number_of_days=2,
    )

    ## sleep_second for gridstatus api request
    test_sleep_seconds = 0.0

    previous_runtime = load_previous_runtime()
    start_time = time.perf_counter()
    
    run_multi_day_experiment(
        start_date="2026-08-25",
        number_of_days=2,
        api_key=api_key,
        battery_parameters=battery_parameters,
         carbon_weight=0.20,
        degradation_cost_per_kWh=0.03,
        sleep_seconds=test_sleep_seconds
    )

    end_time = time.perf_counter()
    run_time = end_time - start_time
        
    if previous_runtime is not None:
        print(
            f"Previous runtime: "
            f"{previous_runtime:3f}s"
        )
    print(f"Cuerrent runtime with sleep seconds ({test_sleep_seconds}): {run_time:.3f}s.")

    save_runtime(run_time)

    print(config)
    print(config.start_date)
    print(config.number_of_days)
    print(config.carbon_weight)
    print(config.caiso_node)