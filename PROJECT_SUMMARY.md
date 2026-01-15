# Facebook Ads to BigQuery ETL Pipeline - Project Summary

## Overview

This is a production-ready ETL (Extract, Transform, Load) pipeline that automatically fetches Facebook Ads performance data and loads it into Google BigQuery for analysis and reporting.

## What It Does

1. **Connects to Facebook Marketing API** to fetch ad performance metrics
2. **Processes and cleans the data** (deduplicates, flattens nested fields)
3. **Loads data to BigQuery** for SQL analysis and reporting
4. **Runs automatically** on a schedule (daily, hourly, etc.) via Cloud Functions
5. **Manages tokens** automatically with auto-refresh capability

## Key Features

- **Multi-account support** - fetch data from multiple Facebook ad accounts
- **Historical backfill** - import past data for any date range
- **Automatic schema updates** - adds new fields as Facebook introduces metrics
- **Token management** - auto-refreshes expiring tokens
- **Production-ready** - comprehensive error handling, logging, and retry logic
- **Cost-effective** - serverless architecture, pay only for what you use

## Project Structure

```
fb-ads-bigquery-etl/
├── main.py                    # Main ETL script (daily sync)
├── backfill.py                # Historical data import
├── load_csv_to_bq.py          # CSV to BigQuery loader
├── requirements.txt           # Python dependencies
├── schema.json                # BigQuery table schema
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── cloudbuild.yaml            # CI/CD deployment config
├── deploy.sh                  # Quick deployment script
├── .gcloudignore              # Cloud deployment ignore rules
│
├── README.md                  # Complete documentation
├── QUICKSTART.md              # Quick start for new team members
├── SETUP_CHECKLIST.md         # Setup checklist for new clients
│
└── docs/
    ├── GCP_SETUP.md           # Detailed GCP setup guide
    └── DEPLOYMENT.md          # Cloud deployment guide
```

## Documentation Guide

### For New Team Members

Start here: **[QUICKSTART.md](QUICKSTART.md)**
- Simplified getting started guide
- How to run locally
- Common tasks and troubleshooting

### For Project Setup

Use this: **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)**
- Complete checklist for new client setup
- Tracks what information you need
- Step-by-step with checkboxes

### For Detailed Instructions

Reference these:
- **[README.md](README.md)** - Complete project documentation
- **[docs/GCP_SETUP.md](docs/GCP_SETUP.md)** - Detailed GCP setup instructions
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Cloud deployment guide

## Quick Start for Your Team

### 1. Local Testing (5-10 minutes)

```bash
# Get the code
cd fb-ads-bigquery-etl

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your credentials

# Update account IDs in main.py and backfill.py

# Authenticate
gcloud auth application-default login

# Test
DRY_RUN=true python main.py
```

### 2. Production Deployment (15-30 minutes)

```bash
# Update deploy.sh with your project info
nano deploy.sh

# Deploy
./deploy.sh

# Set up daily schedule
gcloud scheduler jobs create pubsub daily-fb-ads-sync \
  --schedule="0 9 * * *" \
  --topic=fb-ads-topic \
  --message-body="trigger" \
  --location=us-central1
```

## Required Credentials

### Facebook
- **Access Token** - from Facebook Graph API Explorer
- **App ID** - from Facebook Developer Console
- **App Secret** - from Facebook Developer Console
- **Account IDs** - from Facebook Ads Manager URLs

### Google Cloud
- **Project ID** - your GCP project
- **Service Account** - with BigQuery and Secret Manager permissions
- **BigQuery Dataset/Table** - where data is stored

## Data Schema

The pipeline fetches these metrics:

**Basic Metrics:**
- Impressions, Clicks, Spend
- Campaign name, Ad name
- Date range, Publisher platform

**Video Metrics:**
- 2-second views, 30-second views
- Watch time percentages (25%, 50%, 75%, 100%)
- Average watch time

**Conversion Metrics:**
- Landing page views
- Leads, Page engagement
- Custom conversions
- And more (dynamic based on your ads)

See [schema.json](schema.json) for the full schema.

## Cost Estimate

For typical usage (1000 rows/day, daily sync):

- **BigQuery**: ~$2-5/month
- **Cloud Functions**: ~$0-1/month (free tier)
- **Secret Manager**: ~$0.20/month
- **Total: $5-10/month**

## Use Cases

### Daily Reporting
- Automated daily sync of ad performance
- Historical data available for analysis
- Connect to BI tools (Looker, Data Studio, Tableau)

### Multi-Client Management
- Easy to set up for new clients (just update IDs)
- Each client can have their own project/dataset
- Consistent schema across all clients

### Historical Analysis
- Backfill any date range
- Compare performance over time
- Track trends and seasonality

## Technical Stack

- **Language**: Python 3.13
- **Cloud Platform**: Google Cloud Platform
  - BigQuery (data warehouse)
  - Cloud Functions (serverless compute)
  - Secret Manager (credential storage)
  - Cloud Scheduler (automation)
- **APIs**: Facebook Marketing API v22.0

## Security Features

- Secrets stored in Google Secret Manager (not in code)
- Automatic token refresh (no manual intervention)
- Service account with minimal required permissions
- `.gitignore` prevents accidental credential commits
- Secure authentication with Google Cloud

## Support & Troubleshooting

Common issues and solutions are documented in:
- README.md - Troubleshooting section
- QUICKSTART.md - Quick fixes
- docs/DEPLOYMENT.md - Deployment troubleshooting

## Next Steps

1. **Read QUICKSTART.md** if you're new to the project
2. **Follow SETUP_CHECKLIST.md** when setting up for a new client
3. **Reference README.md** for detailed documentation
4. **Check docs/** for GCP setup and deployment guides

## Questions?

Check the documentation first:
- [QUICKSTART.md](QUICKSTART.md) - Getting started
- [README.md](README.md) - Complete documentation
- [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) - Setup guide
- [docs/GCP_SETUP.md](docs/GCP_SETUP.md) - GCP configuration
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Cloud deployment

## License

Internal use only. Modify as needed for client requirements.

---

**Created:** January 2026
**Maintained by:** Your Team
**Contact:** [Your contact info]
