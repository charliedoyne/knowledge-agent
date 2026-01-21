# Deployment Guide

This guide covers deploying the Knowledge Sharing Agent to Google Cloud Run.

## Prerequisites

- Google Cloud project with billing enabled
- Terraform installed locally
- `gcloud` CLI installed and authenticated
- GitHub repository for the agent code
- GitHub repository for the knowledge base

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Setup                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Agent Repo (this repo)          Knowledge Repo                  │
│  ├── .github/workflows/          ├── .github/workflows/          │
│  │   └── deploy.yaml             │   └── update-clusters.yaml   │
│  ├── infra/                      ├── note1.md                    │
│  │   └── *.tf                    ├── note2.md                    │
│  ├── backend/                    └── clusters.json (auto)        │
│  └── frontend/                                                   │
│                                                                  │
│         │                                  │                     │
│         ▼                                  ▼                     │
│  ┌─────────────┐                  ┌─────────────────┐           │
│  │ Cloud Run   │◀────webhook─────│  GitHub App     │           │
│  │ Service     │                  │  (PRs, webhooks)│           │
│  └─────────────┘                  └─────────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Step 1: Configure Terraform Variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
project_id     = "your-gcp-project-id"
region         = "europe-west2"
github_owner   = "your-github-username"
github_repo    = "my_agent"
knowledge_repo = "your-github-username/knowledge-base"
```

## Step 2: Deploy Infrastructure

```bash
cd infra

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply (creates all resources)
terraform apply
```

This creates:
- Cloud Run service
- Artifact Registry for Docker images
- Secret Manager secrets (empty, to be populated)
- Workload Identity Federation for GitHub Actions
- Service accounts with proper permissions

## Step 3: Populate Secrets

After Terraform completes, populate the secrets with your GitHub App credentials:

```bash
# Get secret IDs from Terraform output
terraform output secret_ids

# Add your GitHub App credentials
echo -n "YOUR_APP_ID" | gcloud secrets versions add knowledge-agent-github-app-id --data-file=-

# For the private key, base64 encode it first
cat your-app.private-key.pem | base64 | tr -d '\n' | gcloud secrets versions add knowledge-agent-github-app-private-key --data-file=-

echo -n "YOUR_INSTALLATION_ID" | gcloud secrets versions add knowledge-agent-github-app-installation-id --data-file=-

# Generate a webhook secret
openssl rand -hex 32 | gcloud secrets versions add knowledge-agent-github-webhook-secret --data-file=-
```

## Step 4: Configure GitHub Actions (Agent Repo)

Get the values from Terraform output:

```bash
terraform output github_actions_vars
```

In your agent repo, go to **Settings > Secrets and variables > Actions > Variables** and add:

| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_REGION` | `europe-west2` |
| `WIF_PROVIDER` | From Terraform output |
| `WIF_SERVICE_ACCOUNT` | From Terraform output |
| `SERVICE_NAME` | `knowledge-agent` |

## Step 5: Deploy the Application

Push to main branch to trigger deployment:

```bash
git add .
git commit -m "Add deployment configuration"
git push origin main
```

Or trigger manually from GitHub Actions tab.

After deployment, get the service URL:

```bash
gcloud run services describe knowledge-agent --region europe-west2 --format 'value(status.url)'
```

## Step 6: Configure GitHub Webhook

This is the crucial step for real-time PR notifications!

1. Go to your GitHub App settings: **Settings > Developer settings > GitHub Apps > Your App**

2. Scroll to **Webhook** section

3. Configure:
   - **Webhook URL**: `https://YOUR-CLOUD-RUN-URL/api/github-webhook`
   - **Content type**: `application/json`
   - **Secret**: The same value you put in Secret Manager for `github-webhook-secret`

4. Under **Subscribe to events**, select:
   - **Pull requests** (for PR merge/close notifications)
   - **Pushes** (for direct push notifications)

5. Ensure **Active** is checked

6. Click **Save changes**

### Testing the Webhook

You can test the webhook with:

```bash
# Get webhook URL
echo "$(terraform output -raw service_url)/api/github-webhook"

# Send a test ping (GitHub does this automatically)
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen": "Testing webhook"}'
```

## Step 7: Set Up Knowledge Repo Clustering

Copy the clustering workflow to your knowledge repo:

```bash
# In your knowledge repo
mkdir -p .github/workflows
cp /path/to/agent/docs/knowledge-repo-workflow.yaml .github/workflows/update-clusters.yaml
```

Get the values from Terraform output:

```bash
terraform output knowledge_repo_vars
```

In your knowledge repo, go to **Settings > Secrets and variables > Actions**:

**Variables:**
| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_REGION` | `europe-west2` |
| `WIF_PROVIDER` | From Terraform output |
| `WIF_SERVICE_ACCOUNT` | Clusterer service account from output |

**Secrets:**
| Secret | Value |
|--------|-------|
| `GITHUB_APP_ID` | Your GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY` | Base64-encoded private key |
| `GITHUB_APP_INSTALLATION_ID` | Your installation ID |

## Verification Checklist

- [ ] Cloud Run service is running: `gcloud run services list`
- [ ] Can access the app at the Cloud Run URL
- [ ] GitHub Actions can deploy (check workflow runs)
- [ ] Webhook is receiving events (check GitHub App > Advanced > Recent Deliveries)
- [ ] Clustering workflow runs when notes change
- [ ] PRs created from the app show up in GitHub
- [ ] PR merges refresh the knowledge base

## Troubleshooting

### Webhook not working

1. Check GitHub App > Advanced > Recent Deliveries for errors
2. Verify the webhook secret matches
3. Check Cloud Run logs: `gcloud run services logs read knowledge-agent`

### Deployment failing

1. Check GitHub Actions logs
2. Verify WIF is configured correctly
3. Ensure service account has required permissions

### Notes not loading

1. Check KNOWLEDGE_REPO is set correctly
2. Verify GitHub App has access to the knowledge repo
3. Check Cloud Run logs for fetch errors

## Architecture Details

### Authentication Flow

```
GitHub Actions ──WIF──▶ GCP Service Account ──▶ Cloud Run Deploy
                                              ──▶ Gemini API
                                              ──▶ Secret Manager
```

### Webhook Flow

```
PR Merged ──▶ GitHub ──webhook──▶ Cloud Run ──▶ Refresh Cache
                                           ──▶ Update PR Status
```

### Clustering Flow

```
Note Changed ──▶ GitHub Actions ──WIF──▶ Gemini ──▶ clusters.json
```
