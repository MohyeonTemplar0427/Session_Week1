import pandas as pd
import math
import matplotlib.pyplot as plt

def create_time_index(
        date: str,
        timezone: str = "America/Los_Angeles"
) -> pd.DatetimeIndex:

    """Creating one day of 15-minute timestamps"""

    timestamps = pd.date_range(
        start = date,
        periods = 96,
        freq = "15min",
        tz = timezone,
    )

    return timestamps


def create_pv_profile(
        timestamps: pd.DatetimeIndex,
        maximum_pv_kw: float = 30.0,
) -> list[float]:
    """Create a simplified solar-PV profile"""

    pv_values = []

    for timestamp in timestamps:
        hour = timestamp.hour + timestamp.minute / 60

        if 6 <= hour < 18:
            solar_fraction = math.sin(math.pi * (hour - 6) / 12)
            pv_kw = maximum_pv_kw * solar_fraction
        else:
            pv_kw = 0.0

        pv_values.append(max(pv_kw, 0.0))

    return pv_values


#Create a synthetic average-carbon-intensity profile 
def create_carbon_profile(
        timestamps: pd.DatetimeIndex,
) -> list[float]:
    carbon_intensity_values = []

    for timestamp in timestamps:
        hour = timestamp.hour + timestamp.minute / 60

        if 0 <= hour < 6:
            carbon_intensity = 320.0
        elif 6 <= hour < 12:
            carbon_intensity = 250.0
        elif 12 <= hour < 17:
            carbon_intensity = 120.0
        elif 17 <= hour < 22:
            carbon_intensity = 380.0
        else:
            carbon_intensity = 300.0

        carbon_intensity_values.append(carbon_intensity)

    return carbon_intensity_values 
    


def create_price_profile(
        timestamps: pd.DatetimeIndex,
) -> list[float]:
    price_values = []

    for timestamp in timestamps:
        hour = timestamp.hour + timestamp.minute / 60

        if 0 <= hour < 6:
            price_per_kwh = 0.12
        elif 6 <= hour < 16:
            price_per_kwh = 0.20
        elif 16 <= hour < 21:
            price_per_kwh = 0.38
        else:
            price_per_kwh = 0.16

        price_values.append(price_per_kwh)

    return price_values



def create_load_profile(
        timestamps: pd.DatetimeIndex,
) -> list[float]:

    #Create a simple daily electrical-load profile

    load_values = []

    for timestamp in timestamps:
        hour = timestamp.hour + timestamp.minute / 60
        if 0 <= hour < 6:
            load_kw = 15.0
        elif 6 <= hour < 12:
            load_kw = 25.0
        elif 12 <= hour < 17:
            load_kw = 35.0
        else:
            load_kw = 20.0

        load_values.append(load_kw)

    return load_values

"""Create and validate a one-day microgrid time-series table."""
def create_sample_dataframe(
    date: str,
    timezone: str = "America/Los_Angeles",
) -> pd.DataFrame:
    #Create the initial one-day time-series table.

    timestamps = create_time_index(
        date=date,
        timezone=timezone,
    )

    load_values = create_load_profile(timestamps)
    pv_values = create_pv_profile(timestamps)
    price_values = create_price_profile(timestamps)
    carbon_intensity_values = create_carbon_profile(timestamps)


    data = pd.DataFrame({
        "timestamp": timestamps,
        "load_kw": load_values,
        "pv_kw": pv_values,
        "price_per_kWh": price_values,
        "gCO2/kWh": carbon_intensity_values,
    })

    validate_sample_data(data)

    data["net_load_kw"] = (
        data["load_kw"] - data["pv_kw"]
    )
    
    return data

