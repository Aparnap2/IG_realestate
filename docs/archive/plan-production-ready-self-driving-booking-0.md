I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when absolutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

## Current State Summary

The codebase is a **real estate Instagram DM lead management system** with:

**Architecture**:
- FastAPI backend with LangGraph agent orchestration (Router → Qualifier → Scheduler → FollowUp)
- Redis for state persistence, caching, and circuit breaker patterns
- Supabase (PostgreSQL) with RLS policies for data storage
- Celery for async task processing
- Google Calendar API integration with basic freebusy queries
- HubSpot CRM integration for contact/deal management
- Immutable audit logging with blockchain-style hash chaining

**Current Capabilities**:
- Instagram comment-triggered DM funnels with keyword detection
- Lead qualification with progressive Q&A and temporal scoring
- Smart booking engine with readiness assessment
- Multi-channel communication manager (Instagram DM, SMS, email, WhatsApp - mostly placeholders)
- Calendar integration with tour optimization (TSP, travel time calculation)
- Redis-backed conversation state and query caching
- Compliance checking (Fair Housing, TCPA, GDPR)

**Key Gaps for "Self-Driving Booking Ops 2.0"**:
1. No idempotent calendar writes (no request IDs, write-audit store, ETag checks)
2. No explicit state machine for booking flow (intake → qualify → propose → confirm → write → reminders → reschedule/no-show)
3. No message UUID deduplication across channels
4. No multi-touch reminder system (T-24h, T-3h, T-30m with confirmation tracking)
5. No waitlist backfill on no-shows
6. No conflict handling with requery/replan
7. No observability panel (SLA tracking, conflict rate, idempotency reuse)
8. No reschedule lineage tracking

**Infrastructure Ready**:
- Redis client with circuit breaker, retry logic, graceful degradation ✅
- Celery for task scheduling ✅
- Audit logging with tamper detection ✅
- Multi-channel manager framework (needs WhatsApp/email webhook handlers) ✅
- Database schema with leads, properties, tour_schedules, audit_logs ✅

### Approach

Transform the existing Instagram DM lead system into a **Self-Driving Booking Ops 2.0** platform by:

1. **Adding idempotent calendar writes** with KSUID-based request IDs, write-audit store, and ETag validation
2. **Creating explicit state machine** for booking orchestration with deterministic transitions
3. **Implementing message bus** for multi-channel intake normalization with UUID deduplication
4. **Building multi-touch reminder system** with T-24h, T-3h, T-30m cadence and confirmation tracking
5. **Adding waitlist backfill** for no-show recovery with ranked candidates and guardrails
6. **Creating observability metrics** for SLA tracking, conflict rate, and Slack alerting
7. **Implementing reschedule flow** with idempotency key lineage

**Phased Approach**:
- **Phase 1**: Foundation (idempotent writes, state machine, message UUIDs)
- **Phase 2**: Reminders & Recovery (multi-touch reminders, reschedule, waitlist)
- **Phase 3**: Observability & Multi-Channel (metrics, Slack alerts, WhatsApp/email webhooks)

### Reasoning

I explored the codebase systematically:
1. Listed directory structure to understand project layout
2. Read core booking/scheduling files (`scheduler.py`, `smart_booking_engine.py`, `calendar_integration.py`, `scheduling_utils.py`)
3. Examined orchestration layer (`prd_compliant_workflow.py`, `workflow.py`, `state.py`)
4. Reviewed infrastructure (`redis_client.py`, `celery_app.py`, `booking_flow.py`, `multi_channel_manager.py`)
5. Analyzed data models (`lead.py`, `audit.py`, `CREATE_TABLES.sql`)
6. Checked webhook handling (`webhooks.py`) and configuration (`config.py`)

This gave me a complete picture of existing capabilities, integration points, and gaps to address.

## Mermaid Diagram

