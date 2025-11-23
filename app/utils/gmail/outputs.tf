output "pubsub_topic_full_name" {
  description = "Full name of the Pub/Sub topic (use this for Gmail watch setup)"
  value       = google_pubsub_topic.gmail_notifications.id
}

output "pubsub_topic_name" {
  description = "Name of the Pub/Sub topic"
  value       = google_pubsub_topic.gmail_notifications.name
}

output "service_account_email" {
  description = "Email of the service account"
  value       = google_service_account.gmail_webhook_sa.email
}

output "service_account_key" {
  description = "Base64-encoded service account key (sensitive - store in GitHub secrets)"
  value       = google_service_account_key.gmail_webhook_key.private_key
  sensitive   = true
}

output "next_steps" {
  description = "Instructions for next steps"
  value       = <<-EOT
    Next Steps:
    1. Save the service account key:
       terraform output -raw service_account_key | base64 -d > gmail-service-account.json

    2. Add to GitHub Secrets (base64-encoded for env var):
       - Name: GMAIL_SERVICE_ACCOUNT_KEY
       - Value: Run 'terraform output -raw service_account_key' (already base64-encoded)

    3. Set environment variables:
       - GMAIL_USER_EMAIL: Your Gmail address to watch
       - GMAIL_PUBSUB_TOPIC: ${google_pubsub_topic.gmail_notifications.id}

    4. Run the renewal script to establish initial watch:
       python renew_gmail_watch.py

    5. Test by sending an email to the watched account
  EOT
}
