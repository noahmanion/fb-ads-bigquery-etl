# Facebook Ads to BigQuery ETL Pipeline

Fetches Facebook Ads performance data daily and loads it into BigQuery. Runs as a Google Cloud Function triggered by Pub/Sub on a daily schedule.

## Architecture

- **Cloud Function** (`fetchFbAdsToBigQuery`): Fetches yesterday's ad data from the Facebook Marketing API and inserts it into BigQuery
- **Cloud Scheduler**: Triggers the function daily at 9 AM UTC via Pub/Sub
- **Secret Manager**: Stores Facebook credentials (app ID, app secret, access token)
- **BigQuery**: Stores all ad performance data in `chi-fire.ad_data.data`
- **Cloud Monitoring**: Sends email alerts on function failure

## Current Configuration

| Setting | Value |
|---------|-------|
| GCP Project | `chi-fire` |
| Region | `us-central1` |
| Function Name | `fetchFbAdsToBigQuery` |
| Pub/Sub Topic | `fb-ads-topic` |
| BigQuery Table | `chi-fire.ad_data.data` |
| Facebook App | CC Ad Data ETL (`9990717067630623`) |
| Ad Account | `237000887` |
| Service Account | `837056475076-compute@developer.gserviceaccount.com` |

## Prerequisites

- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed
- Python 3.11+
- Access to the `chi-fire` GCP project
- Access to Facebook Business Manager with the CC Ad Data ETL app

---

## Setting Up the gcloud CLI

### Install

Follow the instructions at https://cloud.google.com/sdk/docs/install for your OS.

### Log In and Set Project

```bash
# Log in to Google Cloud (opens a browser)
gcloud auth login

# Set the active project
gcloud config set project chi-fire

# Verify you're in the right project
gcloud config get-value project
# Should output: chi-fire

# Set application default credentials (needed for local Python scripts)
gcloud auth application-default login
```

---

## Deploying the Cloud Function

### Quick Deploy

```bash
./deploy.sh
```

This handles everything: sets the project, ensures the Pub/Sub topic exists, and deploys the function.

### Manual Deploy

```bash
gcloud config set project chi-fire

gcloud functions deploy fetchFbAdsToBigQuery \
  --gen2 \
  --region=us-central1 \
  --runtime=python313 \
  --entry-point=main \
  --source=. \
  --trigger-topic=fb-ads-topic \
  --set-env-vars=GCP_PROJECT=chi-fire,BQ_TABLE=chi-fire.ad_data.data \
  --timeout=540 \
  --memory=512MB \
  --max-instances=1 \
  --service-account=837056475076-compute@developer.gserviceaccount.com
```

### Test the Deployment

```bash
# Trigger the function
gcloud pubsub topics publish fb-ads-topic --message='test' --project=chi-fire

# Wait ~30 seconds, then check logs
gcloud functions logs read fetchFbAdsToBigQuery --region=us-central1 --limit=20 --project=chi-fire
```

A successful run shows data being fetched and inserted into BigQuery with no `RuntimeError` in the logs.

---

## Managing Secrets

The function reads credentials from Google Secret Manager. No secrets are passed as environment variables.

### View Current Secrets

```bash
# List all secrets
gcloud secrets list --project=chi-fire

# View a secret value
gcloud secrets versions access latest --secret=fb-app-id --project=chi-fire
gcloud secrets versions access latest --secret=fb-app-secret --project=chi-fire
gcloud secrets versions access latest --secret=fb-marketing-token --project=chi-fire
```

### Update the Facebook Token

This is the most common operation. When the token expires or needs replacement:

```bash
echo -n "YOUR_NEW_TOKEN" | gcloud secrets versions add fb-marketing-token --data-file=- --project=chi-fire
```

Then test the function:

```bash
gcloud pubsub topics publish fb-ads-topic --message='test' --project=chi-fire
```

### Update the App ID

```bash
echo -n "YOUR_APP_ID" | gcloud secrets versions add fb-app-id --data-file=- --project=chi-fire
```

### Update the App Secret

```bash
echo -n "YOUR_APP_SECRET" | gcloud secrets versions add fb-app-secret --data-file=- --project=chi-fire
```

### Generating a New Facebook Token

1. Go to **Business Manager** > **Business Settings** > **System Users**
2. Select the system user (or create one)
3. Click **Generate New Token**
4. Select the **CC Ad Data ETL** app
5. Grant the **`ads_read`** permission
6. Copy the token and update Secret Manager (see above)

