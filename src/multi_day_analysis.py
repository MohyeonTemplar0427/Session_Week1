import pandas as pd
import single_day_analysis as sda
import matplotlib.pyplot as plt


def apply_daily_variation(
        daily_data: pd.DataFrame,
        load_factor: float,
        pv_factor:float,
) -> pd.DataFrame:
    varied_data = daily_data.copy()

    varied_data["load_kw"] = (
        varied_data["load_kw"]
        * load_factor
    )

    varied_data["pv_kw"] = (
        varied_data["pv_kw"]
        * pv_factor
    )

    varied_data["net_load_kw"] = (
        varied_data["load_kw"]
        - varied_data["pv_kw"]
    )

    return varied_data

def compare_daily_metrics(
        weekly_metrics:pd.DataFrame,
        daily_reset_metrics: pd.DataFrame,
) -> pd.DataFrame:

    comparison = pd.merge(
        weekly_metrics,
        daily_reset_metrics,
        on = "date",
        suffixes = (
            "_weekly",
            "_daily_reset",
        ),
    )

    comparison["cost_difference"] = (
        comparison["cost_weekly"]
        - comparison["cost_daily_reset"]
    )

    comparison["emissions_difference"] = (
        comparison["emissions_kgCO2_weekly"]
        - comparison["emissions_kgCO2_daily_reset"]
    )

    comparison["efc_difference"] = (
        comparison["equivalent_full_cycles_weekly"]
        - comparison["equivalent_full_cycles_daily_reset"]
    )

    return comparison

def create_multi_day_dataframe(
    start_date: str,
    number_of_days: int,
) ->pd.DataFrame:

    if number_of_days <= 0:
        raise ValueError(
            "number_of_days must be greater than 0."
        )

    daily_dataframes = []

    start_timestamp = pd.Timestamp(start_date)
    load_factors = [
        1.00,
        1.05,
        0.98,
        1.03,
        1.08,
        0.92,
        0.90,
    ]

    pv_factors = [
        1.00,
        0.85,
        0.60,
        1.10,
        0.90,
        0.70,
        1.05,
    ]
    
    for day_offset in range(number_of_days):

        current_date = (
            start_timestamp
            + pd.Timedelta(days=day_offset)
        )

        factor_index = (
            day_offset
            % len(load_factors)
        )

        is_weekend = (
            current_date.dayofweek >= 5
        )

        if is_weekend:
            calendar_load_factor = 0.85
        else:
            calendar_load_factor = 1.00

        final_load_factor = (
            load_factors[factor_index]
            * calendar_load_factor
        )

        daily_data = sda.create_sample_dataframe(
            date=current_date.strftime("%Y-%m-%d")
        )

        daily_data = apply_daily_variation(
            daily_data,
            load_factor=final_load_factor,
            pv_factor=pv_factors[factor_index]
        )

        daily_dataframes.append(
            daily_data
        )
        print(
                current_date.strftime("%Y-%m-%d"),
                current_date.day_name(),
                final_load_factor,
            )

    multi_day_data = pd.concat(
        daily_dataframes,
        ignore_index=True,
    )

    return multi_day_data

# Plotting
def plot_weekly_soc(
        data:pd.DataFrame,
) -> None:

    plt.figure(
        figsize=(12, 5)
    )

    plt.plot(
        data["timestamp"],
        data["battery_soc_kWh"],
    )

    plt.xlabel(
        "Time"
    )

    plt.ylabel(
        "Battery SOC (kWh)"
    )

    plt.grid(
        True
    )

    plt.tight_layout()

    plt.show()

def plot_soc_comparison(
    weekly_data: pd.DataFrame,
    daily_reset_data: pd.DataFrame,
) -> None:
    plt.figure(
        figsize=(12, 5)
    )

    plt.plot(
        weekly_data["timestamp"],
        weekly_data["battery_soc_kWh"],
        label="Weekly horizon",
    )

    plt.plot(
        daily_reset_data["timestamp"],
        daily_reset_data["battery_soc_kWh"],
        label="Daily reset",
    )

    plt.xlabel(
        "Time"
    )

    plt.ylabel(
        "Battery SOC (kWh)"
    )

    plt.title(
        "Weekly Horizon vs Daily-Reset Battery SOC"
    )

    plt.legend()

    plt.grid(True)

    plt.tight_layout()

    plt.show()

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