def validate_sample_data(data: pd.DataFrame) -> None:

    required_columns = {
        "timestamp",
        "load_kw",
        "pv_kw",
        "price_per_kWh",
        "gCO2/kWh",
        }
    
    difference = required_columns - set(data.columns)

    if difference:
        raise ValueError(
            f"Missing DataFrame columns: {difference}"
            )

    ## Check if we have 96 time intervals to fully cover a day
    if len(data) != 96:
        raise ValueError(f"Expected 96 intervals, but received {len(data)}.")
    
    ## Check if there is any missing entry in the DataFrame
    if data.isna().any().any():
        raise ValueError("There is one or more missing values in the DataFrame.")

    ## Check if there is no overlap in time interval
    if not data["timestamp"].is_unique:
        raise ValueError("Not every timestamp is unique.")

    ## Check if timestamp is increasing chronologically 
    if not data["timestamp"].is_monotonic_increasing:
        raise ValueError("Timestamps must increase chronologically.")

    time_differences = data["timestamp"].diff()
    time_differences = time_differences.dropna()

    if not (time_differences == pd.Timedelta(minutes=15)).all():
        raise ValueError(
            "Time intervals must be 15 minutes"
        )
    # Check if each timestamp has timezone
    if data["timestamp"].dt.tz is None:
        raise ValueError(
            "Timestamps must include timezone information"
                         )

    # Check if four numerical inputs don't have negative values.
    numeric_columns = [
        "load_kw",
        "pv_kw",
        "price_per_kWh",
        "gCO2/kWh",
    ]

    if (data[numeric_columns] < 0).any().any():
        raise ValueError(
            "Numerical input values must be nonnegative."
        )

# This function returns data table updated with updated grid parameter histories
def run_rule_based_dispatch(
        data: pd.DataFrame,
) -> pd.DataFrame:

    timestep_hours = 0.25
    discharge_price_threshold = 0.30
    
    battery_capacity_kWh = 20.0
    battery_soc_kWh = 10.0

    min_soc_kWh = 2.0
    max_soc_kWh = 18.0

    max_charge_kw = 5.0
    max_discharge_kw = 5.0

    charge_efficiency = 0.95
    discharge_efficiency = 0.95

    battery_soc_history = []
    battery_charge_history = []
    battery_discharge_history = []
    grid_import_history = []
    grid_export_history = []

    for index, row in data.iterrows():
        net_load_kw = row["net_load_kw"]
        price_per_kWh = row["price_per_kWh"]

        battery_charge_kw = 0.0
        battery_discharge_kw = 0.0
        grid_import_kw = 0.0
        grid_export_kw = 0.0

        if net_load_kw > 0:
            deficit_kw = net_load_kw

            available_energy_kWh = (
                battery_soc_kWh - min_soc_kWh
            )

            soc_limited_discharge_kw = (
                available_energy_kWh * discharge_efficiency / timestep_hours
            )

            battery_discharge_kw = min(
                deficit_kw,
                max_discharge_kw,
                soc_limited_discharge_kw,
            )

            battery_soc_kWh -= (
                battery_discharge_kw
                * timestep_hours
                / discharge_efficiency
            )

            grid_import_kw = (
                deficit_kw - battery_discharge_kw
            )

        elif net_load_kw < 0:
            excess_pv_kw = abs(net_load_kw)

            available_storage_kWh = (
                max_soc_kWh - battery_soc_kWh
            )

            soc_limited_charge_kw = (
                available_storage_kWh
                / charge_efficiency
                / timestep_hours
            )

            battery_charge_kw = min(
                excess_pv_kw,
                max_charge_kw,
                soc_limited_charge_kw
            )

            battery_soc_kWh += (
                battery_charge_kw
                * timestep_hours
                * charge_efficiency
            )

            grid_export_kw = (
                excess_pv_kw - battery_charge_kw
            )

        battery_soc_history.append(battery_soc_kWh)
        battery_charge_history.append(battery_charge_kw)
        battery_discharge_history.append(battery_discharge_kw)
        grid_import_history.append(grid_import_kw)
        grid_export_history.append(grid_export_kw)

    data["battery_soc_kWh"] = battery_soc_history
    data["battery_charge_kw"] = battery_charge_history
    data["battery_discharge_kw"] = battery_discharge_history
    data["grid_import_kw"] = grid_import_history
    data["grid_export_kw"] = grid_export_history
    data["power_balance_error_kw"] = (
        data["pv_kw"]
        + data["battery_discharge_kw"]
        + data["grid_import_kw"]
        - data["load_kw"]
        - data["battery_charge_kw"]
        - data["grid_export_kw"]
    )
    print(f"max error: {data["power_balance_error_kw"].abs().max()}")
    return data


