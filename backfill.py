#!/usr/bin/env python3
"""
Facebook Ads Historical Data Backfill Script

Fetches Facebook Ads data for a historical date range and exports to CSV.
The CSV can then be loaded to BigQuery using load_csv_to_bq.py

Usage:
    python backfill.py --start-date 2025-11-25 --end-date 2025-12-31

Features:
- Fetches data day-by-day for specified date range
- Handles multiple ad accounts
- Deduplicates records automatically
- Exports to CSV for review before loading to BigQuery
- Comprehensive error handling and progress tracking
"""

import os
import sys
import json
import requests
import argparse
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION - Update these for your client
# =============================================================================

# Facebook Access Token (get from .env file)
FB_TOKEN = os.getenv("FB_TOKEN")

# Facebook Ad Account IDs (same as in main.py)
ACCOUNT_IDS = [
    "1406536489957393",  # Replace with your account IDs
    "950565439763291"
]


# =============================================================================
# FACEBOOK API FUNCTIONS
# =============================================================================

def fetch_insights_for_date_range(token, account_id, start_date, end_date):
    """
    Fetch Facebook Ads insights for a specific date range.

    Args:
        token: Facebook access token
        account_id: Facebook ad account ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of raw Facebook API records
    """
    url = f"https://graph.facebook.com/v22.0/act_{account_id}/insights"
    params = {
        "access_token": token,
        "fields": ",".join([
            "campaign_name", "ad_name",
            "impressions", "clicks", "spend",
            "video_continuous_2_sec_watched_actions",
            "video_30_sec_watched_actions",
            "video_avg_time_watched_actions",
            "video_p25_watched_actions",
            "video_p50_watched_actions",
            "video_p75_watched_actions",
            "video_p100_watched_actions",
            "actions",
            "results",
            "date_start", "date_stop"
        ]),
        "level": "ad",
        "breakdowns": json.dumps(["publisher_platform"]),
        "time_increment": "1",
        "date_start": start_date,
        "date_stop": end_date
    }

    all_data = []
    max_retries = 3
    timeout = 30

    while url:
        for attempt in range(max_retries):
            try:
                print(f"    Fetching {start_date} to {end_date} (attempt {attempt + 1}/{max_retries})")
                resp = requests.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                result = resp.json()

                if "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    error_code = result["error"].get("code", "Unknown")
                    print(f"    ❌ Error [{error_code}]: {error_msg}")
                    raise RuntimeError(f"Facebook API Error [{error_code}]: {error_msg}")

                page = result.get("data", [])
                if page:
                    all_data.extend(page)
                    print(f"    ✅ Fetched {len(page)} records")

                url = result.get("paging", {}).get("next")
                params = {}
                break

            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                print(f"    ⚠️ Retry {attempt + 1}/{max_retries}...")
                continue

    return all_data


# =============================================================================
# DATA PROCESSING
# =============================================================================

def extract_metric(rec, key, is_float=False):
    """Extract metric value from nested Facebook API response."""
    val = rec.get(key, 0)
    if isinstance(val, list):
        raw = val[0].get("value", 0) if val else 0
    else:
        raw = val
    return float(raw) if is_float else int(raw)


def flatten_record(rec, action_types):
    """
    Flatten nested Facebook API response into a flat dictionary.
    Matches the schema used by main.py for consistency.
    """
    flat = {
        "campaign_name": rec.get("campaign_name"),
        "ad_name": rec.get("ad_name"),
        "impressions": int(rec.get("impressions", 0)),
        "clicks": int(rec.get("clicks", 0)),
        "spend": float(rec.get("spend", 0)),
        "date_start": rec.get("date_start"),
        "date_stop": rec.get("date_stop"),
        "publisher_platform": rec.get("publisher_platform"),
        "video_continuous_2_sec_watched_actions": extract_metric(rec, "video_continuous_2_sec_watched_actions"),
        "video_30_sec_watched_actions": extract_metric(rec, "video_30_sec_watched_actions"),
        "video_avg_time_watched_actions": extract_metric(rec, "video_avg_time_watched_actions", is_float=True),
        "video_p25_watched_actions": extract_metric(rec, "video_p25_watched_actions"),
        "video_p50_watched_actions": extract_metric(rec, "video_p50_watched_actions"),
        "video_p75_watched_actions": extract_metric(rec, "video_p75_watched_actions"),
        "video_p100_watched_actions": extract_metric(rec, "video_p100_watched_actions"),
    }

    # Initialize all action types with 0
    for at in action_types:
        col = at.replace(".", "_")
        if col not in flat:
            flat[col] = 0

    # Fill in actual action values
    for act in rec.get("actions", []):
        col = act["action_type"].replace(".", "_")
        flat[col] = int(act.get("value", 0))

    return flat


