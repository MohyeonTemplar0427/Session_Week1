import os
import pandas as pd

from dotenv import load_dotenv, find_dotenv

import single_day_analysis as sda
import electricity_maps_data as emd
import gridstatus_data as gsd


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

# Main-------------------------------------------------------------
if __name__ == "__main__":

    date = "2026-08-26"

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

    print(real_market_data.head())
    print(real_market_data.shape)