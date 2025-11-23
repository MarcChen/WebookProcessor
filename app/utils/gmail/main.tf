terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable Gmail API
resource "google_project_service" "gmail_api" {
  service            = "gmail.googleapis.com"
  disable_on_destroy = false
}

# Enable Pub/Sub API
resource "google_project_service" "pubsub_api" {
  service            = "pubsub.googleapis.com"
  disable_on_destroy = false
}

# Create Pub/Sub topic for Gmail push notifications
resource "google_pubsub_topic" "gmail_notifications" {
  name = var.pubsub_topic_name

  depends_on = [google_project_service.pubsub_api]
}

# Create Pub/Sub subscription with push configuration
resource "google_pubsub_subscription" "gmail_push_subscription" {
  name  = "${var.pubsub_topic_name}-subscription"
  topic = google_pubsub_topic.gmail_notifications.name

  # Push configuration to your webhook endpoint
  push_config {
    push_endpoint = var.webhook_endpoint

    # Use OIDC token for authentication
    oidc_token {
      service_account_email = google_service_account.gmail_webhook_sa.email
    }
  }

  ack_deadline_seconds = 20

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  depends_on = [google_project_service.pubsub_api]
}

# Service account for Gmail webhook operations
resource "google_service_account" "gmail_webhook_sa" {
  account_id   = "gmail-webhook-sa"
  display_name = "Gmail Webhook Service Account"
  description  = "Service account for Gmail push notifications and watch renewal"
}

# Grant Gmail API special service account permission to publish to Pub/Sub topic
resource "google_pubsub_topic_iam_member" "gmail_publisher" {
  topic  = google_pubsub_topic.gmail_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:gmail-api-push@system.gserviceaccount.com"
}

# Grant our service account permission to publish to topic
resource "google_pubsub_topic_iam_member" "sa_publisher" {
  topic  = google_pubsub_topic.gmail_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.gmail_webhook_sa.email}"
}

# Grant our service account permission to subscribe
resource "google_pubsub_subscription_iam_member" "sa_subscriber" {
  subscription = google_pubsub_subscription.gmail_push_subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.gmail_webhook_sa.email}"
}



# Create service account key for GitHub Actions
resource "google_service_account_key" "gmail_webhook_key" {
  service_account_id = google_service_account.gmail_webhook_sa.name
}
