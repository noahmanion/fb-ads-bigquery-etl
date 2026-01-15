# Google Cloud Platform Setup Guide

This guide walks through setting up Google Cloud Platform for the Facebook Ads to BigQuery ETL pipeline.

## Table of Contents

1. [Create GCP Project](#1-create-gcp-project)
2. [Enable Required APIs](#2-enable-required-apis)
3. [Create BigQuery Dataset](#3-create-bigquery-dataset)
4. [Create BigQuery Table](#4-create-bigquery-table)
5. [Set Up Secret Manager](#5-set-up-secret-manager)
6. [Configure Service Account](#6-configure-service-account-for-cloud-functions)
7. [Verify Setup](#7-verify-setup)

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed ([installation guide](https://cloud.google.com/sdk/docs/install))
- Access to create projects and resources
- Facebook access token ready (from Facebook setup)

## 1. Create GCP Project

### Via Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top
3. Click "New Project"
4. Enter project details:
   - Project name: `client-ads-analytics` (or your preferred name)
   - Organization: Select your organization (if applicable)
   - Location: Select appropriate folder/org
5. Click "Create"
6. Note your **Project ID** (may be different from project name)

### Via Command Line

```bash
# Set variables
PROJECT_ID="client-ads-analytics-123"  # Must be globally unique
PROJECT_NAME="Client Ads Analytics"

# Create project
gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"

# Set as active project
gcloud config set project $PROJECT_ID

# Link billing account (required)
# First, list billing accounts
gcloud billing accounts list

# Link billing account to project
BILLING_ACCOUNT_ID="XXXXXX-XXXXXX-XXXXXX"
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID
```

## 2. Enable Required APIs

### Via Console

1. Go to [APIs & Services](https://console.cloud.google.com/apis/dashboard)
2. Click "Enable APIs and Services"
3. Search for and enable each of these:
   - **BigQuery API**
   - **Secret Manager API**
   - **Cloud Functions API** (if deploying to Cloud Functions)
   - **Cloud Scheduler API** (if scheduling)
   - **Pub/Sub API** (if using Cloud Functions)

### Via Command Line

```bash
# Enable all required APIs at once
gcloud services enable \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com \
  pubsub.googleapis.com \
  cloudbuild.googleapis.com
```

This takes 2-3 minutes to complete.

## 3. Create BigQuery Dataset

A dataset is a container for tables in BigQuery.

### Via Console

1. Go to [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Click your project name in the Explorer panel
3. Click the three dots → "Create dataset"
4. Configure dataset:
   - **Dataset ID**: `ad_analytics` (or your preferred name)
   - **Data location**: Choose based on your region
     - `us` for United States
     - `eu` for European Union
     - Or select a specific region like `us-central1`
   - **Default table expiration**: Leave as "Never"
   - **Encryption**: Google-managed key (default)
5. Click "Create dataset"

### Via Command Line

```bash
# Set variables
DATASET_ID="ad_analytics"
LOCATION="us"  # or "eu", "us-central1", etc.

# Create dataset
bq mk \
  --dataset \
  --location=$LOCATION \
  --description="Facebook Ads performance data" \
  $PROJECT_ID:$DATASET_ID
```

## 4. Create BigQuery Table

### Via Console

1. In BigQuery Console, expand your project and dataset
2. Click the three dots next to the dataset → "Create table"
3. Configure table:
   - **Source**: Empty table
   - **Dataset**: Select your dataset (e.g., `ad_analytics`)
   - **Table name**: `ad_data`
   - **Schema**: Click "Edit as text" and paste the contents of `schema.json`
4. Click "Create table"

### Via Command Line

```bash
# From the project root directory
TABLE_ID="ad_data"

bq mk \
  --table \
  --description="Facebook ads performance metrics" \
  --time_partitioning_field=date_start \
  --time_partitioning_type=DAY \
  $PROJECT_ID:$DATASET_ID.$TABLE_ID \
  schema.json
```

The `--time_partitioning_field` makes queries more efficient and reduces costs by partitioning data by date.

### Schema File (schema.json)

The schema is already in your project root. It includes:
- Campaign and ad identifiers
- Basic metrics (impressions, clicks, spend)
- Video engagement metrics
- Conversion actions
- Dates and platform breakdown

The pipeline will automatically add new fields as Facebook introduces new metrics.

## 5. Set Up Secret Manager

Secret Manager securely stores sensitive data like API tokens.

### Create Secrets

You need to create secrets for:
1. **fb-marketing-token**: Your Facebook access token
2. **fb-app-id**: Your Facebook app ID
3. **fb-app-secret**: Your Facebook app secret

### Via Console

1. Go to [Secret Manager](https://console.cloud.google.com/security/secret-manager)
2. Click "Create Secret"
3. For **fb-marketing-token**:
   - Name: `fb-marketing-token`
   - Secret value: Paste your Facebook access token
   - Regions: Automatic (or select specific regions)
   - Click "Create Secret"
4. Repeat for **fb-app-id** and **fb-app-secret**

### Via Command Line

```bash
# Store Facebook access token
echo -n "YOUR_FACEBOOK_ACCESS_TOKEN" | gcloud secrets create fb-marketing-token \
  --data-file=- \
  --replication-policy=automatic

# Store Facebook app ID
echo -n "YOUR_FACEBOOK_APP_ID" | gcloud secrets create fb-app-id \
  --data-file=- \
  --replication-policy=automatic

# Store Facebook app secret
echo -n "YOUR_FACEBOOK_APP_SECRET" | gcloud secrets create fb-app-secret \
  --data-file=- \
  --replication-policy=automatic

# Create optional metadata secret (for tracking token refreshes)
echo -n "{}" | gcloud secrets create fb-marketing-token-metadata \
  --data-file=- \
  --replication-policy=automatic
```

### Update a Secret (when token expires)

```bash
# Add a new version of the token
echo -n "NEW_FACEBOOK_ACCESS_TOKEN" | gcloud secrets versions add fb-marketing-token \
  --data-file=-
```

### Grant Access to Secrets

```bash
# For your user account (local development)
gcloud secrets add-iam-policy-binding fb-marketing-token \
  --member="user:your-email@example.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding fb-app-id \
  --member="user:your-email@example.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding fb-app-secret \
  --member="user:your-email@example.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 6. Configure Service Account (for Cloud Functions)

If you're deploying to Cloud Functions, you need a service account with appropriate permissions.

### Create Service Account

```bash
# Create service account
SERVICE_ACCOUNT_NAME="fb-ads-etl-sa"
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="Facebook Ads ETL Service Account" \
  --description="Service account for Facebook Ads to BigQuery ETL pipeline"
```

### Grant Permissions

```bash
# BigQuery Data Editor (to insert data)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataEditor"

# BigQuery User (to run jobs)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.user"

# Secret Manager Secret Accessor (to read secrets)
gcloud secrets add-iam-policy-binding fb-marketing-token \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding fb-app-id \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding fb-app-secret \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

# Secret Manager Secret Version Adder (to refresh tokens)
gcloud secrets add-iam-policy-binding fb-marketing-token \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretVersionAdder"
```

### Create Service Account Key (for local testing)

```bash
# Create and download key
gcloud iam service-accounts keys create ~/fb-ads-etl-key.json \
  --iam-account=$SERVICE_ACCOUNT_EMAIL

# Set environment variable to use key
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/fb-ads-etl-key.json"
```

**Important**: Keep this key file secure and never commit it to version control.

## 7. Verify Setup

### Check APIs

```bash
# List enabled APIs
gcloud services list --enabled | grep -E "bigquery|secret|function"
```

Expected output:
```
bigquery.googleapis.com
secretmanager.googleapis.com
cloudfunctions.googleapis.com
```

### Check BigQuery Dataset and Table

```bash
# List datasets
bq ls

# Show table schema
bq show $PROJECT_ID:$DATASET_ID.$TABLE_ID
```

### Check Secrets

```bash
# List secrets
gcloud secrets list

# Access a secret (to verify permissions)
gcloud secrets versions access latest --secret="fb-marketing-token"
```

### Test Query

```bash
# Run a test query
bq query --nouse_legacy_sql \
"SELECT COUNT(*) as row_count FROM \`$PROJECT_ID.$DATASET_ID.$TABLE_ID\`"
```

Expected output: `0` rows (empty table initially)

## Quick Setup Script

Here's a complete script that sets up everything:

```bash
#!/bin/bash
set -e

# Configuration
PROJECT_ID="client-ads-analytics-123"
DATASET_ID="ad_analytics"
TABLE_ID="ad_data"
LOCATION="us"
SERVICE_ACCOUNT_NAME="fb-ads-etl-sa"

echo "Setting up GCP for Facebook Ads ETL..."

# Set active project
gcloud config set project $PROJECT_ID

# Enable APIs
echo "Enabling APIs..."
gcloud services enable \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com \
  pubsub.googleapis.com

# Create BigQuery dataset
echo "Creating BigQuery dataset..."
bq mk --dataset --location=$LOCATION $PROJECT_ID:$DATASET_ID || true

# Create BigQuery table
echo "Creating BigQuery table..."
bq mk --table \
  --time_partitioning_field=date_start \
  --time_partitioning_type=DAY \
  $PROJECT_ID:$DATASET_ID.$TABLE_ID \
  schema.json || true

# Create secrets (prompts for values)
echo "Creating secrets..."
read -sp "Enter Facebook Access Token: " FB_TOKEN
echo
echo -n "$FB_TOKEN" | gcloud secrets create fb-marketing-token --data-file=- || true

read -p "Enter Facebook App ID: " FB_APP_ID
echo -n "$FB_APP_ID" | gcloud secrets create fb-app-id --data-file=- || true

read -sp "Enter Facebook App Secret: " FB_APP_SECRET
echo
echo -n "$FB_APP_SECRET" | gcloud secrets create fb-app-secret --data-file=- || true

# Create service account
echo "Creating service account..."
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="Facebook Ads ETL Service Account" || true

# Grant permissions
echo "Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.user"

for secret in fb-marketing-token fb-app-id fb-app-secret; do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/secretmanager.secretAccessor"
done

gcloud secrets add-iam-policy-binding fb-marketing-token \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretVersionAdder"

echo "✅ Setup complete!"
echo ""
echo "Summary:"
echo "  Project: $PROJECT_ID"
echo "  Dataset: $DATASET_ID"
echo "  Table: $TABLE_ID"
echo "  Service Account: $SERVICE_ACCOUNT_EMAIL"
echo ""
echo "Update your .env file with:"
echo "  GCP_PROJECT=$PROJECT_ID"
echo "  BQ_TABLE=$DATASET_ID.$TABLE_ID"
```

Save this as `setup_gcp.sh`, make it executable with `chmod +x setup_gcp.sh`, and run it.

## Next Steps

After completing this setup:

1. Update your `.env` file with the GCP configuration:
   ```
   GCP_PROJECT=your-project-id
   BQ_TABLE=ad_analytics.ad_data
   ```

2. Test the pipeline locally:
   ```bash
   python main.py
   ```

3. Deploy to Cloud Functions (see [DEPLOYMENT.md](DEPLOYMENT.md))

## Troubleshooting

### "Permission denied" errors

- Make sure you've granted yourself access to secrets (step 5)
- For Cloud Functions, check service account permissions (step 6)
- Run: `gcloud auth application-default login` for local development

### "API not enabled" errors

- Wait a few minutes after enabling APIs
- Verify with: `gcloud services list --enabled`

### "Table not found" errors

- Check the table exists: `bq ls $DATASET_ID`
- Verify schema: `bq show $PROJECT_ID:$DATASET_ID.$TABLE_ID`

### Billing issues

- Ensure billing is enabled: https://console.cloud.google.com/billing
- Link billing to project: `gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID`

## Cost Considerations

### BigQuery Costs

- **Storage**: ~$0.02 per GB per month (first 10 GB free)
- **Queries**: ~$5 per TB processed (first 1 TB per month free)
- **Streaming inserts**: Free

For typical ad data (1000 rows/day), expect:
- Storage: < $1/month
- Queries: < $1/month with partitioning
- **Total: < $5/month**

### Cloud Functions Costs

- **Invocations**: First 2 million free
- **Compute time**: Depends on execution time
- **Network**: Egress charges may apply

For 1 daily execution:
- **Total: < $1/month** (likely $0 with free tier)

### Secret Manager Costs

- **Active secrets**: $0.06 per secret per month
- **Access operations**: First 10,000 free per month
- **Total: ~$0.18/month** for 3 secrets

### Total Estimated Cost

**$5-10 per month** for typical usage.

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use Secret Manager** instead of environment variables in production
3. **Rotate tokens** regularly (every 60 days for user tokens)
4. **Use system user tokens** (never expire) for production
5. **Apply least privilege** - only grant necessary permissions
6. **Enable audit logging** to track access to secrets
7. **Use VPC Service Controls** for additional security in production

## Additional Resources

- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [IAM Best Practices](https://cloud.google.com/iam/docs/best-practices)
