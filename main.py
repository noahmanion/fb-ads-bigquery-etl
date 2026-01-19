#!/usr/bin/env python3
"""
Facebook Ads to BigQuery ETL Pipeline

This script fetches Facebook Ads insights data and loads it into BigQuery.
It can be run locally or deployed as a Google Cloud Function.

Features:
- Automatic token refresh and management via Secret Manager
- Fetches yesterday's ad performance data from Facebook Marketing API
- Deduplicates records before inserting
- Dynamic schema management (adds new fields automatically)
- Supports multiple ad accounts
- Comprehensive error handling and logging
"""

import os
import requests
import json
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.cloud import bigquery, secretmanager

# Load environment variables from .env file
load_dotenv()

# Lazy-initialized clients (to avoid gRPC timeout warnings when not used)
_bq_client = None
_sm_client = None


def get_bq_client():
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client()
    return _bq_client


def get_sm_client():
    global _sm_client
    if _sm_client is None:
        _sm_client = secretmanager.SecretManagerServiceClient()
    return _sm_client

# =============================================================================
# CONFIGURATION - Update these for your client
# =============================================================================

# Facebook Ad Account IDs (get from Facebook Ads Manager URL)
# Example URL: https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=1234567890
# The number after 'act=' is your account ID
ACCOUNT_IDS = [
    "237000887"
]

# GCP Configuration
GCP_PROJECT = os.getenv("GCP_PROJECT", "chi-fire")

# Secret Manager secret names
TOKEN_SECRET_NAME = "fb-marketing-token"
TOKEN_METADATA_SECRET_NAME = "fb-marketing-token-metadata"
FB_APP_ID_SECRET = "fb-app-id"
FB_APP_SECRET_SECRET = "fb-app-secret"


# =============================================================================
# SECRET MANAGER FUNCTIONS
# =============================================================================

def get_secret(secret_id: str) -> str:
    """Fetch a secret from Secret Manager."""
    name = f"projects/{GCP_PROJECT}/secrets/{secret_id}/versions/latest"
    response = get_sm_client().access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def set_secret(secret_id: str, value: str):
    """
    Add a new version to an existing secret.
    Note: The secret must already exist in Secret Manager.
    """
    parent = f"projects/{GCP_PROJECT}/secrets/{secret_id}"
    get_sm_client().add_secret_version(
        request={
            "parent": parent,
            "payload": {"data": value.encode("UTF-8")}
        }
    )
    print(f"✅ Updated secret: {secret_id}")


# =============================================================================
# TOKEN MANAGEMENT
# =============================================================================

def debug_token(token: str, app_id: str, app_secret: str) -> dict:
    """
    Check token validity and expiration via Facebook's debug endpoint.
    Returns dict with: is_valid, expires_at (timestamp), scopes, error (if any)
    """
    url = "https://graph.facebook.com/v22.0/debug_token"
    params = {
        "input_token": token,
        "access_token": f"{app_id}|{app_secret}"
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {})

        return {
            "is_valid": data.get("is_valid", False),
            "expires_at": data.get("expires_at", 0),  # 0 means never expires
            "scopes": data.get("scopes", []),
            "app_id": data.get("app_id"),
            "user_id": data.get("user_id"),
            "type": data.get("type"),
            "error": data.get("error")
        }
    except Exception as e:
        return {
            "is_valid": False,
            "expires_at": 0,
            "error": str(e)
        }


def refresh_long_lived_token(current_token: str, app_id: str, app_secret: str) -> tuple[str, int]:
    """
    Refresh an existing long-lived token.

    Important: Facebook only allows refreshing tokens that are at least 24 hours old
    and not yet expired. The new token will be valid for 60 days from refresh.

    Returns: (new_token, expires_at_timestamp)
    """
    url = "https://graph.facebook.com/v22.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": current_token
    }

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    new_token = data["access_token"]
    expires_in = data.get("expires_in", 60 * 24 * 60 * 60)
    expires_at = int(datetime.now().timestamp()) + expires_in

    return new_token, expires_at