sequenceDiagram
    participant User as Lead
    participant Bus as MessageBus
    participant SM as BookingStateMachine
    participant Cache as SlotCacheManager
    participant Writer as IdempotentCalendarWriter
    participant Cal as GoogleCalendar
    participant Audit as booking_attempts DB
    participant Remind as ReminderScheduler
    participant Wait as WaitlistManager

    User->>Bus: Send message (IG/WhatsApp/Email)
    Bus->>Bus: Generate message_uuid
    Bus->>Bus: Check dedupe (Redis)
    Bus->>SM: Normalized message
    
    SM->>SM: State: INTAKE → QUALIFY
    Note over SM: Qualifier agent runs
    
    SM->>SM: State: QUALIFY → PROPOSE_SLOT
    SM->>Cache: get_cached_slots(location, service, buffers)
    alt Cache hit
        Cache-->>SM: Cached slots
    else Cache miss
        Cache->>Cal: Freebusy query
        Cal-->>Cache: Busy periods
        Cache->>Cache: Calculate free slots + apply buffer policy
        Cache->>Cache: Store in Redis (5min TTL)
        Cache-->>SM: Fresh slots
    end
    
    SM->>User: Propose N ranked slots
    User->>SM: Accept slot
    
    SM->>SM: State: PROPOSE_SLOT → CONFIRM
    SM->>SM: Generate idempotency_key (KSUID)
    SM->>Cache: revalidate_on_accept(slot_time)
    
    alt Available
        SM->>SM: State: CONFIRM → WRITE
        SM->>Writer: write_event(lead_id, slot, payload, key)
        
        Writer->>Audit: Check existing attempt by key
        alt Key exists
            Audit-->>Writer: Return stored event_id + ETag
            Writer-->>SM: Idempotent response (no-op)
        else New attempt
            Writer->>Cal: create_event(extendedProperties.idempotency_key)
            Cal-->>Writer: Event created (event_id, ETag)
            Writer->>Audit: Persist attempt (key, event_id, ETag, payload)
            Writer-->>SM: Write confirmed
        end
        
        SM->>SM: State: WRITE → REMINDERS
        SM->>Remind: schedule_reminders(event_id, lead_id, slot_time)
        Remind->>Remind: Schedule T-24h, T-3h, T-30m Celery tasks
        SM->>User: Confirmation with Meet link
        
        loop Reminder cadence
            Remind->>User: Send reminder (SMS/email/DM)
            User->>Remind: Confirm attendance
            Remind->>Cal: Update event.extendedProperties.confirmed_at
        end
        
        alt No confirmation at T-60m
            Remind->>User: Last-chance ping
            Remind->>Remind: Send Slack alert
            Remind->>SM: Mark no_show_predicted
            SM->>Wait: trigger_backfill(slot_time, service, location)
            Wait->>Wait: Query waitlist by fit_score
            Wait->>User: Contact waitlist candidates
        end
        
    else Conflict detected (ETag drift)
        Writer-->>SM: Conflict status
        SM->>SM: State: CONFIRM → PROPOSE_SLOT (replan)
        SM->>Cache: invalidate_cache(calendar_id)
        SM->>User: Slot unavailable, propose alternatives
        SM->>Remind: Send Slack alert (conflict)
    end
    
    alt User requests reschedule
        User->>SM: Reschedule request
        SM->>SM: State: RESCHEDULE
        SM->>Cal: Soft-cancel original event
        SM->>Audit: Link new key to parent_key
        SM->>SM: State: RESCHEDULE → PROPOSE_SLOT
    end

## Proposed File Changes

### backend/booking/booking_state_machine.py(NEW)

References: 

- backend/schemas/state.py(MODIFY)
- backend/utils/redis_client.py(MODIFY)

Create explicit state machine orchestrator for booking flow with states: `INTAKE`, `QUALIFY`, `PROPOSE_SLOT`, `CONFIRM`, `WRITE`, `REMINDERS`, `RESCHEDULE`, `NO_SHOW`, `WAITLIST_BACKFILL`. Implement `BookingStateMachine` class with methods: `transition(current_state, event, context)` returning next state and actions, `get_state(lead_id)` from Redis key `booking_state:{lead_id}`, `set_state(lead_id, state, context)` persisting state snapshot with TTL 7 days. State context includes: `slot_candidates`, `idempotency_key`, `reminder_schedule`, `parent_key` (for reschedules), `attempt_count`. Use deterministic state transitions with validation at each gate. Integrate with existing `AgentState` from `backend/schemas/state.py` by adding `booking_state` field. Reference existing state management patterns in `backend/utils/redis_client.py` for Redis operations.

