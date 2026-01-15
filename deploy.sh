#!/bin/bash
# Quick deployment script for Cloud Function
#
# Usage:
#   ./deploy.sh

set -e

# Configuration - UPDATE THESE FOR YOUR CLIENT
PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
FUNCTION_NAME="fetchFbAdsToBigQuery"
DATASET_ID="ad_analytics"
TABLE_ID="ad_data"
SERVICE_ACCOUNT="fb-ads-etl-sa"

echo "======================================"
echo "Facebook Ads ETL - Cloud Function Deploy"
echo "======================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Function: $FUNCTION_NAME"
echo "Target: $DATASET_ID.$TABLE_ID"
echo ""

# Set active project
echo "Setting active project..."
gcloud config set project $PROJECT_ID

# Check if Pub/Sub topic exists
echo "Checking Pub/Sub topic..."
if ! gcloud pubsub topics describe fb-ads-topic &>/dev/null; then
  echo "Creating Pub/Sub topic..."
  gcloud pubsub topics create fb-ads-topic
else
  echo "Pub/Sub topic already exists"
fi

# Deploy function
echo ""
echo "Deploying Cloud Function..."
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
  --service-account=$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com

echo ""
echo "======================================"
echo "✅ Deployment complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Test the function:"
echo "     gcloud pubsub topics publish fb-ads-topic --message='test'"
echo ""
echo "  2. View logs:"
echo "     gcloud functions logs read $FUNCTION_NAME --region=$REGION --limit=50"
echo ""
echo "  3. Set up scheduler (if not already done):"
echo "     gcloud scheduler jobs create pubsub daily-fb-ads-sync \\"
echo "       --schedule='0 9 * * *' \\"
echo "       --topic=fb-ads-topic \\"
echo "       --message-body='trigger' \\"
echo "       --location=$REGION"
echo ""
