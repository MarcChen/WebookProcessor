variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "pubsub_topic_name" {
  description = "Name of the Pub/Sub topic for Gmail notifications"
  type        = string
  default     = "gmail-webhook-notifications"
}

variable "webhook_endpoint" {
  description = "The HTTPS endpoint where Gmail notifications will be pushed (e.g., https://your-app.onrender.com/webhook)"
  type        = string
}
