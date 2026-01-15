# Quick Start Guide

This is a simplified guide for getting the Facebook Ads ETL pipeline running quickly. For detailed instructions, see [README.md](README.md).

## For New Team Members

Follow these steps to get the pipeline running on your local machine.

### 1. Prerequisites

Install these first:
- Python 3.11 or higher ([download](https://www.python.org/downloads/))
- Google Cloud SDK / gcloud CLI ([install guide](https://cloud.google.com/sdk/docs/install))
- Git (usually pre-installed on Mac/Linux)

### 2. Get the Code

```bash
# Clone or download this project
cd fb-ads-bigquery-etl
```

### 3. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Mac/Linux
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env and fill in the values
nano .env  # or use your preferred editor
```

You need to fill in:
```bash
FB_TOKEN=your_facebook_access_token
FB_APP_ID=your_facebook_app_id
GCP_PROJECT=your-gcp-project-id
BQ_TABLE=your_dataset.ad_data
```

Ask your team lead for these values if you don't have them.

### 5. Update Account IDs

Edit `main.py` and `backfill.py` and update the `ACCOUNT_IDS` list with your client's Facebook ad account IDs:

```python
ACCOUNT_IDS = [
    "1234567890",  # Replace with actual account IDs
    "9876543210"
]
```

### 6. Authenticate with Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project your-gcp-project-id

# Set application default credentials
gcloud auth application-default login
```

### 7. Test the Pipeline

```bash
# Run a dry run (doesn't insert to BigQuery)
DRY_RUN=true python main.py

# If that works, run for real
python main.py
```

## Common Tasks

### Backfill Historical Data

```bash
# Backfill last 30 days
python backfill.py --start-date 2025-12-01 --end-date 2025-12-31
```

This creates a CSV file like `backfill_2025-12-01_to_2025-12-31.csv`

### Load CSV to BigQuery

```bash
# Load the most recent backfill CSV
python load_csv_to_bq.py

# Or specify a file
python load_csv_to_bq.py backfill_2025-12-01_to_2025-12-31.csv
```

### Deploy to Cloud Functions

```bash
# Edit deploy.sh and update the configuration variables
nano deploy.sh

# Run the deployment script
./deploy.sh
```

## Troubleshooting Quick Fixes

### "FB_TOKEN not found"
- Make sure you created `.env` file from `.env.example`
- Check that `.env` has `FB_TOKEN=...` with a real token

### "Permission denied" errors
- Run: `gcloud auth application-default login`
- Ask your admin to grant you permissions

### "Table not found"
- Make sure the BigQuery table was created (see [docs/GCP_SETUP.md](docs/GCP_SETUP.md))
- Check your `BQ_TABLE` value in `.env`

### "Token is invalid"
- Token may have expired (user tokens expire after 60 days)
- Ask your team lead for a new token
- For production, use a system user token (never expires)

## Important Files

- `main.py` - Main script (fetches yesterday's data)
- `backfill.py` - Historical data script
- `load_csv_to_bq.py` - CSV loader
- `.env` - Your local configuration (DO NOT COMMIT TO GIT)
- `requirements.txt` - Python dependencies
- `schema.json` - BigQuery table schema

## Getting Help

1. Check [README.md](README.md) for detailed documentation
2. Check [docs/GCP_SETUP.md](docs/GCP_SETUP.md) for GCP setup
3. Check [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for deployment help
4. Ask your team lead

## Security Reminder

**NEVER commit these files to Git:**
- `.env` (contains secrets)
- `*.csv` (contains client data)
- `*.log` (may contain sensitive info)
- Service account key files (`.json`)

These are already in `.gitignore`, but be careful when adding files to Git.