### backend/booking/message_bus.py(NEW)

References: 

- backend/api/webhooks.py(MODIFY)
- backend/utils/redis_client.py(MODIFY)

Create message bus for multi-channel intake normalization. Implement `MessageBus` class with `normalize_message(channel, raw_payload)` returning `NormalizedMessage` dataclass with fields: `message_uuid` (UUIDv7), `lead_id`, `content`, `channel` (enum: ig, whatsapp, email), `timestamp`, `metadata`. Add `is_duplicate(message_uuid)` checking Redis key `processed_messages:{uuid}` with TTL 7 days. Implement `claim_message(message_uuid)` using Redis SETNX for atomic claim by competing consumers. Add `mark_processed(message_uuid, result)` storing processing outcome. Create channel-specific parsers: `parse_instagram_webhook(payload)`, `parse_whatsapp_webhook(payload)`, `parse_email_webhook(payload)`. Reference existing webhook handling in `backend/api/webhooks.py` for Instagram payload structure. Use Redis client from `backend/utils/redis_client.py` with circuit breaker pattern.

### backend/booking/idempotent_calendar_writer.py(NEW)

References: 

- backend/tools/calendar_integration.py(MODIFY)
- backend/utils/audit.py

Create idempotent calendar write handler. Implement `IdempotentCalendarWriter` class with `write_event(lead_id, slot_time, event_payload, idempotency_key)` that: 1) Queries `booking_attempts` table by `idempotency_key`, 2) If exists, returns stored `event_id` + `etag` (no-op), 3) If new, calls `GoogleCalendarClient.create_event()` from `backend/tools/calendar_integration.py` with `extendedProperties.private.idempotency_key`, 4) Persists response to `booking_attempts` table with `event_id`, `etag`, `request_payload`, `response_body`, `status`, 5) On conflict (ETag drift), returns `conflict` status and triggers replan. Add `validate_availability(slot_time)` checking freebusy before write. Implement `handle_conflict(lead_id, slot_time)` that invalidates slot cache, requeries calendar, proposes alternatives, logs to Slack. Use existing `GoogleCalendarClient` from `backend/tools/calendar_integration.py` and extend `create_event()` to accept `idempotency_key` parameter. Reference audit logging from `backend/utils/audit.py` for write tracking.

### backend/booking/reminder_scheduler.py(NEW)

References: 

- backend/celery_app.py(MODIFY)
- backend/communication/multi_channel_manager.py(MODIFY)
- backend/tools/calendar_integration.py(MODIFY)

Create multi-touch reminder system. Implement `ReminderScheduler` class with `schedule_reminders(event_id, lead_id, slot_time, channel_preferences)` that creates 3 Celery tasks: `send_reminder_24h.apply_async(eta=slot_time - 24h)`, `send_reminder_3h.apply_async(eta=slot_time - 3h)`, `send_reminder_30m.apply_async(eta=slot_time - 30m)`. Each task calls `send_reminder(lead_id, event_id, reminder_type, channel)` using minimal-context prompts from `REMINDER_TEMPLATES` dict with canned variants per channel (SMS > email > DM priority). Implement `track_confirmation(lead_id, event_id, confirmed_at)` updating `event.extendedProperties.private.confirmed_at` via `GoogleCalendarClient.update_event()`. Add `check_confirmation_status(event_id)` and `send_last_chance_reminder(lead_id, event_id)` at T-60m if unconfirmed, with Slack alert to `#booking-ops`. Store reminder schedule in Redis `reminder_schedule:{lead_id}` with fields: `reminder_24h_sent`, `reminder_3h_sent`, `reminder_30m_sent`, `confirmed_at`. Use `MultiChannelManager` from `backend/communication/multi_channel_manager.py` for message delivery. Reference Celery app from `backend/celery_app.py` for task scheduling.

### backend/booking/waitlist_manager.py(NEW)

References: 

- backend/utils/lead_scoring.py
- backend/utils/response_tracker.py
- backend/communication/multi_channel_manager.py(MODIFY)

