#!/usr/bin/env python3
"""
Load CSV data to BigQuery table

This script loads a CSV file (typically from backfill.py) into a BigQuery table.
It automatically detects the schema and appends data to the existing table.

Usage:
    python load_csv_to_bq.py                    # Loads the most recent backfill_*.csv
    python load_csv_to_bq.py mydata.csv         # Loads a specific CSV file

Features:
- Auto-detects CSV schema
- Appends to existing table (WRITE_APPEND)
- Skips header row automatically
- Shows progress and confirms row counts
- Validates file exists before loading
"""

import os
import sys
import glob
from google.cloud import bigquery
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION - Update these for your client
# =============================================================================

# BigQuery table in format: project.dataset.table
BQ_TABLE = os.getenv("BQ_TABLE", "your-project.your_dataset.ad_data")


# =============================================================================
# BIGQUERY LOADING
# =============================================================================

def load_csv_to_bigquery(csv_file):
    """
    Load CSV file to BigQuery table.

    Args:
        csv_file: Path to CSV file to load

    The function will:
    1. Validate the file exists
    2. Parse the table name into project/dataset/table
    3. Configure BigQuery load job with auto-detection
    4. Load the data and wait for completion
    5. Display row counts
    """
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        sys.exit(1)

    print("=" * 80)
    print("Load CSV to BigQuery")
    print("=" * 80)
    print(f"📁 Source file: {csv_file}")
    print(f"📊 Target table: {BQ_TABLE}")
    print()

    # Initialize BigQuery client
    client = bigquery.Client()

    # Parse table name
    # Expected format: dataset.table (project is inferred from client)
    # OR: project.dataset.table (fully qualified)
    parts = BQ_TABLE.split(".")
    if len(parts) == 2:
        # dataset.table format
        dataset_id, table_id = parts
        full_table_id = f"{client.project}.{dataset_id}.{table_id}"
    elif len(parts) == 3:
        # project.dataset.table format
        full_table_id = BQ_TABLE
    else:
        print(f"❌ Invalid BQ_TABLE format: {BQ_TABLE}")
        print("   Expected format: dataset.table OR project.dataset.table")
        sys.exit(1)

    # Configure load job
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,  # Skip header row
        autodetect=True,      # Auto-detect schema from CSV
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,  # Append to existing table
    )

    # Load the file
    print(f"📤 Loading {csv_file} to {full_table_id}...")
    with open(csv_file, "rb") as f:
        load_job = client.load_table_from_file(
            f,
            full_table_id,
            job_config=job_config
        )

    # Wait for the job to complete
    load_job.result()

    # Get table info to show row counts
    destination_table = client.get_table(full_table_id)

    print("=" * 80)
    print(f"✅ Loaded {load_job.output_rows} rows to {full_table_id}")
    print(f"📊 Table now has {destination_table.num_rows} total rows")
    print("=" * 80)


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    # Check if BQ_TABLE is configured
    if BQ_TABLE == "your-project.your_dataset.ad_data":
        print("❌ Error: BQ_TABLE not configured")
        print("   Please set BQ_TABLE in your .env file")
        print("   Example: BQ_TABLE=my-project.my_dataset.ad_data")
        sys.exit(1)

    # Determine which CSV file to load
    if len(sys.argv) > 1:
        # User specified a file
        csv_file = sys.argv[1]
    else:
        # Find the most recent backfill_*.csv file
        csv_files = sorted(glob.glob("backfill_*.csv"), reverse=True)

        if not csv_files:
            print("❌ No backfill CSV files found")
            print()
            print("Usage:")
            print("  python load_csv_to_bq.py               # Load most recent backfill_*.csv")
            print("  python load_csv_to_bq.py mydata.csv    # Load specific CSV file")
            sys.exit(1)

        csv_file = csv_files[0]

        if len(csv_files) > 1:
            print(f"⚠️ Multiple CSV files found:")
            for f in csv_files[:5]:  # Show first 5
                print(f"   - {f}")
            print(f"Using most recent: {csv_file}")
            print()

    load_csv_to_bigquery(csv_file)