def get_valid_token() -> str:
    """
    Main token management function. Gets token from Secret Manager,
    checks validity, refreshes if needed, and returns a working token.
    """
    # First check for env var override (useful for local dev/testing)
    env_token = os.getenv("FB_TOKEN")
    if env_token:
        print("📌 Using FB_TOKEN from environment variable")
        return env_token

    # Get app credentials
    try:
        app_id = get_secret(FB_APP_ID_SECRET)
        app_secret = get_secret(FB_APP_SECRET_SECRET)
    except Exception as e:
        raise RuntimeError(
            f"Failed to get Facebook app credentials from Secret Manager: {e}\n"
            f"Make sure secrets '{FB_APP_ID_SECRET}' and '{FB_APP_SECRET_SECRET}' exist."
        )

    # Get current token
    try:
        current_token = get_secret(TOKEN_SECRET_NAME)
    except Exception as e:
        raise RuntimeError(
            f"Failed to get Facebook token from Secret Manager: {e}\n"
            f"Make sure secret '{TOKEN_SECRET_NAME}' exists with a valid token."
        )

    # Check token status
    token_info = debug_token(current_token, app_id, app_secret)

    if not token_info["is_valid"]:
        error_msg = token_info.get("error", "Unknown error")
        raise RuntimeError(
            f"❌ Facebook token is invalid: {error_msg}\n"
            "You need to manually generate a new token and update Secret Manager."
        )

    expires_at = token_info["expires_at"]

    # expires_at = 0 means never expires (system user token)
    if expires_at == 0:
        print("✅ Token never expires (system user token)")
        return current_token

    expires_dt = datetime.fromtimestamp(expires_at)
    now = datetime.now()
    days_until_expiry = (expires_dt - now).days

    print(f"📅 Token expires: {expires_dt.isoformat()} ({days_until_expiry} days remaining)")

    # Refresh if within 7 days of expiration
    if days_until_expiry <= 7:
        print(f"⚠️ Token expiring soon, attempting refresh...")

        try:
            new_token, new_expires_at = refresh_long_lived_token(
                current_token, app_id, app_secret
            )

            # Verify the new token works
            new_info = debug_token(new_token, app_id, app_secret)
            if not new_info["is_valid"]:
                raise RuntimeError("Refreshed token is not valid")

            # Store the new token
            set_secret(TOKEN_SECRET_NAME, new_token)

            # Store metadata (optional but useful for debugging)
            metadata = json.dumps({
                "refreshed_at": datetime.now().isoformat(),
                "expires_at": new_expires_at,
                "expires_at_human": datetime.fromtimestamp(new_expires_at).isoformat()
            })
            try:
                set_secret(TOKEN_METADATA_SECRET_NAME, metadata)
            except Exception:
                pass  # Metadata is optional

            new_days = (datetime.fromtimestamp(new_expires_at) - now).days
            print(f"✅ Token refreshed successfully! New expiration: {new_days} days")

            return new_token

        except Exception as e:
            # If refresh fails but token is still valid, use it anyway
            if days_until_expiry > 0:
                print(f"⚠️ Token refresh failed ({e}), but current token still valid for {days_until_expiry} days")
                return current_token
            else:
                raise RuntimeError(
                    f"❌ Token refresh failed and current token is expired: {e}\n"
                    "You need to manually generate a new token."
                )

    return current_token


# =============================================================================
# FACEBOOK API FUNCTIONS
# =============================================================================