Create waitlist backfill system. Implement `WaitlistManager` class with `add_to_waitlist(lead_id, service, location, fit_score, responsiveness_score)` inserting into `waitlist` table. Add `trigger_backfill(slot_time, service, location)` querying waitlist by matching criteria, ranking by `fit_score * responsiveness_score`, filtering by guardrails: min 24h notice, max 2 outreach/day/person, fairness rotation (track last contacted in Redis `waitlist_contacted:{lead_id}`). Implement `attempt_backfill(lead_id, slot_time)` that: 1) Generates new `idempotency_key`, 2) Sends slot offer via `MultiChannelManager`, 3) Logs attempt to `waitlist_attempts` table, 4) Caps at 3 attempts per candidate. Add `calculate_fit_score(lead_data, slot_context)` using budget alignment, timeline urgency, engagement score. Implement `calculate_responsiveness_score(lead_id)` from response time history in `backend/utils/response_tracker.py`. Store backfill state in Redis `backfill_state:{slot_time}` with attempted candidates. Reference existing lead scoring from `backend/utils/lead_scoring.py` for fit calculation.

### backend/booking/scheduling_policies.py(NEW)

References: 

- backend/agents/scheduler.py(MODIFY)
- backend/tools/scheduling_utils.py

Create scheduling policy enforcement. Define `BufferPolicy` dataclass with fields: `min_gap_minutes` (default 30), `travel_buffer_by_location` (dict mapping location pairs to buffer minutes), `default_duration_minutes` (default 60), `max_daily_bookings` (default 8). Implement `apply_buffer_policy(slots, policy, existing_events)` filtering slots that violate buffer constraints. Add `calculate_travel_buffer(location_a, location_b)` using distance matrix from `backend/tools/scheduling_utils.py` or hardcoded city pairs (e.g., Miami → Fort Lauderdale = 45min). Implement `enforce_conflict_resolution(slot_time, policy)` that: 1) Checks for overlaps with existing events, 2) If conflict, extends time window and requeries calendar, 3) Proposes alternative slots, 4) Logs conflict to `booking_conflicts` table. Add `get_policy_for_service(service_type)` returning service-specific policies (e.g., multi-property tours need 90min duration). Reference existing buffer logic in `backend/agents/scheduler.py` methods `apply_buffer_times()` and `filter_conflicting_slots()`.

### backend/booking/observability_metrics.py(NEW)

References: 

- backend/utils/audit.py

Create observability and SLA tracking. Implement `ObservabilityMetrics` class with methods: `track_write_latency(start_time, end_time, lead_id)` calculating P50/P95/P99 and storing in `booking_metrics` table, `track_conflict_rate(total_writes, conflicts)` calculating percentage, `track_idempotency_reuse(total_writes, reused)` tracking cache hits, `track_double_book_prevention(prevented_count)` counting conflicts avoided. Add `check_sla_thresholds()` comparing metrics against targets: write latency < 60s, conflict rate < 2%, P95 response < 2min, double-book rate < 0.5%. Implement `send_slack_alert(alert_type, payload)` posting to webhook URL from env var `SLACK_WEBHOOK_URL` for: conflict detected, policy drift, rising retry counts, cache miss spike. Add `generate_weekly_digest()` aggregating: bookings count, reschedules count, backfills count, show-rate trend vs 30-day baseline, conflicts avoided, token/latency cost. Store metrics in Redis with keys: `metrics:write_latency:{date}`, `metrics:conflict_rate:{date}`, `metrics:idempotency_reuse:{date}`. Reference existing audit logging from `backend/utils/audit.py` for event correlation.

### backend/booking/slot_cache_manager.py(NEW)

References: 

- backend/utils/redis_client.py(MODIFY)
- backend/tools/calendar_integration.py(MODIFY)

