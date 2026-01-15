# Facebook Ads to BigQuery ETL Pipeline

A production-ready ETL pipeline that fetches Facebook Ads performance data and loads it into Google BigQuery for analysis and reporting.

## Features

- **Automated Daily Sync**: Fetch yesterday's ad performance data automatically
- **Historical Backfill**: Import historical data for any date range
- **Token Management**: Automatic token refresh via Google Secret Manager
- **Multi-Account Support**: Fetch data from multiple Facebook ad accounts
- **Deduplication**: Automatically removes duplicate records
- **Dynamic Schema**: Adds new fields as Facebook introduces new metrics
- **Production Ready**: Comprehensive error handling, logging, and retry logic
- **Cloud Function Support**: Deploy to Google Cloud Functions for serverless execution

## Table of Contents

- [Quick Start](#quick-start)
- [Setup Instructions](#setup-instructions)
- [Configuration](#configuration)
- [Usage](#usage)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Quick Start

```bash
# 1. Clone or download this project
cd fb-ads-bigquery-etl

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment variables
cp .env.example .env
# Edit .env with your credentials

# 4. Test the connection
python main.py

# 5. Backfill historical data (optional)
python backfill.py --start-date 2025-11-01 --end-date 2025-11-30

# 6. Load CSV to BigQuery (after backfill)
python load_csv_to_bq.py
```

## Setup Instructions

Follow these steps to set up the pipeline for a new client.

### Prerequisites

- Python 3.11 or higher
- Google Cloud Platform account with billing enabled
- Facebook Business Manager account with ad accounts
- Facebook Developer account

### 1. Facebook Setup

#### 1.1 Create a Facebook App

1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Click "My Apps" → "Create App"
3. Select "Business" as the app type
4. Fill in app details:
   - App Name: "MyCompany Ads Analytics"
   - App Contact Email: your email
5. Click "Create App"
6. Note your **App ID** and **App Secret** (Settings → Basic)

#### 1.2 Add Marketing API Permissions

1. In your app, go to "Add Products"
2. Add "Marketing API"
3. Configure the following permissions:
   - `ads_read`
   - `ads_management`
   - `business_management`

#### 1.3 Generate Access Token

**Option A: For Testing/Development (60-day token)**

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from dropdown
3. Click "Generate Access Token"
4. Select permissions: `ads_read`, `ads_management`, `business_management`
5. Copy the short-lived token
6. Exchange it for a long-lived token:

```bash
curl -G "https://graph.facebook.com/v22.0/oauth/access_token" \
  -d "grant_type=fb_exchange_token" \
  -d "client_id=YOUR_APP_ID" \
  -d "client_secret=YOUR_APP_SECRET" \
  -d "fb_exchange_token=YOUR_SHORT_TOKEN"
```

**Option B: For Production (Never-expiring token)**

1. Create a System User in Business Manager:
   - Go to Business Settings → Users → System Users
   - Click "Add" → Name it (e.g., "BigQuery ETL Bot")
   - Assign "Admin" role
2. Generate a system user token:
   - Click on the system user
   - Click "Generate New Token"
   - Select your app
   - Select permissions: `ads_read`, `ads_management`
   - Choose "Never expire"
   - Copy and save the token securely

#### 1.4 Get Ad Account IDs

1. Go to [Facebook Ads Manager](https://adsmanager.facebook.com/)
2. Look at the URL: `https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=1234567890`
3. The number after `act=` is your account ID (e.g., `1234567890`)
4. Collect all account IDs you want to track

### 2. Google Cloud Platform Setup

See [docs/GCP_SETUP.md](docs/GCP_SETUP.md) for detailed GCP setup instructions including:
- Creating a GCP project
- Enabling required APIs
- Setting up BigQuery dataset and table
- Configuring Secret Manager
- Setting up service accounts and permissions

Quick setup checklist:
- [ ] Create GCP project
- [ ] Enable BigQuery API
- [ ] Enable Secret Manager API
- [ ] Create BigQuery dataset
- [ ] Create BigQuery table with schema
- [ ] Store secrets in Secret Manager
- [ ] Set up service account (for Cloud Functions)

### 3. Local Setup

#### 3.1 Install Python Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 3.2 Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env and fill in your values
nano .env  # or use your preferred editor
```

Required variables in `.env`:
```bash
FB_TOKEN=your_facebook_access_token
FB_APP_ID=your_facebook_app_id
GCP_PROJECT=your-gcp-project-id
BQ_TABLE=your_dataset.ad_data
```

#### 3.3 Update Account IDs in Scripts

Edit `main.py` and `backfill.py` and update the `ACCOUNT_IDS` list:

```python
ACCOUNT_IDS = [
    "1234567890",  # Account 1
    "9876543210"   # Account 2
]
```

#### 3.4 Authenticate with Google Cloud

```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set your project
gcloud config set project your-gcp-project-id

# Set application default credentials (for local development)
gcloud auth application-default login
```

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `FB_TOKEN` | Yes (local) | Facebook access token | `EAAbc123...` |
| `FB_APP_ID` | No (local) | Facebook app ID | `123456789` |
| `GCP_PROJECT` | Yes | Google Cloud project ID | `my-project-123` |
| `BQ_TABLE` | Yes | BigQuery table (dataset.table) | `analytics.ad_data` |
| `DRY_RUN` | No | Set to `true` to skip BigQuery insert | `false` |

### Account Configuration

Update the `ACCOUNT_IDS` list in `main.py` and `backfill.py`:

```python
ACCOUNT_IDS = [
    "1234567890",  # Your ad account IDs
]
```

### BigQuery Schema

The default schema is in [schema.json](schema.json). The pipeline automatically adds new fields as Facebook introduces new metrics, but you should start with this schema when creating the table.

## Usage

### Daily Data Sync (Local Testing)

Fetch yesterday's data and load to BigQuery:

```bash
python main.py
```

This will:
1. Get a valid Facebook token (refreshes if needed)
2. Fetch yesterday's ad data for all accounts
3. Deduplicate records
4. Save to `/tmp/ads_output.csv` for review
5. Insert data to BigQuery

### Historical Data Backfill

Fetch historical data for a date range:

```bash
# Backfill a specific date range
python backfill.py --start-date 2025-11-01 --end-date 2025-11-30

# Backfill a single day
python backfill.py --start-date 2025-12-15 --end-date 2025-12-15
```

This creates a CSV file: `backfill_2025-11-01_to_2025-11-30.csv`

### Load CSV to BigQuery

After running a backfill, load the CSV to BigQuery:

```bash
# Load the most recent backfill CSV
python load_csv_to_bq.py

# Load a specific CSV file
python load_csv_to_bq.py backfill_2025-11-01_to_2025-11-30.csv
```

### Dry Run Mode

Test without inserting to BigQuery:

```bash
DRY_RUN=true python main.py
```

## Deployment

### Deploy to Google Cloud Functions

#### 1. Create Deployment Configuration

Create `cloudbuild.yaml`:

```yaml
steps:
- id: Deploy-Function
  name: gcr.io/cloud-builders/gcloud
  entrypoint: bash
  args:
    - -c
    - |
      gcloud functions deploy fetchFbAdsToBigQuery \
        --gen2 \
        --region=us-central1 \
        --runtime=python313 \
        --entry-point=main \
        --trigger-topic=fb-ads-topic \
        --set-env-vars=GCP_PROJECT=YOUR_PROJECT,BQ_TABLE=YOUR_DATASET.ad_data \
        --timeout=300 \
        --memory=256MB
```

#### 2. Create Pub/Sub Topic

```bash
gcloud pubsub topics create fb-ads-topic --project=YOUR_PROJECT
```

#### 3. Deploy Function

```bash
gcloud functions deploy fetchFbAdsToBigQuery \
  --gen2 \
  --region=us-central1 \
  --runtime=python313 \
  --entry-point=main \
  --trigger-topic=fb-ads-topic \
  --set-env-vars=GCP_PROJECT=YOUR_PROJECT,BQ_TABLE=YOUR_DATASET.ad_data \
  --timeout=300 \
  --memory=256MB
```

#### 4. Set Up Scheduler

Create a Cloud Scheduler job to trigger daily at 9 AM UTC:

```bash
gcloud scheduler jobs create pubsub daily-fb-ads-sync \
  --schedule="0 9 * * *" \
  --topic=fb-ads-topic \
  --message-body="trigger" \
  --location=us-central1
```

## Troubleshooting

### Token Issues

**Problem**: "Token is invalid" error

**Solution**:
1. Check token expiration with Facebook's Debug Tool: https://developers.facebook.com/tools/debug/accesstoken/
2. Generate a new token following the Facebook Setup steps
3. For production, use a system user token that never expires

**Problem**: "Permission denied" for ad account

**Solution**:
1. Verify the token has access to the ad account in Business Manager
2. Check that required permissions (`ads_read`) are granted
3. Ensure the token is for a user/system user with access to the ad accounts

### BigQuery Issues

**Problem**: "Table not found" error

**Solution**:
1. Create the table using the schema.json file (see GCP Setup guide)
2. Verify the BQ_TABLE format is correct: `project.dataset.table` or `dataset.table`

**Problem**: "Permission denied" on BigQuery

**Solution**:
1. Run `gcloud auth application-default login` for local development
2. For Cloud Functions, ensure the service account has BigQuery Data Editor role

### Data Issues

**Problem**: No data returned from Facebook API

**Solution**:
1. Check that ads were actually running on the date you're querying
2. Verify account IDs are correct (no `act_` prefix in the ACCOUNT_IDS list)
3. Check for API errors in the console output

**Problem**: Duplicate records in BigQuery

**Solution**:
- The pipeline deduplicates before inserting, but if you manually load data multiple times, you may get duplicates
- Run this query to deduplicate:
```sql
CREATE OR REPLACE TABLE `dataset.ad_data` AS
SELECT DISTINCT * FROM `dataset.ad_data`
```

## Project Structure

```
fb-ads-bigquery-etl/
├── main.py                 # Main ETL script (daily sync)
├── backfill.py            # Historical data backfill script
├── load_csv_to_bq.py      # CSV to BigQuery loader
├── requirements.txt       # Python dependencies
├── schema.json           # BigQuery table schema
├── .env.example          # Environment variables template
├── .gitignore           # Git ignore rules
├── README.md            # This file
└── docs/
    ├── GCP_SETUP.md     # Detailed GCP setup instructions
    └── DEPLOYMENT.md    # Cloud deployment guide
```

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review the detailed setup guides in the `docs/` folder
3. Check Facebook's [Marketing API documentation](https://developers.facebook.com/docs/marketing-apis)
4. Check Google's [BigQuery documentation](https://cloud.google.com/bigquery/docs)

## License

This project is provided as-is for internal use. Modify as needed for your client requirements.
