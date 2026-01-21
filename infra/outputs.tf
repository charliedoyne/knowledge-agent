# =============================================================================
# Outputs
# =============================================================================

output "service_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.app.uri
}

output "webhook_url" {
  description = "GitHub webhook URL (configure in GitHub App settings)"
  value       = "${google_cloud_run_v2_service.app.uri}/api/github-webhook"
}

output "artifact_registry" {
  description = "Artifact Registry repository for Docker images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}"
}

output "wif_provider" {
  description = "Workload Identity Provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "Service account email for GitHub Actions deployment"
  value       = google_service_account.github_actions.email
}

output "clusterer_service_account" {
  description = "Service account email for knowledge repo clustering"
  value       = google_service_account.knowledge_repo_actions.email
}

# =============================================================================
# Secret IDs (for manual population)
# =============================================================================

output "secret_ids" {
  description = "Secret Manager secret IDs to populate"
  value = {
    github_app_id             = google_secret_manager_secret.github_app_id.secret_id
    github_app_private_key    = google_secret_manager_secret.github_app_private_key.secret_id
    github_app_installation_id = google_secret_manager_secret.github_app_installation_id.secret_id
    github_webhook_secret     = google_secret_manager_secret.github_webhook_secret.secret_id
  }
}

# =============================================================================
# GitHub Actions Variables (copy to repo settings)
# =============================================================================

output "github_actions_vars" {
  description = "Variables to set in GitHub Actions repository settings"
  value = {
    GCP_PROJECT_ID      = var.project_id
    GCP_REGION          = var.region
    WIF_PROVIDER        = google_iam_workload_identity_pool_provider.github.name
    WIF_SERVICE_ACCOUNT = google_service_account.github_actions.email
    SERVICE_NAME        = var.service_name
  }
}

output "knowledge_repo_vars" {
  description = "Variables to set in knowledge repo GitHub Actions settings"
  value = {
    GCP_PROJECT_ID      = var.project_id
    GCP_REGION          = var.region
    WIF_PROVIDER        = google_iam_workload_identity_pool_provider.github.name
    WIF_SERVICE_ACCOUNT = google_service_account.knowledge_repo_actions.email
  }
}