Create Redis-backed slot cache with ETag invalidation. Implement `SlotCacheManager` class with `get_cached_slots(location, service, duration, buffers)` checking Redis key `slots:{location}:{service}:{duration}:{buffers}:{etag}` with TTL 5min. Add `cache_slots(location, service, duration, buffers, slots)` storing slot list with current ETag. Implement `invalidate_cache(calendar_id)` incrementing ETag in Redis `calendar_etag:{calendar_id}` (no TTL, manual invalidation). Add `merge_provider_calendars(calendar_ids)` querying freebusy for multiple calendars and returning union of free slots. Implement `optimistic_hold(lead_id, slot_time)` storing in Redis `slot_hold:{lead_id}` with TTL 15min, `validate_hold(lead_id, slot_time)` checking if hold still valid, `release_hold(lead_id)` deleting hold key. Add `revalidate_on_accept(slot_time)` querying calendar freebusy immediately before write to catch last-second conflicts. Reference existing Redis operations from `backend/utils/redis_client.py` and calendar queries from `backend/tools/calendar_integration.py`.

### backend/api/whatsapp_webhook.py(NEW)

References: 

- backend/api/webhooks.py(MODIFY)
- backend/utils/audit.py

Create WhatsApp Business API webhook handler. Implement FastAPI router with `@router.get('/webhooks/whatsapp')` for verification challenge and `@router.post('/webhooks/whatsapp')` for message events. Add `verify_whatsapp_signature(payload, signature)` using HMAC-SHA256 with `WHATSAPP_APP_SECRET`. Implement `extract_whatsapp_message(webhook_data)` parsing WhatsApp webhook payload structure: `entry[].changes[].value.messages[]` with fields `id`, `from`, `text.body`, `timestamp`. Add `is_duplicate_message(message_id)` checking Redis `processed_messages:{message_id}`. Call `MessageBus.normalize_message('whatsapp', message_data)` to create normalized message with UUID. Enqueue Celery task `process_whatsapp_message.delay(normalized_message)` for async processing. Reference existing Instagram webhook structure in `backend/api/webhooks.py` for patterns. Use audit logging from `backend/utils/audit.py` for message tracking.

### backend/api/email_webhook.py(NEW)

References: 

- backend/api/webhooks.py(MODIFY)
- backend/communication/multi_channel_manager.py(MODIFY)

Create email webhook handler for SendGrid/Mailgun. Implement FastAPI router with `@router.post('/webhooks/email/sendgrid')` and `@router.post('/webhooks/email/mailgun')`. Add `verify_sendgrid_signature(payload, signature)` and `verify_mailgun_signature(payload, signature)` using provider-specific HMAC validation. Implement `extract_email_message(webhook_data, provider)` parsing inbound email payload: `from`, `to`, `subject`, `text`, `html`, `message_id`, `timestamp`. Add `extract_lead_id_from_email(to_address)` parsing email address format `leads+{lead_id}@domain.com` or querying database by email. Call `MessageBus.normalize_message('email', message_data)` creating normalized message with UUID. Enqueue Celery task `process_email_message.delay(normalized_message)`. Add `send_email_reply(to_address, subject, body)` using SendGrid/Mailgun API for responses. Reference webhook patterns from `backend/api/webhooks.py` and multi-channel manager from `backend/communication/multi_channel_manager.py`.

### backend/tasks/reminder_tasks.py(NEW)

References: 

- backend/celery_app.py(MODIFY)
- backend/communication/multi_channel_manager.py(MODIFY)

Create Celery tasks for reminder system. Define `@celery_app.task` functions: `send_reminder_24h(lead_id, event_id, slot_time)`, `send_reminder_3h(lead_id, event_id, slot_time)`, `send_reminder_30m(lead_id, event_id, slot_time)`. Each task: 1) Loads lead data from database, 2) Checks if reminder already sent via Redis `reminder_sent:{lead_id}:{reminder_type}`, 3) Selects channel based on preferences (SMS > email > DM), 4) Loads minimal-context prompt template from `REMINDER_TEMPLATES`, 5) Sends message via `MultiChannelManager.send_message()`, 6) Updates Redis reminder tracking, 7) Logs to audit. Add `check_confirmation_task(lead_id, event_id)` scheduled at T-60m that: 1) Checks `event.extendedProperties.private.confirmed_at`, 2) If unconfirmed, sends last-chance reminder and Slack alert, 3) Marks as no-show risk. Implement `process_confirmation_reply(lead_id, event_id, message)` updating event metadata. Reference Celery app from `backend/celery_app.py` and multi-channel manager from `backend/communication/multi_channel_manager.py`.

### backend/tasks/backfill_tasks.py(NEW)