def plot_dispatch_results(
        data: pd.DataFrame,
)-> None:
    figure, axes = plt.subplots(
        3,
        1,
        figsize = (10, 8),
        sharex=True,
    )

    axes[0].plot(
        data["timestamp"],
        data["battery_soc_kWh"],
    )

    axes[0].set_title("Battery State of Charge")
    axes[0].set_ylabel("Energy (kWh)")

    axes[1].plot(
        data["timestamp"],
        data["battery_discharge_kw"],
        label="Discharge"
    )
    axes[1].plot(
            data["timestamp"],
            data["battery_charge_kw"],
            label="Charge"
        )    

    axes[1].set_title("Battery Power")
    axes[1].set_ylabel("Power (kW)")
    axes[1].legend()

    axes[2].plot(
        data["timestamp"],
        data["grid_import_kw"],
        label="Import",
    )
    axes[2].plot(
        data["timestamp"],
        data["grid_export_kw"],
        label="Export",
    )

    axes[2].set_title("Grid Exchange")
    axes[2].set_ylabel("Power (kW)")
    axes[2].set_xlabel("Time")
    axes[2].legend()

    figure.autofmt_xdate()
    figure.tight_layout()

    plt.show()






#Plotting the input signals
def plot_input_profiles(
        data: pd.DataFrame
    ) -> None:
    figure, axes = plt.subplots(
        4,
        1,
        figsize=(9,7.5),
        sharex = True
    )
    axes[0].plot(
        data["timestamp"],
        data["load_kw"],
    )

    axes[1].plot(
        data["timestamp"],
        data["pv_kw"],
    )

    axes[2].plot(
        data["timestamp"],
        data["price_per_kWh"],
    )
    axes[3].plot(
        data["timestamp"],
        data["gCO2/kWh"],
    )
    axes[0].set_title("Electrical Load")
    axes[0].set_ylabel("Load (kW)")

    axes[1].set_title("Solar PV Generation")
    axes[1].set_ylabel("PV (kW)")

    axes[2].set_title("Electricity Price")
    axes[2].set_ylabel("Price ($/kWh)")

    axes[3].set_title("Grid Carbon Intensity")
    axes[3].set_ylabel("gCO2/kWh")
    axes[3].set_xlabel("Time")

    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(
        "results/input_profiles.png",
        dpi = 300,
    )
    plt.show()
    
    

if __name__ == "__main__":
    data = create_sample_dataframe(
        date="2026-08-01",
    )

    output_path = "data/sample_day.csv"
    csv_data = data.to_csv(output_path, index=False)
    print(f"Data saved to: {output_path}.")

    new_data = pd.read_csv(
        output_path, 
        parse_dates = ["timestamp"],
        )
    validate_sample_data(new_data)

    print(new_data.shape)
    print(new_data.dtypes)

    print(data.head(5))
    print(data.tail(5))

    print(f"\nNumber of intervals: {len(data)}")
    print(f"Minimum load: {data['load_kw'].min():.2f} kW")
    print(f"Maximum load: {data['load_kw'].max():.2f} kW")
    print(f"Minimum PV: {data['pv_kw'].min():.2f} kW")
    print(f"Maximum PV: {data['pv_kw'].max():.2f} kW") 
    print(f"Minimum price: ${data['price_per_kWh'].min():.2f}/kWh")
    print(f"Maximum price: ${data['price_per_kWh'].max():.2f}/kWh")
    print(f"Minimum carbon intensity: ${data['gCO2/kWh'].min():.2f}/kWh")
    print(f"Maximum carbon intensity: ${data['gCO2/kWh'].max():.2f}/kWh")

    ##plot_input_profiles(new_data)
    data = run_rule_based_dispatch(data)
    plot_dispatch_results(data)

    
