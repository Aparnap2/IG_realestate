# Instagram Webhook 405 Error - Fix Guide

## Problem Identified

**Error:** `INFO: 2a03:2880:31ff:4:::0 - "POST / HTTP/1.1" 405 Method Not Allowed`

**Root Cause:** Instagram is sending POST webhook events to the root path `/` instead of `/webhook`. The server only had a `GET /` endpoint, causing the 405 Method Not Allowed error.

## Solution Applied

### Task 1: Added POST Handler for Root Path ✅
- Added `@app.post("/")` endpoint that redirects to the main webhook handler
- This handles Instagram webhooks sent to the root path (common misconfiguration)

### Task 2: Enhanced GET Root Path for Verification ✅
- Modified `@app.get("/")` to detect webhook verification requests
- Checks for `hub.mode=subscribe` query parameter
- Handles verification at both `/` and `/webhook` paths

### Task 3: Improved Logging ✅
- Added warnings when webhooks are received at root path
- Provides helpful tips to configure the correct webhook URL
- Better debugging information for troubleshooting

## Changes Made

**File:** `instagram_webhook_server.py`

### 1. Root GET Endpoint (Handles Both Info & Verification)
```python
@app.get("/")
async def root(request: Request):
    """Root endpoint - handles both info requests and webhook verification"""
    # Check if this is a webhook verification request
    if request.query_params.get("hub.mode") == "subscribe":
        # Handle verification at root path
        # Returns challenge token to Instagram
    
    # Otherwise return normal API info
```

### 2. Root POST Endpoint (Handles Webhook Events)
```python
@app.post("/")
async def root_webhook(request: Request):
    """Handle Instagram webhooks sent to root path"""
    print("⚠️  Webhook received at root path '/' - redirecting to webhook handler")
    return await receive_instagram_webhook(request)
```

## Testing Instructions

### Test 1: Verify the Server Starts
```bash
cd /home/aparna/Desktop/IG_realestate
python instagram_webhook_server.py
```

Expected output:
```
🔧 Instagram Webhook Server Configuration:
   Verify Token: ✅ Set
   Page Access Token: ✅ Set (or ❌ Missing)
🚀 Starting AAA Real Estate Instagram DM Automation Server
```

### Test 2: Test Root Path POST (Simulating Instagram)
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_123"},
        "message": {"text": "Looking for 2BHK in Miami, budget $350k"}
      }]
    }]
  }'
```

Expected: Should process successfully (no 405 error)

### Test 3: Test Webhook Verification at Root
```bash
curl "http://localhost:8000/?hub.mode=subscribe&hub.verify_token=aaa_real_estate_verify_token_2025&hub.challenge=12345"
```

Expected: Should return `12345`

### Test 4: Test Standard Webhook Path
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_456"},
        "message": {"text": "3BHK in Miami Beach, budget $800k"}
      }]
    }]
  }'
```

Expected: Should process successfully

## Instagram Webhook Configuration

### Option 1: Configure to Use Root Path (Current Fix Supports This)
In Meta App Dashboard:
- Webhook URL: `https://yourdomain.com/`
- Verify Token: `aaa_real_estate_verify_token_2025`

### Option 2: Configure to Use /webhook Path (Recommended)
In Meta App Dashboard:
- Webhook URL: `https://yourdomain.com/webhook`
- Verify Token: `aaa_real_estate_verify_token_2025`

**Both options now work!** The fix handles webhooks at both paths.

## Alignment with PRD

This fix maintains full PRD compliance:

✅ **Instagram DM Capture** - Webhook receives messages at both `/` and `/webhook`
✅ **AI Lead Qualification** - Extracts budget, location, property type, timeline
✅ **Property Matching** - Queries database for relevant listings
✅ **Intelligent Scoring** - Scores leads 0-1 based on qualification criteria
✅ **Smart Routing** - Routes to Scheduler (>0.7) or Follow-up (≤0.7)
✅ **HITL for High-Value** - Human review for leads >$500k budget
✅ **Auto-Response** - Sends contextual replies via Instagram

## Next Steps

1. **Restart the server** with the fix applied
2. **Test with real Instagram messages** - should now work without 405 errors
3. **Monitor logs** for successful webhook processing
4. **Verify auto-responses** are sent back to Instagram users

## Troubleshooting

### If you still get 405 errors:
1. Check server logs for the exact path being hit
2. Verify Instagram webhook configuration in Meta App Dashboard
3. Ensure the server is accessible from Instagram's IP ranges
4. Check firewall/proxy settings

### If verification fails:
1. Verify `INSTAGRAM_VERIFY_TOKEN` matches in both:
   - `backend/.env` file
   - Meta App Dashboard webhook settings
2. Check server logs for token mismatch details

## Production Deployment Checklist

- [ ] Update webhook URL in Meta App Dashboard to production domain
- [ ] Ensure `INSTAGRAM_VERIFY_TOKEN` is set in production environment
- [ ] Ensure `META_PAGE_ACCESS_TOKEN` is set in production environment
- [ ] Test webhook verification with production URL
- [ ] Test real Instagram message flow
- [ ] Monitor logs for successful processing
- [ ] Verify auto-responses are sent

## Support

If issues persist:
1. Check server logs: `tail -f logs/instagram_webhook.log`
2. Test with `/test` endpoint to verify backend processing works
3. Verify Supabase and Redis connections are healthy
4. Check Instagram API permissions in Meta App Dashboard