References: 

- backend/celery_app.py(MODIFY)

Create Celery tasks for waitlist backfill. Define `@celery_app.task` function `trigger_waitlist_backfill(slot_time, service, location, reason)` that: 1) Queries `waitlist` table for matching candidates, 2) Ranks by fit_score * responsiveness_score, 3) Filters by guardrails (min 24h notice, max 2 outreach/day, fairness rotation), 4) Iterates through top 5 candidates calling `attempt_backfill_for_candidate.delay(lead_id, slot_time)`, 5) Logs backfill trigger to audit. Implement `attempt_backfill_for_candidate(lead_id, slot_time)` that: 1) Checks backfill attempt count < 3, 2) Generates new idempotency_key, 3) Sends slot offer via `MultiChannelManager`, 4) Stores attempt in `waitlist_attempts` table, 5) Updates Redis `waitlist_contacted:{lead_id}` with timestamp. Add `process_backfill_acceptance(lead_id, slot_time, message)` transitioning to booking state machine. Reference waitlist manager from `backend/booking/waitlist_manager.py` and Celery app from `backend/celery_app.py`.

### backend/tools/calendar_integration.py(MODIFY)

Extend `GoogleCalendarClient.create_event()` to accept `idempotency_key` parameter and store in `extendedProperties.private.idempotency_key`. Add `etag` field to return value from `event.get('etag')`. Implement `GoogleCalendarClient.get_event_by_idempotency_key(idempotency_key)` querying calendar events with matching extended property. Add `GoogleCalendarClient.update_event_metadata(event_id, metadata)` for updating confirmation status and reminder tracking. Implement `GoogleCalendarClient.get_event_etag(event_id)` returning current ETag for conflict detection. Add error handling for ETag mismatches returning `conflict` status. Reference existing calendar client implementation and extend methods to support idempotency pattern. Maintain backward compatibility with existing callers by making `idempotency_key` optional parameter.

### backend/models/lead.py(MODIFY)

Add booking-related fields to `Lead` model: `booking_idempotency_key` (Optional[str]), `booking_etag` (Optional[str]), `booking_attempt_count` (Optional[int] default 0), `booking_state` (Optional[str]), `reminder_24h_sent` (Optional[bool] default False), `reminder_3h_sent` (Optional[bool] default False), `reminder_30m_sent` (Optional[bool] default False), `reminder_confirmed_at` (Optional[datetime]), `no_show_predicted` (Optional[bool] default False), `waitlist_added_at` (Optional[datetime]), `parent_booking_key` (Optional[str] for reschedule lineage). Add method `generate_idempotency_key()` creating KSUID-based unique key. Add method `is_booking_confirmed()` checking if reminder_confirmed_at is set. Maintain backward compatibility with existing fields. Reference existing Lead model structure and Pydantic patterns.

### backend/schemas/state.py(MODIFY)

Add `booking_state` field to `AgentState` TypedDict: `booking_state: Optional[Dict[str, Any]]` containing state machine context with keys: `current_state`, `slot_candidates`, `idempotency_key`, `reminder_schedule`, `parent_key`, `attempt_count`, `last_transition_at`. Add `message_uuid` field: `message_uuid: Optional[str]` for deduplication tracking. Add `booking_metrics` field: `booking_metrics: Optional[Dict[str, Any]]` for latency/conflict tracking. Maintain backward compatibility with existing state fields. Reference existing AgentState structure and ensure compatibility with LangGraph checkpointer.

### backend/agents/scheduler.py(MODIFY)

References: 

- backend/booking/scheduling_policies.py(NEW)

Integrate `BookingStateMachine` into `scheduler_node()`. Replace direct calendar booking with state machine transitions: 1) Check current booking state via `BookingStateMachine.get_state(lead_id)`, 2) If state is `PROPOSE_SLOT`, call `SlotCacheManager.get_cached_slots()` with buffer policy, 3) If state is `CONFIRM`, call `IdempotentCalendarWriter.write_event()` with generated idempotency_key, 4) On successful write, transition to `REMINDERS` state and call `ReminderScheduler.schedule_reminders()`, 5) On conflict, transition to `PROPOSE_SLOT` with replan flag. Remove direct calls to `book_calendar_event()` and replace with state machine orchestration. Maintain existing tour optimization methods (`optimize_tour_sequence()`, `apply_buffer_times()`, `filter_conflicting_slots()`) but integrate with new scheduling policies from `backend/booking/scheduling_policies.py`. Reference existing scheduler logic and preserve HITL interrupt handling.

