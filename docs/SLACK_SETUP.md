# Slack Integration Setup

This guide explains how to set up the Knowledge Agent as a Slack bot.

## Prerequisites

- A Slack workspace where you have permission to install apps
- The backend running and accessible (locally via ngrok, or deployed)

## Step 1: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Enter a name (e.g., "Knowledge Agent") and select your workspace
4. Click **Create App**

## Step 2: Configure Bot Permissions

1. In the left sidebar, go to **OAuth & Permissions**
2. Under **Scopes** → **Bot Token Scopes**, add:
   - `app_mentions:read` - To receive @mentions
   - `chat:write` - To send messages
   - `im:history` - To read DMs (if you want DM support)
   - `im:read` - To receive DM events

## Step 3: Enable Event Subscriptions

1. In the left sidebar, go to **Event Subscriptions**
2. Toggle **Enable Events** to On
3. For **Request URL**, enter your backend URL:
   - Local development: Use ngrok (see below)
   - Production: `https://your-backend-url/api/slack/events`
4. Under **Subscribe to bot events**, add:
   - `app_mention` - When someone @mentions the bot
   - `message.im` - Direct messages (optional)
5. Click **Save Changes**

## Step 4: Install the App

1. In the left sidebar, go to **Install App**
2. Click **Install to Workspace**
3. Authorize the app

## Step 5: Get Your Credentials

1. **Bot Token**: Go to **OAuth & Permissions** → Copy the **Bot User OAuth Token** (starts with `xoxb-`)
2. **Signing Secret**: Go to **Basic Information** → Under **App Credentials**, copy the **Signing Secret**

## Step 6: Configure Environment Variables

Add these to your `.env` file:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
```

## Local Development with ngrok

For local testing, you need a public URL. Use ngrok:

```bash
# Install ngrok (if not already installed)
brew install ngrok

# Start your backend
make backend-local

# In another terminal, start ngrok
ngrok http 8000
```

Copy the ngrok URL (e.g., `https://abc123.ngrok.io`) and use it as your Request URL in Slack:
`https://abc123.ngrok.io/api/slack/events`

## Testing

1. Invite the bot to a channel: `/invite @Knowledge Agent`
2. Mention the bot: `@Knowledge Agent how do I deploy to Cloud Run?`
3. The bot should respond with information from the knowledge base

## Troubleshooting

### "challenge" error
- Make sure your Request URL is correct and the backend is running
- Check that the `/api/slack/events` endpoint returns the challenge

### No response from bot
- Check the backend logs for errors
- Verify `SLACK_BOT_TOKEN` is set correctly
- Make sure the bot has been invited to the channel

### Signature verification failed
- Verify `SLACK_SIGNING_SECRET` is correct
- For local dev without a signing secret, the verification is skipped

## Health Check

Check if Slack integration is configured:

```bash
curl http://localhost:8000/api/slack/health
```

Response:
```json
{
  "status": "ok",
  "bot_token_configured": true,
  "signing_secret_configured": true
}
```
