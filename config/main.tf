terraform {
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 5.0"
    }
  }
}

provider "github" {
  owner = var.github_owner
}

locals {
  raw_secrets = {
    GMAIL_SERVICE_ACCOUNT_KEY = var.gmail_service_account_key
    GMAIL_USER_EMAIL          = var.gmail_user_email
    GMAIL_PUBSUB_TOPIC        = var.gmail_pubsub_topic
    GMAIL_REFRESH_TOKEN       = var.gmail_refresh_token
    GMAIL_CLIENT_ID           = var.gmail_client_id
    GMAIL_CLIENT_SECRET       = var.gmail_client_secret
    SIMPLE_TRIGGER_TOKEN      = var.simple_trigger_token
  }

  secrets = { for k, v in local.raw_secrets : k => v if v != "" }
}

resource "github_actions_secret" "repo_secrets" {
  for_each        = local.secrets
  repository      = var.github_repository
  secret_name     = each.key
  plaintext_value = each.value
}
