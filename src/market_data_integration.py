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
from results import ExperimentResult
from experiment_data import ExperimentData
from dataclasses import replace

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
        config: ExperimentConfig,
        data: ExperimentData,
        battery_parameters: dict[str, float],
) -> ExperimentResult:

    synthetic_data = data.synthetic_data
    price_data = data.price_data
    carbon_data = data.carbon_data
    real_market_data = data.real_market_data

    ## 2. Validate Integrated input data

    validate_integrated_market_data(
        real_market_data,
        expected_rows=config.number_of_days * 96,
    )

    # 3. Run optimization
    synthetic_optimized = (
        sda.run_combined_optimization(
            synthetic_data,
            battery_parameters,
            config.carbon_weight,
            config.degradation_cost_per_kWh,
        )
    )

    real_market_optimized = (
        sda.run_combined_optimization(
            real_market_data,
            battery_parameters,
            config.carbon_weight,
            config.degradation_cost_per_kWh,
        )
    )

    #4. Validate Optimized Dispatch

    sda.validate_dispatch(
        synthetic_optimized,
        battery_parameters,
    )

    sda.validate_dispatch(
        real_market_optimized,
        battery_parameters,
    )

    #5. No-battery baseline

    no_battery_dispatch = (
        create_no_battery_dispatch(
            real_market_data,
        )
    )

    #6. Evaluate cost using Real CAISO Prices

    no_battery_cost = (
        calculate_cost_with_external_price(
            no_battery_dispatch,
            price_data,
        )
    )

    synthetic_real_cost = (
        calculate_cost_with_external_price(
            synthetic_optimized,
            price_data,
        )
    )

    real_market_cost = (
        calculate_cost_with_external_price(
            real_market_optimized,
            price_data,
        )
    )

    #7. Evaluate emissions using Real carbon data

    no_battery_emissions = (
        emd.calculate_emissions_with_external_carbon(
            no_battery_dispatch,
            carbon_data,
        )
    )

    synthetic_real_emissions = (
        emd.calculate_emissions_with_external_carbon(
            synthetic_optimized,
            carbon_data,
        )
    )

    real_market_emissions = (
        emd.calculate_emissions_with_external_carbon(
            real_market_optimized,
            carbon_data,
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

    real_market_degradation_cost = (
        real_market_usage["throughput_kWh"]
        * config.degradation_cost_per_kWh
    )

    real_market_total_operating_cost = (
        real_market_cost
        + real_market_degradation_cost
    )

    #9. Analyze real-market dispatch
    dispatch_summary = (
        create_real_dispatch_summary(
            real_market_optimized,
            real_market_data,
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

    operating_cost_savings = (
        no_battery_cost
        - real_market_total_operating_cost
    )

    emissions_reduction = (
        no_battery_emissions
        - real_market_emissions
    )

    daily_summary = calculate_daily_metrics(
        data=real_market_optimized,
        degradation_cost_per_kWh=(
            config.degradation_cost_per_kWh
        ),
        timestep_hours=config.timestep_hours,
    )

    #11. Print Results

    print(
        f"\n=== {config.number_of_days}-Day "
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

    print(
        "\n=== Daily Performance ==="
    ) 

    print(
        daily_summary.to_string(
            index=False
        )
    )


    return ExperimentResult(
        no_battery_cost=float(
            no_battery_cost
        ),

        no_battery_emissions=float(
            no_battery_emissions
        ),

        synthetic_real_cost=float(
            synthetic_real_cost
        ),

        synthetic_real_emissions=float(
            synthetic_real_emissions
        ),

        real_market_cost=float(
            real_market_cost
        ),

        real_market_emissions=float(
            real_market_emissions
        ),

        cost_savings=float(
            cost_savings
        ),

        emissions_reduction=float(
            emissions_reduction
        ),

        synthetic_usage=synthetic_usage,
        real_market_usage=real_market_usage,

        weighted_charge_price=float(
            weighted_charge_price
        ),

        weighted_discharge_price = float(
            weighted_discharge_price
        ),

        weighted_charge_carbon = float(
            weighted_charge_carbon
        ),

        weighted_discharge_carbon = float(
            weighted_discharge_carbon
        ),

        real_market_degradation_cost = float(
            real_market_degradation_cost
        ),

        real_market_total_operating_cost = float(
            real_market_total_operating_cost
        ),

        operating_cost_savings = float(
            operating_cost_savings
        ),

        daily_summary = daily_summary,
    )

def experiment_result_to_dict(
    experiment_name: str,
    result: ExperimentResult,
) -> dict[str, float | str]:
    return {
        "experiment_name": experiment_name,

        "no_battery_cost": result.no_battery_cost,

        "real_market_cost": result.real_market_cost,

        "cost_savings": result.cost_savings,

        "no_battery_emissions": result.no_battery_emissions,

        "real_market_emissions": result.real_market_emissions,

        "emissions_reduction": result.emissions_reduction,

        "battery_throughput_kWh": result.real_market_usage["throughput_kWh"],

        "equivalent_full_cycles": result.real_market_usage["equivalent_full_cycles"],

        "degradation_cost": result.real_market_degradation_cost,

        "total_operating_cost": result.real_market_total_operating_cost,

        "operating_cost_savings": result.operating_cost_savings,
    }

def prepare_experiment_data(
    config: ExperimentConfig,
    api_key: str,
) -> ExperimentData:

    synthetic_data = (
        mda.create_multi_day_dataframe(
            config.start_date,
            config.number_of_days,
        )
    )

    price_data = (
        gsd.get_caiso_real_time_prices_range(
            start_date=config.start_date,
            number_of_days=config.number_of_days,
            sleep_seconds=config.sleep_seconds,
        )
    )

    carbon_data = (
        emd.get_multi_day_carbon_data(
            api_key,
            config.electricity_maps_zone,
            config.start_date,
            config.number_of_days,
        )
    )

    real_market_data = (
        merge_real_market_data(
            synthetic_data,
            price_data,
            carbon_data,
        )
    )

    validate_integrated_market_data(
        real_market_data,
        expected_rows=(
            config.number_of_days * 96
        ),
    )

    return ExperimentData(
        synthetic_data = synthetic_data,
        price_data=price_data,
        carbon_data=carbon_data,
        real_market_data=real_market_data,
    )


def calculate_daily_metrics(
        data:pd.DataFrame,
        degradation_cost_per_kWh: float,
        timestep_hours: float = 0.25,
) -> pd.DataFrame:

    daily_data = data.copy()

    daily_data["date"] = (
        daily_data["timestamp"].dt.date
    )

    daily_data["grid_import_kWh"] = (
        daily_data["grid_import_kw"]
        * timestep_hours
    )

    daily_data["grid_cost"] = (
        daily_data["grid_import_kw"]
        * timestep_hours
        * daily_data["price_per_kWh"]
    )

    daily_data["emissions_kgCO2"] = (
        daily_data["grid_import_kw"]
        * timestep_hours
        * daily_data["gCO2/kWh"]
        / 1000
    )

    daily_data["battery_charge_kWh"] = (
        daily_data["battery_charge_kw"]
        * timestep_hours
    )

    daily_data["battery_discharge_kWh"] = (
        daily_data["battery_discharge_kw"]
        * timestep_hours
    )

    daily_summary = (
        daily_data
        .groupby("date")
        .agg(
            grid_import_kWh = (
                "grid_import_kWh",
                "sum",
            ),
            grid_cost = (
                "grid_cost",
                "sum",
            ),
            emissions_kgCO2=(
                "emissions_kgCO2",
                "sum",
            ),
            charge_kWh=(
                "battery_charge_kWh",
                "sum"
            ),
            discharge_kWh=(
                "battery_discharge_kWh",
                "sum",
            ),
        ).reset_index()
    )

    daily_summary["throughput_kWh"] = (
        daily_summary["charge_kWh"]
        + daily_summary["discharge_kWh"]
    )

    daily_summary["degradation_cost"] = (
        daily_summary["throughput_kWh"]
        * degradation_cost_per_kWh
    )

    return daily_summary


def calculate_normalized_kpis(
    result: ExperimentResult,
    number_of_days: int,
) -> dict[str, float]:

    cost_savings_percentage = (
        result.operating_cost_savings
        / result.no_battery_cost
        * 100
    )

    emissions_reduction_percentage = (
        result.emissions_reduction
        / result.no_battery_emissions
        * 100
    )

    average_daily_cost_savings = (
        result.operating_cost_savings
        / number_of_days
    )

    average_daily_emissions_reduction = (
        result.emissions_reduction
        / number_of_days
    )

    equivalent_full_cycles_per_day = (
        result.real_market_usage[
            "equivalent_full_cycles"
        ]
        / number_of_days
    )

    return {
        "cost_savings_percentage": cost_savings_percentage,
        "emissions_reduction_percentage": emissions_reduction_percentage,
        "average_daily_cost_savings": average_daily_cost_savings,
        "average_daily_emissions_reduction": average_daily_emissions_reduction,
        "equivalent_full_cycles_per_day": equivalent_full_cycles_per_day,
    }

    

    
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
    
    # Configuration must declare start_date and number_of_days, others are optional
    # Goto config.py to see all available parameters
    baseline_config = ExperimentConfig(
        start_date="2026-08-25",
        number_of_days = 2,
    )

    ##replace carbon_weight from baseline_config
    high_carbon_config = replace(
        baseline_config,
        carbon_weight = 0.50,
    )
    
    previous_runtime = load_previous_runtime()
    start_time = time.perf_counter()

    experiment_data = prepare_experiment_data(
        config=baseline_config,
        api_key=api_key,
    )

    #list for creating multiple carbon_weights cases
    carbon_weights = [
        0.00,
        0.20,
        0.50,
    ]
    #list for storing experiment result summaries
    experiment_summaries = []

    for carbon_weight in carbon_weights:

        current_config = replace(
            baseline_config,
            carbon_weight = carbon_weight,
        )

        result = run_multi_day_experiment(
            config = current_config,
            data=experiment_data,
            battery_parameters=battery_parameters,
        )

        summary = experiment_result_to_dict(
            experiment_name=(
                f"Carbon weight {carbon_weight}"
            ),
            result=result,
        )

        experiment_summaries.append(
            summary
        )

    result0 = run_multi_day_experiment(
        config=baseline_config,
        data=experiment_data,
        battery_parameters=battery_parameters
    )

    result_summary0 = experiment_result_to_dict(
        "Baseline",
        result0,
    )

    summary_table = pd.DataFrame(
        [result_summary0],
    )

    comparison_table = pd.DataFrame(
        experiment_summaries
    )

    kpis = calculate_normalized_kpis(
        result = result0,
        number_of_days = baseline_config.number_of_days
    )


    end_time = time.perf_counter()
    run_time = end_time - start_time
        
    if previous_runtime is not None:
        print(
            f"Previous runtime: "
            f"{previous_runtime:3f}s"
        )
    #print(f"Current runtime with sleep seconds ({config.sleep_seconds}): {run_time:.3f}s.")

    save_runtime(run_time)

    print(
        f"\nReal-market cost: ${result0.real_market_cost:.2f}"
    )

    print(
        f"\nReal-market emissions: {result0.real_market_emissions:.2f} kgCO2"
    )

    print(
        f"\nReal-market usage: {result0.real_market_usage}"
    )

    print(
        f"\n\n{result_summary0}"
    )

    print(
        summary_table.to_string(
            index = False,
        )
    )

    print(
        "\n=== Carbon Weight Comparison ==="
    )

    print(
        comparison_table.to_string(
            index = False
        )
    )

    print(kpis)