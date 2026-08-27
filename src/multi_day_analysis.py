import pandas as pd
import single_day_analysis as sda

def create_multi_day_dataframe(
    start_date: str,
    number_of_days: int,
) ->pd.DataFrame:

    daily_dataframes = []

    start_timestamp = pd.Timestamp(start_date)

    for day_offset in range(number_of_days):

        current_date = (
            start_timestamp
            + pd.Timedelta(days=day_offset)
        )

        daily_data = sda.create_sample_dataframe(
            date=current_date.strftime("%Y-%m-%d")
        )

        daily_dataframes.append(
            daily_data
        )

    multi_day_data = pd.concat(
        daily_dataframes,
        ignore_index=True,
    )

    return multi_day_data


#optimize each day separately and concatenate the seven optimized daily results
def run_daily_reset_optimization(
        weekly_data: pd.DataFrame,
)-> pd.DataFrame:

    optimized_days = []

    for index, daily_data in weekly_data.groupby(
        weekly_data["timestamp"].dt.date
    ):
        optimized_day = sda.run_combined_optimization(
            daily_data.copy(),
            sda.battery_parameters,
            carbon_weight=0.20,
            degradation_cost_per_kWh=0.03,
        )

        optimized_days.append(
            optimized_day
        )

    daily_reset_data = pd.concat(
        optimized_days,
        ignore_index=True,
    )

    return daily_reset_data

def calculate_daily_metrics(
        data: pd.DataFrame,
) -> pd.DataFrame:

    daily_results = []

    for date, daily_data in data.groupby(
        data["timestamp"].dt.date
    ):
        dispatch_metrics = sda.calculate_dispatch_metrics(
            daily_data
        )

        battery_metrics = sda.calculate_battery_usage_metrics(
            daily_data,
            sda.battery_parameters
        )

        daily_results.append(
            {
                "date": date,
                "grid_import_kWh": dispatch_metrics["grid_import_kWh"],
                "cost": dispatch_metrics["cost"],
                "emissions_kgCO2": dispatch_metrics["emissions_kgCO2"],
                "throughput_kWh": battery_metrics["throughput_kWh"],
                "equivalent_full_cycles": battery_metrics[
                    "equivalent_full_cycles"
                ],
            }
        )
    daily_metrics = pd.DataFrame(
        daily_results,
    )

    return daily_metrics
        
    











#Main()-------------------------------------------------------------------------------
if __name__ == "__main__":
    weekly_data = create_multi_day_dataframe(
        start_date = "2026-08-01",
        number_of_days = 7,
    )

    time_differences = (
        weekly_data["timestamp"]
        .diff()
        .dropna()
    )

    weekly_optimized_data = sda.run_combined_optimization(
        weekly_data.copy(),
        sda.battery_parameters,
        carbon_weight=0.20,
        degradation_cost_per_kWh=0.03,
    )

    sda.validate_dispatch(
        weekly_optimized_data,
        sda.battery_parameters,
    )

    weekly_dispatch_metrics = sda.calculate_dispatch_metrics(
        weekly_optimized_data
    )

    weekly_battery_usage = sda.calculate_battery_usage_metrics(
        weekly_optimized_data,
        sda.battery_parameters,
    )

    daily_end_soc = weekly_optimized_data[
        weekly_optimized_data["timestamp"].dt.hour.eq(23)
        &
        weekly_optimized_data["timestamp"].dt.minute.eq(45)
    ][
        ["timestamp", "battery_soc_kWh"]
    ]

    daily_reset_data = run_daily_reset_optimization(
        weekly_data
    )

    daily_reset_metrics = sda.calculate_dispatch_metrics(
        daily_reset_data
    )

    daily_reset_battery_usage = sda.calculate_battery_usage_metrics(
        daily_reset_data,
        sda.battery_parameters,
    )

    weekly_daily_metrics = calculate_daily_metrics(
        weekly_optimized_data
    )

    daily_reset_daily_metrics = calculate_daily_metrics(
        daily_reset_data
    )
    #Print
    print(
    "\nWeekly dispatch metrics:",
    weekly_dispatch_metrics,
    )

    print(
        "\nWeekly battery usage:",
        weekly_battery_usage,
    )

    print(
        "\nEnd-of-day SOC:"
    )

    print(
        daily_end_soc
    )

    print(
    "\nDaily-reset dispatch metrics:",
    daily_reset_metrics,
    )

    print(
        "\nDaily-reset battery usage:",
        daily_reset_battery_usage,
    )

    print(
        "\nWeekly-horizon daily metrics:"
    )

    print(
        weekly_daily_metrics
    )

    print(
        "\nDaily-reset daily metrics:"
    )

    print(
        daily_reset_daily_metrics
    )

    