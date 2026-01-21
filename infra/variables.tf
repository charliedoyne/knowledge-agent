# =============================================================================
# Required Variables
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Run"
  type        = string
  default     = "europe-west2"
}

variable "github_owner" {
  description = "GitHub owner/org for the agent repository"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name for the agent"
  type        = string
}

variable "knowledge_repo" {
  description = "GitHub repository for knowledge base (format: owner/repo)"
  type        = string
}

# =============================================================================
# Optional Variables
# =============================================================================

variable "service_name" {
  description = "Name for the Cloud Run service"
  type        = string
  default     = "knowledge-agent"
}

variable "knowledge_branch" {
  description = "Branch to use for knowledge base"
  type        = string
  default     = "main"
}

variable "enable_iap" {
  description = "Enable Identity-Aware Proxy for authentication"
  type        = bool
  default     = false
}

variable "iap_allowed_domain" {
  description = "Domain allowed to access the app (e.g., datatonic.com)"
  type        = string
  default     = ""
}
