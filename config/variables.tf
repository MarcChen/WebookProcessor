variable "github_owner" {
  description = "The GitHub owner (user or organization) that owns the repository."
  type        = string
  default     = "MarcChen"
}

variable "github_repository" {
  description = "The repository name where secrets will be created."
  type        = string
  default     = "WebookProcessor"
}

variable "gmail_service_account_key" {
  description = "Gmail service account key JSON."
  type        = string
}

variable "gmail_user_email" {
  description = "Gmail user email to impersonate."
  type        = string
}

variable "gmail_pubsub_topic" {
  description = "Gmail Pub/Sub topic name."
  type        = string
}

variable "gmail_refresh_token" {
  description = "Gmail refresh token."
  type        = string
}

variable "gmail_client_id" {
  description = "Gmail client ID."
  type        = string
}

variable "gmail_client_secret" {
  description = "Gmail client secret."
  type        = string
}

variable "simple_trigger_token" {
  description = "Token for the Simple SMS Trigger."
  type        = string
}
