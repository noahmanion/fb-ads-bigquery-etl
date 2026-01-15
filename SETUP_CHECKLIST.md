# Setup Checklist for New Client

Use this checklist when setting up the pipeline for a new client. Check off each item as you complete it.

## Client Information

**Client Name:** _______________________
**Date:** _______________________
**Your Name:** _______________________

## Pre-Setup Information Gathering

Collect this information before starting:

- [ ] Facebook Ad Account IDs (from Ads Manager URLs)
  - Account 1: _______________
  - Account 2: _______________
  - Account 3: _______________

- [ ] GCP Project ID: _______________
- [ ] BigQuery Dataset Name: _______________
- [ ] BigQuery Table Name: _______________
- [ ] Preferred GCP Region: _______________ (e.g., us-central1)
- [ ] Client Timezone: _______________ (for scheduler)

## Facebook Setup

- [ ] Create Facebook Developer App
  - [ ] App Name: _______________
  - [ ] App ID: _______________
  - [ ] App Secret: _______________ (keep secure!)

- [ ] Add Marketing API to the app
- [ ] Grant required permissions: `ads_read`, `ads_management`, `business_management`

- [ ] Generate Access Token
  - [ ] Token type: [ ] User Token (60 days) [ ] System User Token (never expires)
  - [ ] Token: _______________ (keep secure!)
  - [ ] Expiration date (if applicable): _______________

- [ ] Verify token has access to all ad accounts
  - [ ] Test with Graph API Explorer
  - [ ] Confirmed access to all accounts

## Google Cloud Platform Setup

- [ ] Create GCP Project
  - [ ] Project ID: _______________
  - [ ] Billing enabled: Yes

- [ ] Enable APIs
  - [ ] BigQuery API
  - [ ] Secret Manager API
  - [ ] Cloud Functions API
  - [ ] Cloud Scheduler API
  - [ ] Pub/Sub API

- [ ] Create BigQuery Dataset
  - [ ] Dataset ID: _______________
  - [ ] Location: _______________

- [ ] Create BigQuery Table
  - [ ] Table ID: _______________
  - [ ] Schema uploaded from schema.json
  - [ ] Partitioning enabled on date_start

- [ ] Set up Secret Manager
  - [ ] Created secret: `fb-marketing-token`
  - [ ] Created secret: `fb-app-id`
  - [ ] Created secret: `fb-app-secret`
  - [ ] Verified secrets are accessible

- [ ] Create Service Account (for Cloud Functions)
  - [ ] Service account name: `fb-ads-etl-sa`
  - [ ] Email: _______________@_______________.iam.gserviceaccount.com
  - [ ] Granted BigQuery Data Editor role
  - [ ] Granted BigQuery User role
  - [ ] Granted Secret Manager Secret Accessor role
  - [ ] Granted Secret Manager Secret Version Adder role

## Local Setup

- [ ] Clone/download project code
- [ ] Install Python 3.11 or higher
- [ ] Install gcloud CLI
- [ ] Create virtual environment: `python3 -m venv venv`
- [ ] Activate virtual environment
- [ ] Install dependencies: `pip install -r requirements.txt`

- [ ] Configure `.env` file
  - [ ] Copied from `.env.example`
  - [ ] Set `FB_TOKEN`
  - [ ] Set `FB_APP_ID`
  - [ ] Set `GCP_PROJECT`
  - [ ] Set `BQ_TABLE`

- [ ] Update `ACCOUNT_IDS` in scripts
  - [ ] Updated `main.py` line 23
  - [ ] Updated `backfill.py` line 20

- [ ] Authenticate with Google Cloud
  - [ ] `gcloud auth login`
  - [ ] `gcloud config set project PROJECT_ID`
  - [ ] `gcloud auth application-default login`

## Testing

- [ ] Test with dry run: `DRY_RUN=true python main.py`
  - [ ] No errors
  - [ ] Token validated successfully
  - [ ] Data fetched successfully
  - [ ] CSV created in /tmp/

- [ ] Test real run: `python main.py`
  - [ ] Data inserted to BigQuery
  - [ ] Row count verified in BigQuery
  - [ ] No errors in output

- [ ] Test backfill (optional)
  - [ ] `python backfill.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD`
  - [ ] CSV created successfully
  - [ ] `python load_csv_to_bq.py`
  - [ ] Historical data loaded to BigQuery

## Deployment (Optional)

- [ ] Update `deploy.sh` configuration
  - [ ] Set `PROJECT_ID`
  - [ ] Set `REGION`
  - [ ] Set `DATASET_ID`
  - [ ] Set `TABLE_ID`

- [ ] Deploy to Cloud Functions
  - [ ] Run `./deploy.sh`
  - [ ] Deployment succeeded
  - [ ] Function appears in Cloud Functions console

- [ ] Test Cloud Function
  - [ ] `gcloud pubsub topics publish fb-ads-topic --message="test"`
  - [ ] Check logs: `gcloud functions logs read fetchFbAdsToBigQuery --limit=50`
  - [ ] Verified data inserted

- [ ] Set up Cloud Scheduler
  - [ ] Created Pub/Sub topic: `fb-ads-topic`
  - [ ] Created scheduler job: `daily-fb-ads-sync`
  - [ ] Schedule: _______________ (e.g., "0 9 * * *")
  - [ ] Timezone: _______________
  - [ ] Manually triggered job to test
  - [ ] Verified successful execution

## Monitoring Setup

- [ ] Set up log-based alerts
  - [ ] Error alert configured
  - [ ] Notification channel: _______________

- [ ] Create BigQuery monitoring queries
  - [ ] Data freshness query saved
  - [ ] Daily summary query saved

- [ ] Set up dashboard (optional)
  - [ ] Looker Studio / Data Studio dashboard created
  - [ ] Shared with stakeholders

## Documentation & Handoff

- [ ] Document client-specific configurations
  - [ ] Account IDs documented
  - [ ] Schedule documented
  - [ ] Contact information: _______________

- [ ] Share access with team
  - [ ] GCP project access granted to: _______________
  - [ ] BigQuery access granted to: _______________
  - [ ] Documentation shared with: _______________

- [ ] Schedule follow-up
  - [ ] Monitor for 7 days
  - [ ] Follow-up date: _______________
  - [ ] Verify data quality with client

## Configuration Summary (for reference)

Fill this out when setup is complete:

```
Client: _______________
GCP Project: _______________
BigQuery Table: _______________._______________._______________
Facebook Accounts: _______________, _______________, _______________
Schedule: _______________ (e.g., daily at 9 AM UTC)
Token Type: [ ] User Token [ ] System User Token
Token Expires: _______________ (if applicable)
Deployed: [ ] Yes [ ] No (local only)
```

## Notes

Use this space for any client-specific notes or special configurations:

```
_______________________________________________________________________________
_______________________________________________________________________________
_______________________________________________________________________________
_______________________________________________________________________________
_______________________________________________________________________________
```

## Sign-Off

- [ ] Setup complete and tested
- [ ] Client notified
- [ ] Documentation complete

**Completed by:** _______________
**Date:** _______________
**Sign-off:** _______________
