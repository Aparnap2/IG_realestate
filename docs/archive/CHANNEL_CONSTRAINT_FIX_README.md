# Channel Constraint Fix for IG Real Estate Application

## Problem Description

The application was experiencing a database constraint violation error with the `leads_channel_check` constraint when trying to update lead records. The error occurred because:

1. The database had a `leads_channel_check` constraint that wasn't documented in the schema files
2. The application was setting `"channel": "instagram"` in lead data
3. The constraint definition was missing from the `CREATE_TABLES.sql` file
4. There was no validation in the application code to prevent invalid channel values

## Solution Overview

This fix addresses the issue by:

1. **Documenting the constraint** in `CREATE_TABLES.sql`
2. **Creating a migration script** to ensure database schema consistency
3. **Adding validation** in `supabase_client.py` to prevent invalid channel values before database operations
4. **Providing test scripts** to verify the fix works correctly

## Files Modified/Created

### 1. Schema Files
- `CREATE_TABLES.sql` - Added the missing constraint definition
- `backend/scripts/add_channel_constraint.sql` - Migration script for existing databases

### 2. Application Code
- `backend/utils/supabase_client.py` - Added channel validation in `save_lead` and `save_or_update_lead` functions

### 3. Testing & Verification
- `check_channel_constraint.sql` - Script to inspect the current constraint in the database
- `test_channel_constraint_fix.py` - Comprehensive test script to verify the fix

## Implementation Details

### Constraint Definition

The `leads_channel_check` constraint ensures the `channel` field only contains valid values:

```sql
CHECK (channel IN ('instagram', ' ', 'web', 'email', ' '))
```

### Application Validation

Before any database operation, the application now validates the channel value:

```python
# Validate channel value before database operations
if "channel" in normalized_lead:
    valid_channels = {'instagram', ' ', 'web', 'email', ' '}
    if normalized_lead["channel"] not in valid_channels:
        logger.warning(f"Invalid channel value '{normalized_lead['channel']}' for instagram_id {instagram_id}. Defaulting to 'instagram'")
        normalized_lead["channel"] = "instagram"
else:
    # Ensure channel has a default value
    normalized_lead["channel"] = "instagram"
```

## Deployment Instructions

### Step 1: Apply Database Migration

Run the migration script in your Supabase SQL Editor:

```sql
-- Run the contents of backend/scripts/add_channel_constraint.sql
```

This script will:
- Drop any existing `leads_channel_check` constraint (to avoid conflicts)
- Add the new constraint with proper channel values
- Update any existing records with invalid channel values to 'instagram'
- Verify the constraint was added successfully

### Step 2: Update Application Code

The changes to `backend/utils/supabase_client.py` are already in place. The application will now:

- Validate channel values before database operations
- Default invalid or missing channel values to 'instagram'
- Log warnings when invalid values are encountered

### Step 3: Verify the Fix

Run the test script to verify everything is working:

```bash
python test_channel_constraint_fix.py
```

This will test:
- Channel validation in both `save_lead` and `save_or_update_lead` functions
- Database constraint enforcement
- Proper handling of various channel scenarios

## Troubleshooting

### If you still get constraint violations:

1. **Check the current constraint**:
   ```sql
   -- Run check_channel_constraint.sql
   ```

2. **Verify the migration was applied**:
   ```sql
   SELECT conname, pg_get_constraintdef(oid) 
   FROM pg_constraint 
   WHERE conrelid = 'leads'::regclass AND conname = 'leads_channel_check';
   ```

3. **Check for existing invalid data**:
   ```sql
   SELECT instagram_id, name, channel, created_at
   FROM leads 
   WHERE channel NOT IN ('instagram', ' ', 'web', 'email', ' ')
   LIMIT 10;
   ```

### If the application still fails:

1. **Check the logs** for any validation warnings
2. **Ensure the latest code** is deployed
3. **Run the test script** to identify specific issues

## Valid Channel Values

The constraint and validation only allow these channel values:

- `instagram` - Default value for Instagram DM leads
- ` ` -   messaging leads
- `web` - Website form leads
- `email` - Email leads
- ` ` -  /text message leads

Any other value will be automatically converted to 'instagram' with a warning logged.

## Future Considerations

1. **Extending channel values**: To add new valid channels, update both the database constraint and the `valid_channels` set in the Python code
2. **Channel-specific logic**: Consider adding channel-specific business logic if needed
3. **Monitoring**: Monitor logs for warnings about invalid channel values to identify data quality issues

## Testing

The fix includes comprehensive testing that verifies:

- ✅ Valid channels are accepted
- ✅ Invalid channels are defaulted to 'instagram'
- ✅ Missing channels are set to 'instagram'
- ✅ Database constraint enforcement works
- ✅ Both save functions handle validation correctly

Run `python test_channel_constraint_fix.py` to execute all tests.