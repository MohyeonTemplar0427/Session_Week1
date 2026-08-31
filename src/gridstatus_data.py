import gridstatus
import pandas as pd
import time
from pathlib import Path

LOCAL_TIMEZONE = "America/Los_Angeles"

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

CAISO_CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "caiso"
)

def measure_average_query_time(
    location: str = "TH_NP15_GEN-APND",
    number_of_runs: int = 5,
) -> float:

    runtimes = []

    for run in range(number_of_runs):

        start_time = time.perf_counter()

        get_caiso_real_time_prices(
            "2026-08-26",
            location= location,
        )


        end_time = time.perf_counter()

        runtime = (
            end_time
            - start_time
        )

        runtimes.append(runtime)

        print(
            f"Run {run + 1}: "
            f"{runtime:.2f} seconds"
        )

    average_runtime = (
        sum(runtimes)
        / len(runtimes)
    )

    return average_runtime

## Fetch caiso real time price data from gridstatus
def get_caiso_real_time_prices(
        date:str,
        location: str,
) -> pd.DataFrame:

    caiso = gridstatus.CAISO()

    data = caiso.get_lmp(
        date = date,
        market="REAL_TIME_15_MIN",
        locations=[
            location
        ],
    )

    return data

def get_caiso_real_time_prices_range(
        start_date: str,
        number_of_days: int,
        location: str,
        sleep_seconds: float = 1.0
) -> pd.DataFrame:

    caiso = gridstatus.CAISO()

    start_timestamp = pd.Timestamp(
        start_date
    )

    end_timestamp = (
        start_timestamp
        + pd.Timedelta(
            days=number_of_days
        )
    )

    raw_data = caiso.get_lmp(
        date=start_timestamp,
        end=end_timestamp,
        market=gridstatus.Markets.REAL_TIME_15_MIN,
        locations=[
            location
        ],
        sleep = sleep_seconds,
    )

    price_data = (
        caiso_price_to_dataframe(
            raw_data
        )
    )

    validate_price_data(
        price_data,
        expected_rows=(
            number_of_days * 96
        ),
    )

    return price_data


## Convert price data into pandas dataframe
def caiso_price_to_dataframe(
        raw_data: pd.DataFrame,
) -> pd.DataFrame:

    data = raw_data[
        [
            "Interval Start",
            "LMP",
        ]
    ].copy()

    data = data.rename(
        columns={
            "Interval Start": "timestamp",
            "LMP": "price_per_kWh",
        }
    )

    data["timestamp"] = (
        data["timestamp"]
        .dt.tz_convert(
            "America/Los_Angeles"
        )
    )

    data["price_per_kWh"] = (
        data["price_per_kWh"]
        / 1000
    )

    return data


def validate_price_data(
    data: pd.DataFrame,
    expected_rows: int | None = None,
    timestep_minutes: int = 15,
    expected_timezone: str = "America/Los_Angeles",
) -> None:

    required_columns = {
        "timestamp",
        "price_per_kWh",
    }

    missing_columns = (
        required_columns
        - set(data.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    if data.empty:
        raise ValueError(
            "Price data is empty."
        )

    if expected_rows is not None:
        if len(data) != expected_rows:
            raise ValueError(
                f"Expected {expected_rows} rows, "
                f"but received {len(data)}."
            )

    if data.isna().any().any():
        raise ValueError(
            "Price data contains missing values."
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
            "Price data does not have "
            "continuous 15-minute timestamps."
        )

    timezone = (
        data["timestamp"]
        .dt.tz
    )

    if timezone is None:
        raise ValueError(
            "Timestamps are not timezone-aware."
        )

    if str(timezone) != expected_timezone:
        raise ValueError(
            f"Expected timezone {expected_timezone}, "
            f"but received {timezone}."
        )

    print(
        "Price data validation passed."
    )

# Caching function used to improve runtime
def load_or_fetch_caiso_prices(
        date: str,
        location:str,
        force_refresh: bool = False,
) -> pd.DataFrame:

    cache_file = (
        CAISO_CACHE_DIR
        / f"caiso_np15_{date}.csv"
    )

    if (
        cache_file.exists() 
        and not force_refresh
    ):
        print(
            f"Loading cached CAISO prices "
            f"for {date}"
        )

        data = pd.read_csv(
            cache_file
        )

        data["timestamp"] = (
            pd.to_datetime(
                data["timestamp"],
                utc=True,
            )
            .dt.tz_convert(
                "America/Los_Angeles"
            )
        )
        validate_price_data(
            data,
            expected_rows = 96
        )

        return data

    print(
        f"Fetching CAISO prices "
        f"from API for {date}"
    )

    raw_data = (
        get_caiso_real_time_prices(
            date=date,
            location=location,
        )
    )

    data = (
        caiso_price_to_dataframe(
            raw_data
        )
    )

    validate_price_data(
        data,
        expected_rows=96,
    )

    CAISO_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    data.to_csv(
        cache_file,
        index=False
    )

    print(
        f"Saved CAISO cache: "
        f"{cache_file.name}"
    )

    return data



def get_multi_day_caiso_prices(
        start_date: str,
        number_of_days: int,
        location: str
) ->pd.DataFrame:

    daily_dataframes = []

    start_timestamp = pd.Timestamp(
        start_date
    )

    for day_offset in range(
        number_of_days
    ):

        current_date = (
            start_timestamp
            + pd.Timedelta(
                days=day_offset
            )
        )

        date_string = (
            current_date.strftime(
                "%Y-%m-%d"
            )
        )

        price_data = (
            load_or_fetch_caiso_prices(
                date_string,
                location=location,
                force_refresh=False,
            )
        )

        daily_dataframes.append(
            price_data
        )

    multi_day_data = pd.concat(
        daily_dataframes,
        ignore_index = True,
    )

    validate_price_data(
        multi_day_data,
        expected_rows=(
            number_of_days * 96
        ),
    )

    return multi_day_data




##MAIN------------------------------------------------------------------------
if __name__ == "__main__":

    start_time = time.perf_counter()

    test_location = "TH_NP15_GEN-APND"

    raw_price_data = (
        get_caiso_real_time_prices(
            "2026-08-26",
            location=test_location,
        )
    )

    end_time = time.perf_counter()

    price_data = (
        caiso_price_to_dataframe(
            raw_price_data
        )
    )

    validate_price_data(
        price_data,
        expected_rows=96,
    )

    query_runtime = end_time - start_time


    print(price_data.head())
    print(price_data.tail())
    print(price_data.shape)
    print(price_data.dtypes)

    print(
        f"CAISO query runtime: "
        f"{query_runtime:.2f} seconds"
    )
    