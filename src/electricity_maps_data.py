import requests
import os
import pandas as pd
import single_day_analysis as sda

pd.set_option(
    "display.max_columns",
    None,
)

def get_latest_carbon_intensity(
        api_key: str,
        zone: str,
) -> dict:

    url = (
        "https://api.electricitymaps.com/"
        "v4/carbon-intensity/latest"
    )

    headers = {
        "auth-token": api_key,
    }

    params = {
        "zone": zone,
        "temporalGradularity": "15_minutes"
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# Converting result data from Electricity Maps to pandas dataframe 
# so I can processs with built-in functions

def carbon_response_to_dataframe(
    result: dict,
) -> pd.DataFrame:
    data = pd.DataFrame(
        [
            {
                "timestamp": result["datetime"],
                "gCO2/kWh": result["carbonIntensity"],
            }
        ]
    )

    data["timestamp"] = pd.to_datetime(
        data["timestamp"],
        utc=True,
    )

    data["timestamp"] = (
        data["timestamp"]
        .dt.tz_convert(
            "America/Los_Angeles"
        )
    )

    return data


#Return Carbon intensity for set range with granularity set manually inside the function
def get_carbon_intensity_range(
    api_key: str,
    zone: str,
    start: str,
    end: str,
) -> dict:
    
    url = (
        "https://api.electricitymaps.com/"
        "v4/carbon-intensity/past-range"
    )

    headers = {
        "auth-token": api_key
    }

    params = {
        "zone": zone,
        "start": start,
        "end": end,
        "temporalGranularity": "15_minutes",
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def carbon_range_to_dataframe(
        result: dict,
) -> pd.DataFrame:

    data = pd.DataFrame(
        result["data"]
    )

    data = data[
        [
            "datetime",
            "carbonIntensity",
        ]
    ].copy()

    data = data.rename(
        columns={
            "datetime": "timestamp",
            "carbonIntensity": "gCO2/kWh",
        }
    )

    data["timestamp"] = pd.to_datetime(
        data["timestamp"],
        utc=True,
    )

    data["timestamp"] = (
        data["timestamp"]
        .dt.tz_convert(
            "America/Los_Angeles"
        )
    )

    return data


def merge_real_carbon_data(
        synthetic_data: pd.DataFrame,
        carbon_data: pd.DataFrame,
) -> pd.DataFrame:

    base_data = synthetic_data.drop(
        columns=["gCO2/kWh"]
    )

    merged_data = pd.merge(
        base_data,
        carbon_data,
        on="timestamp",
        how="inner",
    )

    return merged_data


def calculate_emissions_with_external_carbon(
        dispatch_data: pd.DataFrame,
        carbon_data: pd.DataFrame,
        timestep_hours: float = 0.25,
) -> float:

    evaluation_data = pd.merge(
        dispatch_data[
            [
                "timestamp",
                "grid_import_kw",
            ]
        ],
        carbon_data,
        on="timestamp",
        how="inner",
    )

    emissions_kgCO2 = (
        (
            evaluation_data["grid_import_kw"]
            * timestep_hours
            * evaluation_data["gCO2/kWh"]
        ).sum()
        / 1000
    )

    return float(emissions_kgCO2)

def create_dispatch_comparison(
        synthetic_optimized: pd.DataFrame,
        real_carbon_optimized: pd.DataFrame,
        carbon_data: pd.DataFrame,
) -> pd.DataFrame:

    tolerance = 1e-6

    comparison = pd.DataFrame(
        {
            "timestamp": real_carbon_optimized["timestamp"],
            "gCO2/kWh": carbon_data["gCO2/kWh"],
            "synthetic_charge_kw": synthetic_optimized[
                "battery_charge_kw"
            ],
            "synthetic_discharge_kw": synthetic_optimized[
                "battery_discharge_kw"
            ],
            "real_charge_kw": real_carbon_optimized[
                "battery_charge_kw"
            ],
            "real_discharge_kw": real_carbon_optimized[
                "battery_discharge_kw"
            ],
        }
    )

    comparison["charge_difference_kw"] = (
        comparison["real_charge_kw"]
        - comparison["synthetic_charge_kw"]
    )

    comparison["discharge_difference_kw"] = (
        comparison["real_discharge_kw"]
        - comparison["synthetic_discharge_kw"]
    )

    comparison["total_dispatch_difference_kw"] = (
        comparison["charge_difference_kw"].abs()
        + comparison["discharge_difference_kw"].abs()
    )

    comparison.loc[
        comparison["real_charge_kw"].abs() < tolerance,
        "real_charge_kw"
    ] = 0.0

    comparison.loc[
        comparison["synthetic_discharge_kw"].abs() < tolerance,
        "synthetic_discharge_charge_kw"
    ] = 0.0

    comparison.loc[
        comparison["synthetic_charge_kw"].abs() < tolerance,
        "synthetic_charge_kw"
    ] = 0.0

    comparison.loc[
        comparison["real_discharge_kw"].abs() < tolerance,
        "real_discharge_kw"
    ] = 0.0


    return comparison









## Main -----------------------------------------------------------------
if __name__ == "__main__":

    api_key = os.getenv(
        "ELECTRICITY_MAPS_API_KEY"
    )

    if api_key is None:
        raise ValueError(
            "API Key is not set."
        )

    result = get_carbon_intensity_range(
        api_key=api_key,
        zone = "US-CAL-CISO",
        start="2026-08-26T07:00:00Z",
        end="2026-08-27T07:00:00Z",
    )

    carbon_data = carbon_range_to_dataframe(
        result
    )

    synthetic_data = sda.create_sample_dataframe(
        date = "2026-08-26"
    )

    merged_data = merge_real_carbon_data(
        synthetic_data,
        carbon_data,
    )

    synthetic_optimized = sda.run_combined_optimization(
        synthetic_data.copy(),
        sda.battery_parameters,
        carbon_weight=0.20,
        degradation_cost_per_kWh=0.03
    )

    real_carbon_optimized = sda.run_combined_optimization(
        merged_data.copy(),
        sda.battery_parameters,
        carbon_weight=0.20,
        degradation_cost_per_kWh=0.03
    )

    synthetic_metrics = sda.calculate_dispatch_metrics(
        synthetic_optimized
    )

    real_carbon_metrics = sda.calculate_dispatch_metrics(
        real_carbon_optimized
    )

    synthetic_battery_usage = sda.calculate_battery_usage_metrics(
        synthetic_optimized,
        sda.battery_parameters,
    )

    real_carbon_battery_usage = sda.calculate_battery_usage_metrics(
        real_carbon_optimized,
        sda.battery_parameters,
    )

    synthetic_schedule_real_emissions = (
        calculate_emissions_with_external_carbon(
            synthetic_optimized,
            carbon_data,
        )
    )

    real_schedule_real_emissions = (
        calculate_emissions_with_external_carbon(
            real_carbon_optimized,
            carbon_data,
        )
    )

    emissions_difference = (
        real_schedule_real_emissions
        - synthetic_schedule_real_emissions
    )

    emissions_change_percent = (
        emissions_difference
        / synthetic_schedule_real_emissions
        * 100
    )

    dispatch_comparison = create_dispatch_comparison(
        synthetic_optimized,
        real_carbon_optimized,
        carbon_data,
    )

    largest_differences = (
        dispatch_comparison
        .sort_values(
            by="total_dispatch_difference_kw",
            ascending=False,
        )
        .head(10)
    )

    real_charging_intervals = (
        dispatch_comparison[
            dispatch_comparison["real_charge_kw"] > 0.01
        ]
    )

    real_discharging_intervals = (
        dispatch_comparison[
            dispatch_comparison["real_discharge_kw"] > 0.01
        ]
    )

    average_charge_carbon = (
        real_charging_intervals["gCO2/kWh"].mean()
    )

    average_discharge_carbon = (
        real_discharging_intervals["gCO2/kWh"].mean()
    )

    print(
    "\nSynthetic-carbon schedule evaluated with real carbon:",
        f"{synthetic_schedule_real_emissions:.2f} kgCO2",
)

    print(
        "Real-carbon schedule evaluated with real carbon:",
        f"{real_schedule_real_emissions:.2f} kgCO2",
    )

    print(
        "Emissions difference:",
        f"{emissions_difference:.2f} kgCO2",
    )

    print(
        "Emissions change:",
        f"{emissions_change_percent:.2f}%",
    )

    print(
        "\nLargeest dispatch differences:"
    )

    print(
        largest_differences[
            [
            "timestamp",
            "gCO2/kWh",
            "synthetic_charge_kw",
            "real_charge_kw",
            "synthetic_discharge_kw",
            "real_discharge_kw",
            "total_dispatch_difference_kw",
            ]
        ]
    )

    print(
        "\nAverage carbon intensity during real-carbon charging:",
        f"{average_charge_carbon:.2f} gCO2/kWh",
    )

    print(
        "Average carbon intensity during real-carbon discharging:",
        f"{average_discharge_carbon:.2f} gCO2/kWh",
    )

    




    


