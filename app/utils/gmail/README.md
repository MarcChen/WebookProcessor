# Gmail Webhook Integration

This directory contains the Terraform configuration and scripts for setting up Gmail push notifications via Google Cloud Pub/Sub.

## Overview

The Gmail webhook integration allows you to receive real-time notifications when new emails arrive in your Gmail inbox. Notifications are sent via Google Cloud Pub/Sub to your webhook endpoint, triggering workflows without processing email content.

## Prerequisites

1. **Google Cloud Project** with billing enabled (stays within free tier for normal email volumes)
2. **gcloud CLI** installed and authenticated
3. **Terraform** installed (>= 1.0)
4. **Webhook endpoint** (e.g., deployed on Render.com)

## Setup Instructions

### 1. Configure Terraform Variables

Copy the example tfvars file and edit it with your values:

```bash
cd gmail
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
project_id       = "your-gcp-project-id"
region           = "us-central1"
pubsub_topic_name = "gmail-webhook-notifications"
webhook_endpoint = "https://your-app.onrender.com/webhook"
```

### 2. Apply Terraform Configuration

```bash
terraform init
terraform plan
terraform apply
```

This will:
- Enable Gmail API and Pub/Sub API
- Create Pub/Sub topic and subscription
- Create service account with necessary permissions
- Generate service account key

### 3. Save Service Account Credentials

After Terraform apply, save the service account key:

```bash
# Save as JSON file (for local testing)
terraform output -raw service_account_key | base64 -d > gmail-service-account.json

# Get base64-encoded key (for GitHub secrets and env vars)
terraform output -raw service_account_key
```

### 4. Configure GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- **GMAIL_SERVICE_ACCOUNT_KEY**: Run `terraform output -raw service_account_key` (already base64-encoded)
- **GMAIL_USER_EMAIL**: Your Gmail address (e.g., `yourname@gmail.com`)
- **GMAIL_PUBSUB_TOPIC**: Run `terraform output pubsub_topic_full_name`

### 5. Enable Domain-Wide Delegation (Google Workspace ONLY)

If you're using a Google Workspace account:
1. Go to Google Admin Console → Security → API Controls → Domain-wide Delegation
2. Add the service account client ID (from service account details)
3. Add OAuth scope: `https://www.googleapis.com/auth/gmail.readonly`

### 5b. Personal Gmail Accounts (OAuth2)

For personal Gmail accounts (@gmail.com), you cannot use service account delegation. Instead, use OAuth2:

1. **Create OAuth Client**:
   - Go to GCP Console → APIs & Services → Credentials
   - Create Credentials → OAuth client ID → Web application
   - Add `https://developers.google.com/oauthplayground` to Authorized redirect URIs (for easy token generation)
   - Note the **Client ID** and **Client Secret**

2. **Get Refresh Token**:
   - Go to [OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
   - Click the gear icon (top right) → Check "Use your own OAuth credentials" → Enter Client ID & Secret
   - In "Select & authorize APIs", enter: `https://www.googleapis.com/auth/gmail.readonly`
   - Click "Authorize APIs" and login with your personal Gmail
   - Click "Exchange authorization code for tokens"
   - Copy the **Refresh Token**

3. **Configure Secrets**:
   Add these additional secrets to GitHub/Env:
   - `GMAIL_REFRESH_TOKEN`
   - `GMAIL_CLIENT_ID`
   - `GMAIL_CLIENT_SECRET`

   *Note: You still need `GMAIL_SERVICE_ACCOUNT_KEY` for Pub/Sub authentication.*

### 6. Establish Initial Watch

Run the renewal script locally to set up the initial watch:

```bash
# Set environment variables
export GMAIL_SERVICE_ACCOUNT_KEY="$(cat gmail-service-account.json | base64)"
export GMAIL_USER_EMAIL="your-email@gmail.com"
export GMAIL_PUBSUB_TOPIC="$(terraform output -raw pubsub_topic_full_name)"

# Run the renewal script
python renew_gmail_watch.py
```

You should see output confirming the watch was established with an expiration date ~7 days in the future.

### 7. Configure Application Environment

Add these variables to your `.env` file (for local development) or your hosting platform (e.g., Render.com):

```bash
GMAIL_SERVICE_ACCOUNT_KEY=<base64_encoded_key>
GMAIL_USER_EMAIL=your-email@gmail.com
GMAIL_PUBSUB_TOPIC=projects/YOUR_PROJECT/topics/gmail-webhook-notifications

# Optional: To trigger GitHub workflows on email
GMAIL_GITHUB_TOKEN=ghp_...
GMAIL_GITHUB_REPO=username/repo
GMAIL_GITHUB_WORKFLOW_ID=workflow.yml
```

## Automated Watch Renewal

The Gmail watch must be renewed every 7 days. This is automated via GitHub Actions:

- **Workflow file**: `.github/workflows/renew-gmail-watch.yml`
- **Schedule**: Runs every 6 days at 2 AM UTC
- **Manual trigger**: Can be triggered manually from GitHub Actions UI

The workflow uses the secrets you configured in step 4.

## Testing

### Test Terraform Setup

```bash
# Verify resources in GCP Console
gcloud pubsub topics list
gcloud pubsub subscriptions list
gcloud iam service-accounts list
```

### Test Watch Renewal

```bash
# Trigger GitHub workflow manually
gh workflow run renew-gmail-watch.yml

# Or run locally
python renew_gmail_watch.py
```

### Test Webhook Integration

1. Send a test email to your Gmail account
2. Check your webhook endpoint logs
3. Verify the `GmailWebhookProcessor` received the notification
4. Confirm workflow was triggered (if configured)

## Troubleshooting

### Watch Renewal Fails

- **Permission denied**: Ensure domain-wide delegation is enabled (Workspace accounts)
- **Invalid credentials**: Verify `GMAIL_SERVICE_ACCOUNT_KEY` is correctly base64-encoded
- **Topic not found**: Verify `GMAIL_PUBSUB_TOPIC` matches Terraform output

### No Notifications Received

- Check Pub/Sub subscription configuration in GCP Console
- Verify webhook endpoint is accessible (must be HTTPS)
- Check Gmail API quotas (should be well within limits)
- Review application logs for processing errors

### Service Account Authentication

For personal Gmail accounts, you must use the OAuth2 flow described in step 5b. The service account is ONLY used for Pub/Sub authentication in this case, while the OAuth2 tokens are used to authorize the Gmail API watch request.

## Cost Information

**Completely FREE** for typical email volumes:
- Gmail API: Free (no quota charges for push notifications)
- Pub/Sub: Free tier covers 10 GB/month + 10,000 operations/month
- Even if you exceed free tier: ~$0.40 per million operations

## Additional Resources

- [Gmail Push Notifications Documentation](https://developers.google.com/gmail/api/guides/push)
- [Google Cloud Pub/Sub Pricing](https://cloud.google.com/pubsub/pricing)
- [Service Account Authentication](https://cloud.google.com/iam/docs/service-accounts)