# =============================================================================
# MAIN BACKFILL LOGIC
# =============================================================================

def backfill(start_date, end_date):
    """
    Backfill data from start_date to end_date (inclusive).

    Fetches data day-by-day, deduplicates, and exports to CSV.
    """
    if not FB_TOKEN:
        print("❌ Error: FB_TOKEN not found in .env file")
        print("   Please create a .env file with your Facebook access token")
        sys.exit(1)

    print("=" * 80)
    print("Facebook Ads Historical Data Backfill")
    print("=" * 80)
    print(f"📅 Date range: {start_date} to {end_date}")
    print(f"📊 Accounts: {len(ACCOUNT_IDS)}")
    print()

    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        print("   Expected format: YYYY-MM-DD")
        sys.exit(1)

    if start > end:
        print("❌ Error: start_date must be <= end_date")
        sys.exit(1)

    all_raw = []
    current_date = start

    # Fetch data for each day
    while current_date <= end:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"📊 Fetching {date_str}...")

        for account_id in ACCOUNT_IDS:
            try:
                print(f"  Account {account_id}:")
                raw = fetch_insights_for_date_range(
                    FB_TOKEN,
                    account_id,
                    date_str,
                    date_str
                )
                all_raw.extend(raw)
                print(f"  ✅ Total: {len(raw)} records")
            except Exception as e:
                print(f"  ❌ Failed: {e}")

        current_date += timedelta(days=1)

    if not all_raw:
        print("\n⚠️ No data fetched")
        return

    # Deduplicate raw records
    print(f"\n🔄 Processing {len(all_raw)} records...")
    print(f"🔍 Deduplicating records...")

    # Create unique key for each record
    seen = set()
    deduped_raw = []
    for rec in all_raw:
        # Unique key: campaign_name|ad_name|date_start|publisher_platform
        key = f"{rec.get('campaign_name')}|{rec.get('ad_name')}|{rec.get('date_start')}|{rec.get('publisher_platform')}"
        if key not in seen:
            seen.add(key)
            deduped_raw.append(rec)

    duplicates_removed = len(all_raw) - len(deduped_raw)
    print(f"  Removed {duplicates_removed} duplicate records ({len(deduped_raw)} unique)")

    # Collect all action types for consistent schema
    action_types = set()
    for rec in deduped_raw:
        for act in rec.get("actions", []):
            action_types.add(act["action_type"])

    # Flatten all records
    rows = [flatten_record(rec, action_types) for rec in deduped_raw]

    # Filter to only requested date range
    print(f"📋 Filtering to date range {start_date} to {end_date}...")
    rows_before = len(rows)
    rows = [row for row in rows if start_date <= row["date_start"] <= end_date]
    rows_after = len(rows)
    filtered_count = rows_before - rows_after
    if filtered_count > 0:
        print(f"  Filtered from {rows_before} to {rows_after} rows ({filtered_count} outside range removed)")

    if not rows:
        print("\n⚠️ No data in requested date range")
        return

    # Export to CSV
    csv_filename = f"backfill_{start_date}_to_{end_date}.csv"
    print(f"\n📤 Writing {len(rows)} rows to {csv_filename}...")

    with open(csv_filename, 'w', newline='') as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print("=" * 80)
    print(f"✅ Successfully exported {len(rows)} rows to {csv_filename}")
    print()
    print("Next steps:")
    print(f"  1. Review the CSV file: {csv_filename}")
    print(f"  2. Load to BigQuery: python load_csv_to_bq.py")
    print("=" * 80)


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill Facebook Ads data for a historical date range",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill November 2025
  python backfill.py --start-date 2025-11-01 --end-date 2025-11-30

  # Backfill last 7 days
  python backfill.py --start-date 2025-12-24 --end-date 2025-12-31

  # Backfill single day
  python backfill.py --start-date 2025-12-15 --end-date 2025-12-15
        """
    )
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")

    args = parser.parse_args()
    backfill(args.start_date, args.end_date)