def create_weekly_comparison(
    weekly_data: pd.DataFrame,
    daily_reset_data: pd.DataFrame,
) -> pd.DataFrame:

    weekly_dispatch = sda.calculate_dispatch_metrics(
        weekly_data
    )

    weekly_battery = sda.calculate_battery_usage_metrics(
        weekly_data,
        sda.battery_parameters,
    )

    daily_dispatch = sda.calculate_dispatch_metrics(
        daily_reset_data
    )

    daily_battery = sda.calculate_battery_usage_metrics(
        daily_reset_data,
        sda.battery_parameters,
    )

    comparison = pd.DataFrame(
        [
            {
                "strategy": "Weekly horizon",
                "grid_import_kWh": weekly_dispatch[
                    "grid_import_kWh"
                ],
                "cost": weekly_dispatch["cost"],
                "emissions_kgCO2": weekly_dispatch[
                    "emissions_kgCO2"
                ],
                "throughput_kWh": weekly_battery[
                    "throughput_kWh"
                ],
                "equivalent_full_cycles": weekly_battery[
                    "equivalent_full_cycles"
                ],
            },
            {
                "strategy": "Daily reset",
                "grid_import_kWh": daily_dispatch[
                    "grid_import_kWh"
                ],
                "cost": daily_dispatch["cost"],
                "emissions_kgCO2": daily_dispatch[
                    "emissions_kgCO2"
                ],
                "throughput_kWh": daily_battery[
                    "throughput_kWh"
                ],
                "equivalent_full_cycles": daily_battery[
                    "equivalent_full_cycles"
                ],
            },
        ]
    )

    return comparison



#Main()-------------------------------------------------------------------------------
if __name__ == "__main__":
    weekly_data = create_multi_day_dataframe(
        start_date = "2026-08-01",
        number_of_days = 14,
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

    daily_comparison = compare_daily_metrics(
        weekly_daily_metrics, 
        daily_reset_daily_metrics,
    )

    weekly_comparison = create_weekly_comparison(
        weekly_optimized_data,
        daily_reset_data,
    )

    weekly_row = weekly_comparison[
        weekly_comparison["strategy"] == "Weekly horizon"
    ].iloc[0]

    daily_row = weekly_comparison[
        weekly_comparison["strategy"] == "Daily reset"
    ].iloc[0]

    grid_import_diff_percent = (
        (
            weekly_row["grid_import_kWh"]
            - daily_row["grid_import_kWh"]
        )
        / daily_row["grid_import_kWh"]
        * 100
    )

    throughput_diff_percent = (
        (
            weekly_row["throughput_kWh"]
            - daily_row["throughput_kWh"]
        )
        / daily_row["throughput_kWh"]
        * 100
    )

    efc_diff_percent = (
        (
            weekly_row["equivalent_full_cycles"]
            - daily_row["equivalent_full_cycles"]
        )
        / daily_row["equivalent_full_cycles"]
        * 100
    ) 

    cost_diff_percent = (
        (
            weekly_row["cost"]
            - daily_row["cost"]
        )
        / daily_row["cost"]
        * 100
    )

    emissions_diff_percent = (
        (
            weekly_row["emissions_kgCO2"]
            - daily_row["emissions_kgCO2"]
        )
        / daily_row["emissions_kgCO2"]
        * 100
    )


    #Print
    print("\nDaily load and PV totals:")

    print(
        weekly_data.groupby(
            weekly_data["timestamp"].dt.date
        )[["load_kw","pv_kw"]].sum()
    )

    print(
        "\nDaily optimization comparison:"
    )

    print(
        daily_comparison[
            [
                "date",
                "cost_weekly",
                "cost_daily_reset",
                "cost_difference",
                "emissions_kgCO2_weekly",
                "emissions_kgCO2_daily_reset",
                "emissions_difference",
            ]
        ]
    )
    """
    plot_weekly_soc(
        weekly_optimized_data
    )
    """

    print(
        "\nWeekly strategy comparison:"
    )

    print(
        weekly_comparison
    )

    print(
        "\nWeekly horizon vs daily reset:"
    )

    print(
        f"Grid import difference: "
        f"{grid_import_diff_percent:.2f}%"
    )

    print(
        f"Battery throughput difference: "
        f"{throughput_diff_percent:.2f}%"
    )

    print(
        f"EFC change: "
        f"{efc_diff_percent:.2f}%"
    )

    print(
        f"Cost difference: "
        f"{cost_diff_percent:.2f}%"
    )

    print(
        f"Emissions change: "
        f"{emissions_diff_percent:.2f}%"
    )

    
    #plot_soc_comparison(
    #   weekly_optimized_data,
    #   daily_reset_data,
    #)



    