import pandas as pd

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

def create_load_profile(
        timestamps: pd.DatetimeIndex,
) -> list[float]:

    """Create a simple daily electrical-load profile"""

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


def create_sample_dataframe(
    date: str,
    timezone: str = "America/Los_Angeles",
) -> pd.DataFrame:
    """Create the initial one-day time-series table."""

    timestamps = create_time_index(
        date=date,
        timezone=timezone,
    )

    load_values = create_load_profile(timestamps)

    data = pd.DataFrame({
        "timestamp": timestamps,
        "load_kw": load_values,
    })

    return data



if __name__ == "__main__":
    data = create_sample_dataframe(
        date="2026-08-01",
    )

    print(data.head(10))
    print(data.tail(10))

    print(f"\nNumber of intervals: {len(data)}")
    print(f"Minimum load: {data['load_kw'].min():.2f} kW")
    print(f"Maximum load: {data['load_kw'].max():.2f} kW")

    
