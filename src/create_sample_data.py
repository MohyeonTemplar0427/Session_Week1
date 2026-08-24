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

def create_sample_dataframe(
    date: str,
    timezone: str = "America/Los_Angeles",
) -> pd.DataFrame:
    """Create the initial one-day time-series table."""

    timestamps = create_time_index(
        date=date,
        timezone=timezone,
    )

    data = pd.DataFrame({
        "timestamp": timestamps,
    })

    return data

if __name__ == "__main__":
    data = create_sample_dataframe("2026-08-01",)

    print(data.head())
    print(data.tail())
    print(f"Number of intervals: {len(data)}")


    