def fetch_all_insights(token, account_id):
    """
    Fetch Facebook Ads insights for yesterday, broken down by publisher platform.

    This fetches ad-level data including:
    - Basic metrics (impressions, clicks, spend)
    - Video metrics (watch times, completion rates)
    - Conversion actions (leads, landing page views, etc.)
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
        "date_preset": "yesterday"
    }
    all_data = []
    max_retries = 3
    timeout = 30

    while url:
        for attempt in range(max_retries):
            try:
                print(f"  Fetching data from account {account_id} (attempt {attempt + 1}/{max_retries})")
                resp = requests.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                result = resp.json()

                if "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    error_type = result["error"].get("type", "Unknown")
                    error_code = result["error"].get("code", "Unknown")
                    print(f"❌ Facebook API Error [{error_code}] ({error_type}): {error_msg}")
                    if error_code in [190, 104]:
                        print(f"⚠️ TOKEN ERROR: Token may be expired or invalid for account {account_id}")
                    raise RuntimeError(f"Facebook API Error [{error_code}]: {error_msg}")

                page = result.get("data", [])
                if not page:
                    print("  No data returned from API")
                    break

                all_data.extend(page)
                print(f"  ✅ Successfully fetched {len(page)} records")

                url = result.get("paging", {}).get("next")
                params = {}
                break

            except requests.Timeout:
                if attempt == max_retries - 1:
                    print(f"❌ Request timed out after {max_retries} attempts")
                    raise
                print(f"⚠️ Request timed out, retrying...")
                continue

            except requests.RequestException as e:
                print(f"❌ Request failed: {str(e)}")
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    if e.response.status_code == 401:
                        print(f"⚠️ TOKEN ERROR: 401 Unauthorized")
                    elif e.response.status_code == 403:
                        print(f"⚠️ PERMISSION ERROR: 403 Forbidden")
                raise

    return all_data


# =============================================================================
# DATA PROCESSING
# =============================================================================

def extract_metric(rec, key, is_float=False):
    """Extract metric value from nested Facebook API response."""
    val = rec.get(key, 0)
    if isinstance(val, list):
        raw = val[0].get("value", 0)
    else:
        raw = val
    return float(raw) if is_float else int(raw)


def flatten_record(rec, action_types):
    """
    Flatten nested Facebook API response into a flat dictionary.
    Extracts all metrics and actions into column-friendly format.
    """
    flat = {
        "campaign_name": rec.get("campaign_name"),
        "ad_name": rec.get("ad_name"),
        "publisher_platform": rec.get("publisher_platform"),
        "impressions": int(rec.get("impressions", 0)),
        "clicks": int(rec.get("clicks", 0)),
        "spend": float(rec.get("spend", 0)),
        "date_start": rec.get("date_start"),
        "date_stop": rec.get("date_stop"),
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
# BIGQUERY FUNCTIONS
# =============================================================================

def ensure_bq_schema(table_id: str, rows: list[dict]):
    """
    Dynamically update BigQuery table schema to include any new fields from the data.
    This allows the schema to evolve as Facebook adds new metrics.
    """
    client = bigquery.Client()
    table = client.get_table(table_id)
    existing = {f.name for f in table.schema}

    all_keys = set().union(*(r.keys() for r in rows))

    # Define expected static fields
    static_keys = {
        "campaign_name", "ad_name", "publisher_platform", "date_start", "date_stop",
        "impressions", "clicks", "spend", "video_continuous_2_sec_watched_actions",
        "video_30_sec_watched_actions", "video_avg_time_watched_actions",
        "video_p25_watched_actions", "video_p50_watched_actions",
        "video_p75_watched_actions", "video_p100_watched_actions"
    }

    missing_static = static_keys - existing
    new_fields = (all_keys - existing) - static_keys
    to_add = sorted(missing_static | new_fields)

    if not to_add:
        return

    new_schema = list(table.schema)
    for name in to_add:
        # String fields
        if name in ["ad_name", "campaign_name", "publisher_platform", "date_start", "date_stop"]:
            field_type = "STRING"
        else:
            field_type = "FLOAT"
        new_schema.append(bigquery.SchemaField(name, field_type, mode="NULLABLE"))

    table.schema = new_schema
    client.update_table(table, ["schema"])
    print(f"✅ Added new fields to {table_id}: {to_add}")


def insert_to_bq(rows, table_id):
    """Insert rows into BigQuery table."""
    errors = get_bq_client().insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert errors: {errors}")
    else:
        print(f"✅ Inserted {len(rows)} rows into {table_id}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main(event=None, context=None):
    """
    Main entry point for the ETL pipeline.

    Can be run locally or as a Cloud Function.
    Set DRY_RUN=true to test without inserting to BigQuery.
    """
    table_id = os.getenv("BQ_TABLE", "your-project.your_dataset.ad_data")
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    print("=" * 60)
    print("Facebook Ads to BigQuery ETL Pipeline")
    print("=" * 60)

    # Get valid token (handles refresh automatically)
    token = get_valid_token()

    account_ids = ACCOUNT_IDS
    all_raw = []
    failed_accounts = []

    # Fetch data from all accounts
    for account_id in account_ids:
        try:
            print(f"\n📊 Fetching insights for account {account_id}...")
            raw = fetch_all_insights(token, account_id)
            all_raw.extend(raw)
            print(f"✅ Successfully processed account {account_id}")
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to process account {account_id}: {error_msg}")
            failed_accounts.append((account_id, error_msg))
            continue

    if failed_accounts:
        print(f"\n⚠️ WARNING: {len(failed_accounts)} account(s) failed to process:")
        for account_id, error in failed_accounts:
            print(f"   - {account_id}: {error}")

    if not all_raw:
        print("\n⚠️ No data found for any account")
        if failed_accounts:
            print(f"\n⛔ CRITICAL: All {len(account_ids)} account(s) failed to process.")
            raise RuntimeError(f"Failed to fetch data from all accounts: {failed_accounts}")
        return {"status": "success", "message": "No data found", "rows_processed": 0}

    # Deduplicate raw records (Facebook API may return overlapping data)
    print(f"\n🔍 Deduplicating {len(all_raw)} records...")
    seen = set()
    deduped_raw = []
    for rec in all_raw:
        # Unique key: campaign_name|ad_name|date_start|publisher_platform
        key = f"{rec.get('campaign_name')}|{rec.get('ad_name')}|{rec.get('date_start')}|{rec.get('publisher_platform')}"
        if key not in seen:
            seen.add(key)
            deduped_raw.append(rec)

    duplicates_removed = len(all_raw) - len(deduped_raw)
    if duplicates_removed > 0:
        print(f"  Removed {duplicates_removed} duplicate records ({len(deduped_raw)} unique)")
    else:
        print(f"  No duplicates found ({len(deduped_raw)} unique records)")

    # Collect all action types for schema
    action_types = {a["action_type"]
                    for r in deduped_raw
                    for a in r.get("actions", [])}

    # Flatten all records
    rows = []
    for r in deduped_raw:
        flat = flatten_record(r, action_types)
        rows.append(flat)

    # Save to CSV for review
    if rows:
        csv_path = "/tmp/ads_output.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Saved {len(rows)} rows to {csv_path}")

    # Insert to BigQuery
    if dry_run:
        print("\n🧪 DRY RUN MODE: Skipping BigQuery insertion")
        print(f"Would have inserted {len(rows)} rows to {table_id}")
    elif rows:
        ensure_bq_schema(table_id, rows)
        insert_to_bq(rows, table_id)

    print("\n" + "=" * 60)
    print(f"✅ Pipeline completed successfully!")
    print(f"Processed {len(rows)} rows")
    print("=" * 60)

    return {"status": "success", "message": f"Processed {len(rows)} rows", "rows_processed": len(rows)}


if __name__ == "__main__":
    main()
