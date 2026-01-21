# =============================================================================
# Terraform Configuration
# =============================================================================

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Uncomment to use GCS backend for state
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "knowledge-agent"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Enable Required APIs
# =============================================================================

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "aiplatform.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# =============================================================================
# Artifact Registry (for Docker images)
# =============================================================================

resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.service_name
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

# =============================================================================
# Service Account for Cloud Run
# =============================================================================

resource "google_service_account" "cloud_run" {
  account_id   = "${var.service_name}-runner"
  display_name = "Knowledge Agent Cloud Run Service Account"
}

# Grant Vertex AI access
resource "google_project_iam_member" "vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Grant Secret Manager access
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# =============================================================================
# Secrets in Secret Manager
# =============================================================================

resource "google_secret_manager_secret" "github_app_id" {
  secret_id = "${var.service_name}-github-app-id"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "github_app_private_key" {
  secret_id = "${var.service_name}-github-app-private-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "github_app_installation_id" {
  secret_id = "${var.service_name}-github-app-installation-id"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "github_webhook_secret" {
  secret_id = "${var.service_name}-github-webhook-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# =============================================================================
# Workload Identity Federation (for GitHub Actions)
# =============================================================================

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository_owner == '${var.github_owner}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Service account for GitHub Actions deployments
resource "google_service_account" "github_actions" {
  account_id   = "${var.service_name}-deployer"
  display_name = "GitHub Actions Deployer"
}

# Allow GitHub Actions to impersonate the service account
resource "google_service_account_iam_member" "github_actions_wif" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.github_repo}"
}

# Grant deployer permissions
resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "deployer_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "deployer_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

# =============================================================================
# Cloud Run Service
# =============================================================================

resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}/${var.service_name}:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      env {
        name  = "KNOWLEDGE_REPO"
        value = var.knowledge_repo
      }

      env {
        name  = "KNOWLEDGE_BRANCH"
        value = var.knowledge_branch
      }

      env {
        name = "GITHUB_APP_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_app_id.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GITHUB_APP_PRIVATE_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_app_private_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GITHUB_APP_INSTALLATION_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_app_installation_id.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GITHUB_WEBHOOK_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_webhook_secret.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.repo,
  ]

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# Allow unauthenticated access (or use IAP)
resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.enable_iap ? 0 : 1

  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# WIF for Knowledge Repo (for clustering workflow)
# =============================================================================

# Allow the knowledge repo to also use WIF for the clustering workflow
resource "google_service_account" "knowledge_repo_actions" {
  account_id   = "${var.service_name}-clusterer"
  display_name = "Knowledge Repo Clustering Service Account"
}

# Allow knowledge repo GitHub Actions to impersonate
resource "google_service_account_iam_member" "knowledge_repo_wif" {
  service_account_id = google_service_account.knowledge_repo_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.knowledge_repo}"
}

# Grant Vertex AI access for Gemini
resource "google_project_iam_member" "knowledge_repo_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.knowledge_repo_actions.email}"
}

# Grant Secret Manager access (for GitHub App credentials)
resource "google_project_iam_member" "knowledge_repo_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.knowledge_repo_actions.email}"
}