### Secret Manager Permissions

The function's service account needs these IAM roles on the secrets:

```bash
SA="837056475076-compute@developer.gserviceaccount.com"

# Read access for all secrets
for SECRET in fb-app-id fb-app-secret fb-marketing-token fb-marketing-token-metadata; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor" \
    --project=chi-fire
done

# Write access for token secrets (so the function can refresh tokens)
for SECRET in fb-marketing-token fb-marketing-token-metadata; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretVersionAdder" \
    --project=chi-fire
done
```

---

## Backfilling Historical Data

Use `backfill.py` to fetch historical data and `load_csv_to_bq.py` to load it into BigQuery.

### 1. Set Up Local Environment

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure `.env`

Make sure `.env` has the correct values:

```bash
FB_TOKEN=your_facebook_access_token
FB_APP_ID=9990717067630623
GCP_PROJECT=chi-fire
BQ_TABLE=chi-fire.ad_data.data
DRY_RUN=false
```

The `FB_TOKEN` here is used directly by `backfill.py` (it does not go through Secret Manager). You can get the current token from Secret Manager:

```bash
gcloud secrets versions access latest --secret=fb-marketing-token --project=chi-fire
```

### 3. Run the Backfill

```bash
# Backfill a date range
python backfill.py --start-date 2025-11-01 --end-date 2025-11-30

# Backfill a single day
python backfill.py --start-date 2025-12-15 --end-date 2025-12-15
```

This creates a CSV file (e.g. `backfill_2025-11-01_to_2025-11-30.csv`) for review.

### 4. Load the CSV to BigQuery

```bash
# Load the most recent backfill CSV
python load_csv_to_bq.py

# Load a specific CSV
python load_csv_to_bq.py backfill_2025-11-01_to_2025-11-30.csv
```

---

## Monitoring and Alerts

A Cloud Monitoring alert policy sends emails to `noah@softpath.co` and `iryna@geletkaplus.com` when the function fails.

### View Logs

```bash
# Recent logs
gcloud functions logs read fetchFbAdsToBigQuery --region=us-central1 --limit=50 --project=chi-fire

# Logs from Cloud Console
# https://console.cloud.google.com/logs/query;query=resource.type%3D%22cloud_run_revision%22%20resource.labels.service_name%3D%22fetchfbadstobigquery%22;?project=chi-fire
```

### Manually Trigger the Function

```bash
gcloud pubsub topics publish fb-ads-topic --message='test' --project=chi-fire
```

---

## Troubleshooting

### "API access deactivated"

The Facebook developer account needs re-registration. Go to [developers.facebook.com](https://developers.facebook.com) and complete any required verification steps.

### "The App_id in the input_token did not match the Viewing App"

The token was generated under a different Facebook app than what's in Secret Manager. Generate a new token under the correct app (CC Ad Data ETL) or update the `fb-app-id` secret to match the app the token was generated under.

### "Invalid OAuth access token signature"

The app secret in Secret Manager doesn't match the app ID. Verify the app secret at developers.facebook.com > Your App > Settings > Basic, then update:

```bash
echo -n "CORRECT_SECRET" | gcloud secrets versions add fb-app-secret --data-file=- --project=chi-fire
```

### "Permission denied" on Secret Manager

The service account needs `secretmanager.secretAccessor` role. See the [Secret Manager Permissions](#secret-manager-permissions) section.

### No data returned

1. Verify ads were running on the queried date
2. Check that the ad account ID (`237000887`) is correct
3. Ensure the token has `ads_read` permission for the ad account

### Duplicate records in BigQuery

The pipeline deduplicates before inserting, but manual loads can create duplicates. Deduplicate with:

```sql
CREATE OR REPLACE TABLE `chi-fire.ad_data.data` AS
SELECT DISTINCT * FROM `chi-fire.ad_data.data`
```

---

## Project Structure

```
fb-ads-to-bq/
  main.py               # Cloud Function entry point (daily sync)
  backfill.py           # Historical data backfill (local)
  load_csv_to_bq.py     # CSV to BigQuery loader (local)
  deploy.sh             # Deployment script
  requirements.txt      # Python dependencies
  schema.json           # BigQuery table schema
  .env                  # Local environment variables (gitignored)
  .env.example          # Environment variables template
  secrets.txt           # Token reference notes (gitignored)
```
