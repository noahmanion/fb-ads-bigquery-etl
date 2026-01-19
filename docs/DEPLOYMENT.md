# Deployment Guide

This guide covers deploying the Facebook Ads ETL pipeline to Google Cloud Functions for automated daily execution.

## Table of Contents

1. [Deployment Options](#deployment-options)
2. [Deploy to Cloud Functions](#deploy-to-cloud-functions)
3. [Set Up Scheduler](#set-up-scheduler)
4. [Monitoring and Logging](#monitoring-and-logging)
5. [Troubleshooting](#troubleshooting)

## Deployment Options

### Option 1: Cloud Functions (Recommended)

**Pros:**
- Serverless - no infrastructure management
- Pay only for execution time
- Built-in monitoring and logging
- Easy to schedule with Cloud Scheduler
- Automatic scaling

**Cons:**
- 540-second (9 minute) maximum execution time
- Cold start latency for infrequent runs

**Best for:** Daily/hourly scheduled runs with moderate data volumes

### Option 2: Cloud Run

**Pros:**
- Longer execution time (up to 60 minutes)
- More control over resources
- Can handle larger data volumes

**Cons:**
- Slightly more complex setup
- May cost more for infrequent runs

**Best for:** Large data volumes or complex processing

### Option 3: Compute Engine VM

**Pros:**
- Complete control
- Can run continuously
- Suitable for very large workloads

**Cons:**
- Requires managing infrastructure
- Always-on costs
- More maintenance overhead

**Best for:** Continuous processing or very custom requirements

This guide focuses on **Cloud Functions** (Option 1).

## Deploy to Cloud Functions

### Prerequisites

- Complete [GCP Setup](GCP_SETUP.md)
- Test the pipeline locally first
- Have your Facebook tokens in Secret Manager

### Required APIs

Ensure these APIs are enabled before deploying:

```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  eventarc.googleapis.com \
  pubsub.googleapis.com \
  run.googleapis.com \
  --project=YOUR_PROJECT_ID
```

### Required IAM Permissions for Cloud Build

The Cloud Build service account needs these roles to deploy Cloud Functions:

```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")

# Grant Cloud Functions Developer role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/cloudfunctions.developer"

# Grant Service Account User role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Grant Cloud Build Service Account role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"
```

Wait a minute for IAM changes to propagate before deploying.

### Method 1: Using gcloud CLI (Recommended)

#### 1. Prepare Deployment

From your project root directory:

```bash
# Set variables
PROJECT_ID="your-gcp-project-id"
REGION="us-central1"  # or your preferred region
FUNCTION_NAME="fetchFbAdsToBigQuery"
DATASET_ID="ad_analytics"
TABLE_ID="ad_data"

# Set active project
gcloud config set project $PROJECT_ID
```

#### 2. Create Pub/Sub Topic

Cloud Functions need a trigger. We'll use Pub/Sub:

```bash
gcloud pubsub topics create fb-ads-topic --project=$PROJECT_ID
```

#### 3. Deploy Function

```bash
gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --region=$REGION \
  --runtime=python313 \
  --entry-point=main \
  --source=. \
  --trigger-topic=fb-ads-topic \
  --set-env-vars=GCP_PROJECT=$PROJECT_ID,BQ_TABLE=$DATASET_ID.$TABLE_ID \
  --timeout=540 \
  --memory=512MB \
  --max-instances=1 \
  --service-account=fb-ads-etl-sa@$PROJECT_ID.iam.gserviceaccount.com
```

**Parameters explained:**
- `--gen2`: Use 2nd generation Cloud Functions (better performance)
- `--runtime=python313`: Python 3.13 runtime
- `--entry-point=main`: Function to call (main function in main.py)
- `--source=.`: Deploy from current directory
- `--trigger-topic`: Pub/Sub topic that triggers the function
- `--set-env-vars`: Environment variables for the function
- `--timeout=540`: Maximum execution time (9 minutes)
- `--memory=512MB`: Memory allocation
- `--max-instances=1`: Prevent concurrent runs
- `--service-account`: Service account with required permissions

The deployment takes 2-3 minutes.

#### 4. Verify Deployment

```bash
# List functions
gcloud functions list --region=$REGION

# Describe function
gcloud functions describe $FUNCTION_NAME --region=$REGION
```

#### 5. Test the Function

```bash
# Trigger the function manually
gcloud pubsub topics publish fb-ads-topic --message="test"

# Check logs
gcloud functions logs read $FUNCTION_NAME --region=$REGION --limit=50
```

### Method 2: Using Cloud Build (CI/CD)

For automated deployments, use Cloud Build.

#### 1. Create cloudbuild.yaml

Create `cloudbuild.yaml` in your project root:

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
          --source=. \
          --trigger-topic=fb-ads-topic \
          --set-env-vars=GCP_PROJECT=${PROJECT_ID},BQ_TABLE=ad_analytics.ad_data \
          --timeout=540 \
          --memory=512MB \
          --max-instances=1 \
          --service-account=fb-ads-etl-sa@${PROJECT_ID}.iam.gserviceaccount.com

options:
  logging: CLOUD_LOGGING_ONLY

timeout: 600s
```

#### 2. Deploy Using Cloud Build

```bash
gcloud builds submit --config=cloudbuild.yaml
```

#### 3. Set Up Continuous Deployment (Optional)

Connect to a Git repository:

```bash
# Create trigger from GitHub
gcloud builds triggers create github \
  --name="deploy-fb-ads-function" \
  --repo-name="your-repo" \
  --repo-owner="your-github-username" \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

Now pushes to `main` branch automatically deploy.

### Method 3: Using Console UI

1. Go to [Cloud Functions](https://console.cloud.google.com/functions)
2. Click "Create Function"
3. Configure basics:
   - **Function name**: `fetchFbAdsToBigQuery`
   - **Region**: `us-central1`
   - **Trigger**: Cloud Pub/Sub
   - **Topic**: Select or create `fb-ads-topic`
4. Click "Save" then "Next"
5. Configure runtime:
   - **Runtime**: Python 3.13
   - **Entry point**: `main`
   - **Source code**: Inline editor or Cloud Storage
6. Paste the code from `main.py`
7. Add `requirements.txt` content
8. Set environment variables:
   - `GCP_PROJECT`: your project ID
   - `BQ_TABLE`: your dataset.table
9. Configure resources:
   - **Memory**: 512 MB
   - **Timeout**: 540 seconds
   - **Max instances**: 1
10. Click "Deploy"

## Set Up Scheduler

Schedule the function to run daily.

### Using gcloud CLI

```bash
# Create daily job at 9 AM UTC
gcloud scheduler jobs create pubsub daily-fb-ads-sync \
  --schedule="0 9 * * *" \
  --topic=fb-ads-topic \
  --message-body='{"trigger":"scheduled"}' \
  --location=$REGION \
  --description="Daily Facebook Ads data sync"

# Verify
gcloud scheduler jobs list --location=$REGION

# Run immediately to test
gcloud scheduler jobs run daily-fb-ads-sync --location=$REGION
```

### Schedule Format (Cron)

```
# Format: minute hour day month day-of-week
# All times in UTC

0 9 * * *       # 9 AM UTC daily
0 */6 * * *     # Every 6 hours
30 8 * * 1-5    # 8:30 AM UTC weekdays only
0 0 1 * *       # First day of every month
```

### Using Console UI

1. Go to [Cloud Scheduler](https://console.cloud.google.com/cloudscheduler)
2. Click "Create Job"
3. Configure:
   - **Name**: `daily-fb-ads-sync`
   - **Region**: Same as your function
   - **Frequency**: `0 9 * * *` (9 AM UTC daily)
   - **Timezone**: Choose your timezone
   - **Target**: Pub/Sub
   - **Topic**: `fb-ads-topic`
   - **Message body**: `{"trigger":"scheduled"}`
4. Click "Create"

### Common Schedules

```bash
# Every day at 9 AM UTC
--schedule="0 9 * * *"

# Every 12 hours
--schedule="0 */12 * * *"

# Weekdays at 8 AM UTC
--schedule="0 8 * * 1-5"

# Every Sunday at midnight
--schedule="0 0 * * 0"
```

### Timezone Considerations

Cloud Scheduler uses UTC by default. To run at 9 AM EST (UTC-5):
- Winter (EST): Use 14:00 UTC → `--schedule="0 14 * * *"`
- Summer (EDT): Use 13:00 UTC → `--schedule="0 13 * * *"`

Or specify timezone:
```bash
--time-zone="America/New_York"
```

## Monitoring and Logging

### View Logs

#### Via gcloud

```bash
# Recent logs
gcloud functions logs read fetchFbAdsToBigQuery \
  --region=$REGION \
  --limit=100

# Follow logs in real-time
gcloud functions logs read fetchFbAdsToBigQuery \
  --region=$REGION \
  --limit=50 \
  --filter="timestamp>=2025-01-15T00:00:00Z"

# Show only errors
gcloud functions logs read fetchFbAdsToBigQuery \
  --region=$REGION \
  --limit=50 \
  --filter="severity>=ERROR"
```

#### Via Console

1. Go to [Cloud Functions](https://console.cloud.google.com/functions)
2. Click on your function
3. Click "Logs" tab
4. Use filters to search logs

#### Via Logs Explorer

Advanced log queries in [Logs Explorer](https://console.cloud.google.com/logs):

```
resource.type="cloud_function"
resource.labels.function_name="fetchFbAdsToBigQuery"
severity>=ERROR
```

### Set Up Alerts

#### Error Alert

Get notified when function fails:

```bash
# Create notification channel (email)
gcloud alpha monitoring channels create \
  --display-name="Alert Email" \
  --type=email \
  --channel-labels=email_address=your-email@example.com

# Get channel ID
CHANNEL_ID=$(gcloud alpha monitoring channels list \
  --filter="displayName='Alert Email'" \
  --format="value(name)")

# Create alert policy
gcloud alpha monitoring policies create \
  --notification-channels=$CHANNEL_ID \
  --display-name="FB Ads ETL Function Errors" \
  --condition-display-name="Error rate" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s \
  --condition-filter='resource.type="cloud_function" AND resource.labels.function_name="fetchFbAdsToBigQuery" AND severity="ERROR"'
```

#### Execution Time Alert

Alert if function takes too long:

```yaml
# Via Console: Monitoring > Alerting > Create Policy
# Condition: Cloud Function Execution Time > 480 seconds
```

### View Metrics

#### Via Console

1. Go to [Cloud Functions](https://console.cloud.google.com/functions)
2. Click on your function
3. Click "Metrics" tab
4. View:
   - Invocations
   - Execution time
   - Memory usage
   - Error rate

#### Via Metrics Explorer

Go to [Metrics Explorer](https://console.cloud.google.com/monitoring/metrics-explorer) and query:

```
Resource type: Cloud Function
Metric: function/execution_count
Function: fetchFbAdsToBigQuery
```

### BigQuery Monitoring

Check data freshness:

```sql
-- Most recent data date
SELECT MAX(date_start) as latest_date
FROM `your-project.ad_analytics.ad_data`;

-- Row count by date
SELECT
  date_start,
  COUNT(*) as row_count,
  SUM(impressions) as total_impressions,
  SUM(spend) as total_spend
FROM `your-project.ad_analytics.ad_data`
WHERE date_start >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY date_start
ORDER BY date_start DESC;
```

Create a scheduled query to monitor daily:

```sql
-- Create in BigQuery > Scheduled queries
SELECT
  CURRENT_DATE() as check_date,
  CASE
    WHEN MAX(date_start) = CURRENT_DATE() - 1 THEN 'OK'
    ELSE 'MISSING_DATA'
  END as status
FROM `your-project.ad_analytics.ad_data`;
```

## Updating the Deployment

### Update Function Code

```bash
# After making changes to main.py
gcloud functions deploy fetchFbAdsToBigQuery \
  --gen2 \
  --region=$REGION \
  --runtime=python313 \
  --entry-point=main \
  --source=. \
  --trigger-topic=fb-ads-topic \
  --set-env-vars=GCP_PROJECT=$PROJECT_ID,BQ_TABLE=$DATASET_ID.$TABLE_ID \
  --timeout=540 \
  --memory=512MB
```

### Update Environment Variables Only

```bash
gcloud functions deploy fetchFbAdsToBigQuery \
  --region=$REGION \
  --update-env-vars=BQ_TABLE=new_dataset.new_table
```

### Update Account IDs

Edit `main.py` and update `ACCOUNT_IDS`, then redeploy:

```python
ACCOUNT_IDS = [
    "1234567890",
    "9876543210",
    "5555555555"  # New account
]
```

```bash
# Redeploy
gcloud functions deploy fetchFbAdsToBigQuery --region=$REGION --source=.
```

## Troubleshooting

### Function Times Out

**Problem**: Function exceeds 540-second limit

**Solutions:**
1. Reduce date range (use yesterday only, not last 7 days)
2. Process accounts sequentially instead of in parallel
3. Consider Cloud Run instead (60-minute limit)

### Token Expired

**Problem**: "Token is invalid" error

**Solution:**
```bash
# Update token in Secret Manager
echo -n "NEW_TOKEN" | gcloud secrets versions add fb-marketing-token --data-file=-

# Function will pick up new token automatically on next run
```

### No Data Returned

**Problem**: Function completes but no data inserted

**Check:**
1. Verify ads were running yesterday
2. Check logs for API errors
3. Verify account IDs are correct
4. Test locally first: `python main.py`

### Permission Errors

**Problem**: "Permission denied" on BigQuery or Secret Manager

**Solution:**
```bash
# Re-grant permissions to service account
SERVICE_ACCOUNT="fb-ads-etl-sa@$PROJECT_ID.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/bigquery.dataEditor"

gcloud secrets add-iam-policy-binding fb-marketing-token \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

### Cloud Build Permission Errors

**Problem**: "Could not build the function due to missing permissions" or "serviceAccounts cannot be accessed by IAM"

**Solution:**
```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Grant required roles to Cloud Build service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"
```

Wait 1-2 minutes for IAM propagation, then retry deployment.

### Eventarc API Not Enabled

**Problem**: "Eventarc API has not been used in project"

**Solution:**
```bash
gcloud services enable eventarc.googleapis.com --project=$PROJECT_ID
```

Wait a few minutes for the API to fully enable, then retry deployment.

### Cold Starts

**Problem**: Function slow to start

**Solution:**
1. Use minimum instances (costs more):
   ```bash
   gcloud functions deploy fetchFbAdsToBigQuery \
     --region=$REGION \
     --min-instances=1
   ```
2. Accept cold starts (typical for daily runs)

### View Function Configuration

```bash
gcloud functions describe fetchFbAdsToBigQuery --region=$REGION
```

## Cost Optimization

### Reduce Invocations

- Schedule only as often as needed (daily vs hourly)
- Use a single Scheduler job instead of multiple

### Optimize Memory

Test different memory allocations:
- 256MB: Minimal cost, may be slow
- 512MB: Balanced (recommended)
- 1024MB: Faster but costs more

### Use Minimum Instances Wisely

Only use `--min-instances` if cold starts are truly problematic (adds ongoing costs).

## Rollback

### Rollback to Previous Version

```bash
# List versions
gcloud functions list --region=$REGION

# Get previous version
PREVIOUS_VERSION=$(gcloud functions describe fetchFbAdsToBigQuery \
  --region=$REGION \
  --format="value(updateTime)" | sort -r | sed -n 2p)

# Rollback
gcloud functions deploy fetchFbAdsToBigQuery \
  --region=$REGION \
  --source=gs://gcf-sources-$PROJECT_ID-$REGION/fetchFbAdsToBigQuery-$PREVIOUS_VERSION.zip
```

### Emergency Stop

```bash
# Delete scheduler job (stops automatic runs)
gcloud scheduler jobs delete daily-fb-ads-sync --location=$REGION

# Delete function (complete removal)
gcloud functions delete fetchFbAdsToBigQuery --region=$REGION
```

## Next Steps

After successful deployment:

1. **Monitor for 7 days** to ensure daily runs complete successfully
2. **Set up alerting** for failures and missing data
3. **Create dashboards** in Looker Studio or Data Studio using BigQuery data
4. **Document** any client-specific configurations
5. **Share access** with stakeholders who need to view data

## Additional Resources

- [Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Cloud Monitoring Documentation](https://cloud.google.com/monitoring/docs)
- [Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
