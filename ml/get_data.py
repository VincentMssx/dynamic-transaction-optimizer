
import os
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv

# Load environment variables from .env file (for the key path)
load_dotenv()

def fetch_gas_data():
    """
    Connects to Google BigQuery and fetches two years of hourly
    base_fee_per_gas data from the Ethereum blockchain.
    """
    print("Connecting to Google BigQuery...")
    client = bigquery.Client()

    # --- THIS IS THE CORRECTED QUERY ---
    # The only change is from `INTERVAL 2 YEAR` to `INTERVAL (2 * 365) DAY`
    query = """
        SELECT
            TIMESTAMP_TRUNC(timestamp, HOUR) AS hour,
            AVG(base_fee_per_gas) / 1e9 AS avg_gas_in_gwei
        FROM
            `bigquery-public-data.crypto_ethereum.blocks`
        WHERE
            timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL (2 * 365) DAY)
        GROUP BY
            hour
        HAVING
            avg_gas_in_gwei IS NOT NULL
        ORDER BY
            hour;
    """

    print("Executing query... This may take a minute or two.")
    # Execute the query and load the result into a pandas DataFrame
    df = client.query(query).to_dataframe()

    # Create the data directory if it doesn't exist
    if not os.path.exists('../data'):
        os.makedirs('../data')
    
    # Define the output file path
    output_path = '../data/gas_data.csv'
    
    print(f"Query complete. Found {len(df)} hourly records.")
    print(f"Saving data to {output_path}...")
    
    # Save the DataFrame to a CSV file
    df.to_csv(output_path, index=False)

    print("Data successfully downloaded and saved.")
    print("\n--- Data Preview ---")
    print(df.head())
    print("--------------------")

if __name__ == "__main__":
    fetch_gas_data()