### backend/api/webhooks.py(MODIFY)

Integrate `MessageBus` for Instagram webhook handling. In `handle_comment_webhook()`, after extracting comment events, call `MessageBus.normalize_message('instagram', comment_event)` to create normalized message with UUID. Replace `is_duplicate_comment()` with `MessageBus.is_duplicate(message_uuid)`. Replace `mark_comment_processed()` with `MessageBus.mark_processed(message_uuid, result)`. Add `message_uuid` to audit log events. Maintain existing signature verification, keyword detection, and Celery task enqueueing. Ensure backward compatibility with existing comment processing flow. Reference message bus implementation from `backend/booking/message_bus.py`.

### backend/tasks/booking_flow.py(MODIFY)

Integrate state machine into `BookingFlowManager`. In `initiate_booking_flow()`, initialize booking state via `BookingStateMachine.set_state(lead_id, 'INTAKE', context)`. In `_offer_time_slots()`, transition to `PROPOSE_SLOT` state and use `SlotCacheManager.get_cached_slots()` with buffer policy. In `_book_meeting_slot()`, transition to `CONFIRM` state, generate idempotency_key via `Lead.generate_idempotency_key()`, call `IdempotentCalendarWriter.write_event()`, on success transition to `REMINDERS` and call `ReminderScheduler.schedule_reminders()`. Add reschedule handling: `handle_reschedule_request(lead_id, new_slot_time)` that soft-cancels original event, creates new idempotency_key with parent_key lineage, transitions to `RESCHEDULE` state. Maintain existing email capture flow and slot selection logic. Reference state machine from `backend/booking/booking_state_machine.py`.

### backend/utils/redis_client.py(MODIFY)

Add helper methods for booking state management: `get_booking_state(lead_id)` retrieving from Redis key `booking_state:{lead_id}`, `set_booking_state(lead_id, state, context, ttl=604800)` storing state snapshot with 7-day TTL, `increment_booking_attempt(lead_id)` atomically incrementing attempt counter. Add slot cache methods: `get_slot_cache(cache_key)`, `set_slot_cache(cache_key, slots, ttl=300)`, `invalidate_slot_cache(pattern)`. Add optimistic hold methods: `create_slot_hold(lead_id, slot_time, ttl=900)`, `validate_slot_hold(lead_id, slot_time)`, `release_slot_hold(lead_id)`. Add reminder tracking methods: `mark_reminder_sent(lead_id, reminder_type)`, `check_reminder_sent(lead_id, reminder_type)`. Maintain existing Redis operations and circuit breaker pattern. Use consistent key naming conventions.

### backend/config.py(MODIFY)

Add configuration settings for booking ops: `SLACK_WEBHOOK_URL` (Optional[str]), `WHATSAPP_APP_SECRET` (Optional[str]), `WHATSAPP_PHONE_NUMBER_ID` (Optional[str]), `SENDGRID_API_KEY` (Optional[str]), `MAILGUN_API_KEY` (Optional[str]), `BOOKING_WRITE_TIMEOUT_SECONDS` (int default 60), `REMINDER_LEAD_TIMES` (List[int] default [24*60, 3*60, 30]), `WAITLIST_MAX_ATTEMPTS` (int default 3), `WAITLIST_MIN_NOTICE_HOURS` (int default 24), `SLOT_CACHE_TTL_SECONDS` (int default 300), `OPTIMISTIC_HOLD_TTL_SECONDS` (int default 900), `ENABLE_MULTI_TOUCH_REMINDERS` (bool default True), `ENABLE_WAITLIST_BACKFILL` (bool default True), `ENABLE_SLACK_ALERTS` (bool default True). Add feature flags for phased rollout. Maintain existing configuration structure and validation functions.

### CREATE_TABLES.sql(MODIFY)

