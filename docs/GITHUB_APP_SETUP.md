# GitHub App Setup for Knowledge Contributions

This guide explains how to set up a GitHub App to allow the Knowledge Agent to create PRs on behalf of users.

## Why a GitHub App?

- **No API keys** - Uses JWT authentication with a private key
- **Fine-grained permissions** - Only needs access to specific repos
- **User attribution** - PRs show who contributed the knowledge
- **Audit trail** - All changes go through PR review

## Step 1: Create a GitHub App

1. Go to **Settings** → **Developer settings** → **GitHub Apps** → **New GitHub App**
2. Fill in the details:
   - **Name**: `Knowledge Agent` (or your preferred name)
   - **Homepage URL**: Your app's URL (can be localhost for dev)
   - **Webhook**: Uncheck "Active" (not needed)

3. Set **Permissions**:
   - **Repository permissions**:
     - Contents: Read & Write (to create/update files)
     - Pull requests: Read & Write (to create PRs)
     - Metadata: Read-only (required)

4. **Where can this GitHub App be installed?**: Select "Only on this account" for private use

5. Click **Create GitHub App**

## Step 2: Generate a Private Key

1. On the App's settings page, scroll to **Private keys**
2. Click **Generate a private key**
3. A `.pem` file will be downloaded - keep this secure!

## Step 3: Install the App

1. On the App's settings page, click **Install App** in the sidebar
2. Select the account/organization
3. Choose **Only select repositories** and select your knowledge base repo(s)
4. Click **Install**
5. Note the **Installation ID** from the URL (e.g., `/installations/12345678`)

## Step 4: Configure Environment Variables

Add these to your `.env` file:

```bash
# GitHub App credentials
GITHUB_APP_ID=123456
GITHUB_APP_INSTALLATION_ID=12345678
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...your private key content...
-----END RSA PRIVATE KEY-----"

# Knowledge base repository (org/repo format)
KNOWLEDGE_REPO=your-org/knowledge-base

# Target branch for PRs (optional, defaults to repo's default branch)
# Use "dev" for local testing, omit or set to "main" for production
KNOWLEDGE_BRANCH=dev
```

### Encoding the Private Key

For easier handling, you can base64-encode the private key:

```bash
# Encode
cat your-app.private-key.pem | base64 | tr -d '\n'

# Then use in .env:
GITHUB_APP_PRIVATE_KEY=LS0tLS1CRUdJTi...base64-encoded-key...
```

The backend will automatically detect and decode base64-encoded keys.

## Step 5: Create the Knowledge Base Repository

1. Create a new repository (e.g., `knowledge-base`)
2. Add an initial README or note
3. Make sure the GitHub App is installed on this repo

## Testing

1. Start the backend: `make backend-local`
2. Check GitHub config: `curl http://localhost:8000/api/contribute` (should return error about missing fields, not "not configured")
3. Try contributing a note through the UI

## Troubleshooting

### "GitHub App not configured"
- Check all three environment variables are set
- Verify the private key format (should start with `-----BEGIN`)

### "Resource not accessible by integration"
- The App doesn't have access to the repo
- Go to App settings → Install App → Configure → Add the repo

### "Reference already exists"
- A branch with that name already exists
- This shouldn't happen with timestamped branch names

## Production Deployment

For Cloud Run deployment:
1. Store the private key in Secret Manager
2. Mount it as an environment variable or file
3. Set `KNOWLEDGE_REPO` to your production repo

## Security Notes

- Never commit the private key to git
- Use Secret Manager in production
- The App only has access to repos you explicitly grant
- All PRs require review before merging
