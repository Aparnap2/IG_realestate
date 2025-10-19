# Instagram Webhook Testing Guide

## Problem Identified
Your system is skipping messages from your other Instagram account because they are being flagged as "echo" messages. This happens when Meta's API marks messages as echoes (typically when they're sent by the same page/account).

## Solution: Debug Mode for Testing

### Step 1: Enable Echo Message Processing
Set this environment variable to allow processing of echo messages during testing:

```bash
export ALLOW_ECHO_MESSAGES=true
```

### Step 2: Restart the Backend Server
The backend needs to be restarted to pick up the new environment variable:

```bash
# Stop the current backend (Ctrl+C in the terminal where it's running)
# Then restart it:
cd backend
source .venv/bin/activate
export ALLOW_ECHO_MESSAGES=true
python main.py
```

### Step 3: Run the Debug Script
Test the webhook processing locally:

```bash
python debug_webhook_messages.py
```

This will show you:
- Current environment settings
- Test with echo message payload
- Test with normal message payload
- Detailed response from the webhook

### Step 4: Set Up ngrok
Expose your local server to the internet:

```bash
# Install ngrok if you haven't already
# Ubuntu/Debian:
snap install ngrok

# Or download from https://ngrok.com/download

# Start ngrok to expose port 8000
ngrok http 8000
```

Copy the ngrok URL (e.g., `https://abc123.ngrok.io`) - you'll need this for Meta's dashboard.

### Step 5: Configure Meta Developer Dashboard

1. Go to your Meta Developer Dashboard
2. Select your Instagram App
3. Go to Webhooks section
4. Set the Callback URL to: `https://your-ngrok-url.ngrok.io/`
5. Set the Verify Token to: `aaa_real_estate_verify_token_2025`
6. Subscribe to these fields:
   - `messages`
   - `messaging_postbacks`
   - `messaging_optins`

### Step 6: Test with Your Other Instagram Account

1. Send a message from your other Instagram account to your business account
2. Check the backend logs - you should see detailed debugging information like:
   ```
   🔍 DEBUG MESSAGE DETAILS:
     - Sender ID: 123456789
     - Message Text: 'Hello from other account'
     - Message ID: msg_12345
     - Is Echo: True
     - Full messaging event: {...}
   ```

### Step 7: Monitor the Processing

The backend will now process echo messages and show:
- Message deduplication checks
- User profile fetching
- Lead processing results
- Response sending (if configured)

## Environment Variables for Testing

```bash
# Required for echo message processing
export ALLOW_ECHO_MESSAGES=true

# Skip signature verification in development
export ENVIRONMENT=development

# Your Meta credentials
export META_APP_SECRET=your_app_secret
export META_VERIFY_TOKEN=aaa_real_estate_verify_token_2025
export META_PAGE_ACCESS_TOKEN=your_page_access_token
export INSTAGRAM_ACCOUNT_ID=your_ig_account_id
```

## Troubleshooting

### Messages Still Being Skipped?
1. Check the backend logs for the "DEBUG MESSAGE DETAILS" section
2. Verify the message isn't being caught by the duplicate filter
3. Make sure `ALLOW_ECHO_MESSAGES=true` is set before starting the backend

### Signature Verification Issues?
In development mode, signature verification is automatically skipped if `ENVIRONMENT=development`.

### No Response from Bot?
Check these environment variables:
- `META_PAGE_ACCESS_TOKEN` - Must be valid
- `INSTAGRAM_ACCOUNT_ID` - Your Instagram account ID
- The bot needs proper permissions from Meta

## Production Deployment

**IMPORTANT**: Before going to production, disable echo message processing:

```bash
export ALLOW_ECHO_MESSAGES=false
# or simply unset it
unset ALLOW_ECHO_MESSAGES
```

This ensures only genuine user messages are processed in production.

## Debugging Commands

```bash
# Check current environment
env | grep -E "(ALLOW_ECHO|META_|ENVIRONMENT)"

# Test webhook health
curl http://localhost:8000/health

# Test webhook verification
curl "http://localhost:8000/?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=aaa_real_estate_verify_token_2025"

# Test webhook payload manually
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"object":"instagram","entry":[{"id":"123","messaging":[{"sender":{"id":"user123"},"message":{"text":"test"}}]}]}'
```

## Next Steps

Once you've confirmed messages are being processed correctly:

1. Test the complete lead qualification workflow
2. Verify responses are being sent back to Instagram
3. Check the database for lead entries
4. Monitor the agent processing in the logs
5. Test with the frontend dashboard

The system should now process messages from your other Instagram account without skipping them!