Add new tables for booking ops: `booking_attempts` with columns `id TEXT PRIMARY KEY` (KSUID), `lead_id UUID REFERENCES leads(id)`, `slot_time TIMESTAMPTZ`, `request_payload JSONB`, `response_etag TEXT`, `calendar_event_id TEXT`, `status TEXT CHECK (status IN ('pending', 'confirmed', 'conflict', 'failed'))`, `parent_key TEXT` (for reschedule lineage), `created_at TIMESTAMPTZ DEFAULT NOW()`, `updated_at TIMESTAMPTZ DEFAULT NOW()`. Add `waitlist` table with columns `id UUID PRIMARY KEY`, `lead_id UUID REFERENCES leads(id)`, `service TEXT`, `location TEXT`, `fit_score FLOAT`, `responsiveness_score FLOAT`, `backfill_attempts INT DEFAULT 0`, `last_contacted_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ DEFAULT NOW()`. Add `waitlist_attempts` table with columns `id UUID PRIMARY KEY`, `waitlist_id UUID REFERENCES waitlist(id)`, `slot_time TIMESTAMPTZ`, `idempotency_key TEXT`, `status TEXT`, `attempted_at TIMESTAMPTZ DEFAULT NOW()`. Add `booking_metrics` table with columns `id UUID PRIMARY KEY`, `metric_type TEXT`, `value FLOAT`, `metadata JSONB`, `recorded_at TIMESTAMPTZ DEFAULT NOW()`. Add `booking_conflicts` table with columns `id UUID PRIMARY KEY`, `lead_id UUID`, `slot_time TIMESTAMPTZ`, `conflict_reason TEXT`, `resolved BOOLEAN DEFAULT FALSE`, `created_at TIMESTAMPTZ DEFAULT NOW()`. Create indexes on new tables. Add RLS policies. Reference existing table structure and maintain consistency.

### backend/celery_app.py(MODIFY)

References: 

- backend/tasks/booking_flow.py(MODIFY)

Add task imports for new reminder and backfill tasks: `from backend.tasks.reminder_tasks import send_reminder_24h, send_reminder_3h, send_reminder_30m, check_confirmation_task`, `from backend.tasks.backfill_tasks import trigger_waitlist_backfill, attempt_backfill_for_candidate`. Configure Celery beat schedule for periodic tasks: `check_unconfirmed_bookings` running every 15 minutes to check T-60m confirmations, `generate_weekly_digest` running every Monday at 9am. Add task routing for reminder tasks to dedicated queue `reminders` and backfill tasks to queue `backfill`. Maintain existing Celery configuration and auto-discovery. Reference existing task structure from `backend/tasks/booking_flow.py`.

### backend/communication/multi_channel_manager.py(MODIFY)

Implement actual WhatsApp and email sending methods. In `_send_via_whatsapp()`, call WhatsApp Business API using `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_APP_SECRET` from config, send message via POST to `https://graph.facebook.com/v18.0/{phone_number_id}/messages` with template or text message. In `_send_via_email()`, call SendGrid API using `SENDGRID_API_KEY` from config, send email via POST to `https://api.sendgrid.com/v3/mail/send` with from/to/subject/body. Add retry logic with exponential backoff for API failures. Add delivery status tracking via webhook callbacks. Maintain existing Instagram DM and SMS placeholder implementations. Reference existing channel sending patterns and audit logging.

### backend/booking/README.md(NEW)

Create comprehensive documentation for Self-Driving Booking Ops 2.0. Document architecture overview with state machine diagram, idempotent write flow, multi-channel intake, reminder cadence, waitlist backfill, observability metrics. Include setup instructions: database migrations, Redis keys, Celery workers, webhook configuration. Add API reference for each module: `BookingStateMachine`, `MessageBus`, `IdempotentCalendarWriter`, `ReminderScheduler`, `WaitlistManager`, `SchedulingPolicies`, `ObservabilityMetrics`, `SlotCacheManager`. Document configuration settings and feature flags. Include troubleshooting guide for common issues: Redis connection failures, calendar API rate limits, webhook signature verification, ETag conflicts. Add binary acceptance test specifications: write latency < 60s, P95 response < 2min, +20% show-rate, <0.5% double-books. Include example usage and integration patterns.