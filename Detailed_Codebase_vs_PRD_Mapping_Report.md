PRD Alignment Analysis and Exact File/Function Mapping
Below is a precise gap analysis and a file/function-level implementation plan to align the codebase with the PRD: “Vertical Real Estate Revenue Acceleration Platform.” Each PRD section maps to current code, gaps, and exact actions (files/functions) so a coding agent can implement without re-reading the repo.

0) High-Level Architecture Alignment
Current core

Backend FastAPI + LangGraph agents
backend/api/webhooks.py (Instagram webhook)
backend/agents/prd_compliant_workflow.py (Qualifier, Scheduler, FollowUp)
backend/agents/{qualifier.py,scheduler.py,followup.py,modular_agents.py}
backend/tasks/{lead_processing.py,production_lead_processing.py} (Celery pipeline)
backend/tools/agent_tools.py (LLM, Supabase, calendar placeholders, HubSpot)
backend/utils/{supabase_client.py,redis_client.py,llm_client.py,observability.py}
backend/schemas/state.py, backend/models/lead.py
Storage/infra
Supabase (CREATE_TABLES.sql + backend/scripts/create_database_schema.py)
Redis for state/checkpoints
Frontend (React + Playwright tests)
Main gaps

No Router Agent or pre-send Compliance Gate
No Immutable Audit Log with policy checks
No Temporal Knowledge Graph (Neo4j/Graphiti); minimal temporal memory
Qualification not multi-step (no budget/needs reconciliation tool)
Scheduler uses placeholder GCal; no property availability, traffic, no-show risk
Nurture lacks temporal triggers/new inventory awareness
GDPR/TCPA consent tracking absent
Revenue intelligence/attribution missing
Observability minimal (no Sentry/Langfuse)
1) PRD 2.1 Intelligent Lead Capture (Router + Compliance)
Current
Instagram webhook handling:
backend/api/webhooks.py → verifies and queues messages to Celery (process_webhook)
instagram_webhook_server.py (standalone FastAPI); overlaps with backend/api/webhooks.py
Agents start at Qualifier (no Router):
backend/workflow.py (mentions 3 agents only)
backend/agents/prd_compliant_workflow.py (QualifierAgent entry point)
Gaps
Missing Router Agent to classify intent/channel and apply pre-send policy gates.
No fair housing evaluator, GDPR/CCPA/TCPA compliance checks.
No immutable audit log capturing policy decisions and message send events.
Duplicate webhook entrypoint (instagram_webhook_server.py) → potential divergence.
Actions (exact files/functions)
Add Router Agent

File: backend/agents/router.py
Function: RouterAgent.process(state: AgentState) -> Dict[str, Any]
Classify intent: inquiry/objection/info
Select channel (IG/SMS/email) from history (for now, IG default)
Invoke compliance evaluator before sending any reply
Set next_agent to qualifier|scheduler|followup based on intent and context
# backend/agents/router.py
from typing import Dict, Any
from schemas.state import AgentState
from tools.compliance import fair_housing_evaluator
from tools.agent_tools import send_instagram_message

class RouterAgent:
    def process(self, state: AgentState) -> Dict[str, Any]:
        lead = state["lead"]
        intent = self.classify_intent(lead.message)  # simple heuristic/LLM
        compliance = fair_housing_evaluator(lead.message, context=lead.to_dict())
        if compliance["blocked"]:
            # Reroute with neutral reply, record audit
            send_instagram_message.invoke({"user_id": lead.user_id, "message": compliance["neutral_reply"]})
            state["next_agent"] = "followup"
            return {"lead": lead, "next_agent": "followup", "messages": state.get("messages", [])}
        # Default route
        state["next_agent"] = "qualifier"
        return {"lead": lead, "next_agent": "qualifier", "messages": state.get("messages", [])}

    def classify_intent(self, text: str) -> str:
        # Minimal heuristic/LLM classification; extend later
        return "inquiry"
Add Compliance tools

File: backend/tools/compliance.py
Functions:
fair_housing_evaluator(message:str, context:dict) -> dict
gdpr_tcpa_tracker(lead_id:str, event:str, metadata:dict) -> None
Uses utils/audit.py to append immutable logs.
# backend/tools/compliance.py
from utils.audit import audit_log_event

def fair_housing_evaluator(message: str, context: dict) -> dict:
    # Simple rule-based check + LLM later
    blocked = any(kw in message.lower() for kw in ["families in", "race", "religion"])
    if blocked:
        audit_log_event("policy_block", {"message": message, "lead": context, "policy": "fair_housing"})
        return {"blocked": True, "neutral_reply": "Let's focus on property features and local amenities that match your needs."}
    return {"blocked": False}

def gdpr_tcpa_tracker(lead_id: str, event: str, metadata: dict) -> None:
    audit_log_event("consent_event", {"lead_id": lead_id, "event": event, "meta": metadata})
Immutable Audit Log

File: backend/utils/audit.py
Function: audit_log_event(event_type:str, payload:dict) -> None → write to Supabase table audit_logs with server-side timestamp, hash.
Update schema:
Add audit_logs table (per PRD: eventType, agentType, policy_checks, humanReviewed, hash)
SQL: put in backend/scripts/create_database_schema.py + CREATE_TABLES.sql
Integrate Router into workflow

File: backend/workflow.py
Update to add Router node as entry point; add edge Router → Qualifier/Scheduler/FollowUp
Update backend/tasks/production_lead_processing.py to start with Router
Deprecate duplicate webhook file

Remove or document instagram_webhook_server.py as legacy; route everything through backend/api/webhooks.py.
2) PRD 2.2 Adaptive Lead Qualification
Current
Qualifier agent present
backend/agents/prd_compliant_workflow.py::QualifierAgent.process
Extracts info via utils/llm_client.extract_lead_info
Queries Supabase via tools.agent_tools.query_properties_tool
Scores via tools.agent_tools.qualify_lead_with_llm (prompt-only)
Some routing logic to scheduler/followup
Gaps
No budget vs. needs reconciliation (3BR vs. 2BR budget) multi-step reasoning.
No temporal knowledge graph; no engagement trajectory scoring adjustments.
No property graph queries beyond simple filters.
Actions
Add reconciliation tool

File: backend/tools/qualifier_utils.py
Function: reconcile_budget_mismatch(desired:int, budget:int, inventory:list) -> dict
Wire into QualifierAgent.process after DB query.
# backend/tools/qualifier_utils.py
def reconcile_budget_mismatch(desired_bedrooms: int, budget: int, inventory: list) -> dict:
    # Analyze inventory availability and propose trade-offs
    options = []
    # Example heuristics; expand with LLM/tool use
    has_three_br = any(p["bedrooms"] >= 3 and p["price"] <= budget * 1.1 for p in inventory)
    if not has_three_br:
        options.append("Show 2BR in premium school districts as alternative")
        options.append("Show 3BR up to +10% budget, justify value")
    return {"tradeoffs": options}
File change: backend/agents/prd_compliant_workflow.py::QualifierAgent.process
Import and call reconcile_budget_mismatch
Incorporate into qualification_result["reasoning"]
Temporal knowledge graph client (placeholder)

File: backend/temporal/graph_client.py
Class: GraphClient with methods:
get_recent_interests(lead_id), upsert_interest_event(...)
Future: back with Neo4j/Graphiti; for now, persist to Supabase tables lead_interactions, lead_interests.
Update QualifierAgent to read engagement trajectory and adjust score:
If re_engaged after >30d → +0.15
If prior_showings > 2 and avg_viewed_price > budget → +0.2
Enhance qualify_lead_with_llm

File: backend/tools/agent_tools.py
Update prompt to include:
Engagement trajectory, prior interactions, inventory signals, budget/needs reconciliation, temporal adjustments
Return structured fields: {score, reasoning, adjustments: {...}}
3) PRD 2.3 Frictionless Scheduling (Multi-Constraint)
Current
SchedulerAgent sends available slots and books first slot
Calendar functions are placeholders:
get_available_calendar_slots, book_calendar_event in backend/tools/agent_tools.py
Gaps
No Google Calendar real integration (freebusy).
No property availability (MLS/internal)
No travel time/traffic optimization
No timezone inference/no-show risk
Actions
Separate calendar integration

File: backend/tools/calendar_integration.py
Implement:
get_google_calendar_freebusy(days_ahead:int) -> List[datetime]
book_google_calendar_event(start_time, duration, attendee_email, summary, description) -> dict
Update SchedulerAgent to import these functions instead of placeholders.
Property availability integration

File: backend/tools/property_availability.py
Function: query_property_showings(property_ids: list) -> dict[property_id -> slots]
For now, fetch from Supabase properties table fields like showing_slots if present or create a small table property_showings.
Travel time and no-show risk

File: backend/tools/scheduling_utils.py
Functions:
get_maps_travel_time(agent_location, properties) -> dict
predict_no_show_risk(lead_context) -> float (simple heuristic by engagement)
infer_timezone_from_phone(user_id) -> str
find_optimal_tour_slots(lead, properties, constraints) -> list
Update SchedulerAgent.process:
Compute constraints + find_optimal_tour_slots (return top 2-3 sequences)
Ask confirmation; then book.
# backend/tools/scheduling_utils.py
def find_optimal_tour_slots(lead, properties, constraints) -> list:
    # Compose objective: maximize [lead_preference, agent_efficiency, property_availability]
    # Return ordered list of Slot suggestions
    return []
4) PRD 2.4 Intelligent Nurture (Temporal, Property-Matched)
Current
FollowUpAgent sends basic suggestions or generic message based on db_results
Gaps
No temporal triggers (what changed since last interaction)
No “new inventory since last interaction” lookup
No engagement trajectory-driven actions
Actions
Enhance follow-up agent

File: backend/agents/followup.py (extend current)
Add query:
“New listings since last_interaction matching past criteria”
From Supabase (properties.created_at > last_interaction)
Add “temporal events since last interaction” using temporal/graph_client.py
Add nurture strategy generator:
tools/nurture.py::generate_nurture_action(lead, graph) -> dict returning action like “send market alert with 2BR alternatives”
# backend/tools/nurture.py
def generate_nurture_action(lead, temporal_graph) -> dict:
    # Use recent events and new_matches to decide
    return {"type": "market_alert", "message": "New 2BR in your range just listed..."}
Update persistence

On every follow-up send:
Append to audit log
Update lead.last_interaction
5) PRD 2.6 Compliance-by-Design (Policy Gates, Audit, GDPR/CCPA)
Current
Basic observability only
No explicit GDPR/TCPA fields or immutable audit logs
No pre-send evaluator tooling
Gaps
Audit log schema absent
Consent tracking absent
HITL policy approval not logged as tamper-evident
Actions
Immutable audit logs

File: backend/utils/audit.py as above
DB:
Add audit_logs table (see PRD model): event_type, agent_type, agent_decision JSON, policy_checks JSON, human_reviewed BOOL, message_hash, timestamp
Implement server-side compute of hash (message + timestamp + secret) to detect tampering
GDPR/CCPA/TCPA consent

DB:
Extend leads with: gdpr_consent BOOLEAN, tcpa_opt_in BOOLEAN, consent_timestamp TIMESTAMPTZ
Update:
backend/scripts/create_database_schema.py, CREATE_TABLES.sql
Runtime:
tools/compliance.gdpr_tcpa_tracker(...) on consent events
Policy evaluator hook-points

Pre-send in Router, Qualifier, Scheduler, FollowUp
Always call fair_housing_evaluator before sending a message
Record results in audit log
6) Temporal Memory & Knowledge Graph
Current
Redis checkpoint + minimal conversation state
No temporal graph for preferences/causality
Gaps
No Graphiti/Neo4j client layer or equivalent Supabase-based temporal tables
Actions
Temporal client abstraction

File: backend/temporal/graph_client.py
Methods:
record_event(lead_id, type, payload)
recent_events(lead_id, since)
prior_interests(lead_id)
Backed initially by Supabase tables: lead_events, lead_interests
Later swap with Neo4j seamlessly
Integrate into all agents

Qualifier: upsert interest, engagement changes
Scheduler: record appointments, cancellations
FollowUp: record nurture events/responses
7) Revenue Intelligence & Metrics
Current
backend/utils/observability.py basic counters
No lead-to-close attribution, inventory insights
Gaps
No attribution model, no inventory performance analytics
Actions
Inventory insights
File: backend/utils/analytics.py
analyze_inventory_performance() to rank properties by qualified leads, bookings
Attribution pipeline
Track agent steps → conversion events in audit_logs
Build simple attribution query in analytics.py
Frontend dashboard
New/extend: frontend/src/components/MetricsDashboard.tsx to include attribution, inventory insights
8) Data Schema Changes (Supabase)
Extend leads:
gdpr_consent BOOLEAN DEFAULT false
tcpa_opt_in BOOLEAN DEFAULT false
consent_timestamp TIMESTAMPTZ
engagement_score FLOAT DEFAULT 0 (optional for temporal adjustments)
New tables:
audit_logs(...) as PRD (immutable design with hash)
lead_events(...), lead_interests(...)
property_showings(...) (if separate from properties)
Update:
backend/scripts/create_database_schema.py
CREATE_TABLES.sql
9) Testing & E2E
Backend unit/integration tests (pytest):
Add tests for:
Router intent classification and compliance gating
Qualifier reconciliation path
Scheduler multi-constraint planner
FollowUp temporal-triggered actions
Audit log append and tamper hash
Locations: backend/tests/
Frontend Playwright E2E:
Extend frontend/tests/e2e/ to simulate IG → routed → qualified → scheduled → audit verified
Seed/migrations:
backend/alembic + scripts updated to create new tables/seeds
10) Concrete File-by-File Task List
New files

backend/agents/router.py (RouterAgent)
backend/tools/compliance.py (policy gates + consent tracker)
backend/utils/audit.py (immutable logging)
backend/tools/qualifier_utils.py (reconcile_budget_mismatch)
backend/tools/calendar_integration.py (real GCal)
backend/tools/property_availability.py
backend/tools/scheduling_utils.py (planner, risk, timezone)
backend/tools/nurture.py (nurture actions)
backend/temporal/graph_client.py (temporal memory)
backend/utils/analytics.py (attribution, inventory insights)
Modified files

backend/workflow.py: Add Router node as entry; wire compliance pre-send hooks
backend/agents/prd_compliant_workflow.py: call reconciliation + temporal adjustments; pre-send compliance check on all messages
backend/agents/{qualifier.py,scheduler.py,followup.py}: keep consistent with above or migrate fully to prd_compliant_workflow.py
backend/api/webhooks.py: no logical change (already solid)
backend/tools/agent_tools.py: remove calendar placeholders; enhance qualify_lead_with_llm
backend/utils/observability.py: add counters by event type; optional Sentry/Langfuse hooks
backend/scripts/create_database_schema.py and CREATE_TABLES.sql: add new tables/columns
Deprecations

instagram_webhook_server.py → mark as legacy
11) Example: Pre-Send Compliance Hook in Agents
# In every agent before sending messages:
from tools.compliance import fair_housing_evaluator
from utils.audit import audit_log_event

def safe_send(user_id: str, message: str):
    result = fair_housing_evaluator(message, context={"user_id": user_id})
    if result.get("blocked"):
        msg = result["neutral_reply"]
    else:
        msg = message
    audit_log_event("message_send", {"user_id": user_id, "final_message": msg, "policy_blocked": result.get("blocked", False)})
    send_instagram_message.invoke({"user_id": user_id, "message": msg})
12) Milestones and Acceptance Criteria
Phase 1 (Week 1–2)

Router Agent + compliance gate integrated
Immutable audit logs (+ migrations)
Qualifier reconciliation + temporal adjustments
Basic temporal store (Supabase-backed)
Criteria: pre-send policy gate active; audit logs recorded; tests for router/qualifier
Phase 2 (Week 3–4)

Scheduler multi-constraint planner (GCal + property availability + basic travel/no-show)
FollowUp temporal nurture actions
Criteria: suggested multi-slot tours, nurture triggers validated in tests
Phase 3 (Week 5–6)

Revenue intelligence: attribution + inventory insights
Observability upgrade; optional Sentry/Langfuse
Criteria: dashboard shows attribution and inventory rankings
13) Exact Mapping: PRD → Code
2.1 Lead Capture (Router, Fair Housing)
New: backend/agents/router.py + backend/tools/compliance.py + backend/utils/audit.py
Existing entry: backend/api/webhooks.py (keep)
2.2 Adaptive Qualification
Existing: backend/agents/prd_compliant_workflow.py::QualifierAgent.process
New: backend/tools/qualifier_utils.py, backend/temporal/graph_client.py
Update: tools/agent_tools.py::qualify_lead_with_llm
2.3 Scheduling
Existing: backend/agents/prd_compliant_workflow.py::SchedulerAgent.process
New: backend/tools/calendar_integration.py, backend/tools/property_availability.py, backend/tools/scheduling_utils.py
2.4 Nurture
Existing: backend/agents/followup.py or prd_compliant_workflow.py::FollowUpAgent
New: backend/tools/nurture.py, backend/temporal/graph_client.py
2.6 Compliance-by-Design
New: backend/tools/compliance.py, backend/utils/audit.py
DB: audit_logs, consent fields in leads
Temporal Memory
New: backend/temporal/graph_client.py (+ Supabase tables lead_events, lead_interests)
Revenue Intelligence
New: backend/utils/analytics.py, FE dashboard updates
14) What to Do Next (quickest path)
Add Router + Compliance + Audit (files outlined above), wire into workflow.py.
Add schema migrations (audit_logs, consent fields), run seeds.
Enhance Qualifier with reconciliation + temporal adjustments.
Replace calendar placeholders with calendar_integration.py; add simple property availability.
Extend FollowUp with temporal nurture.
Add tests for each module; run Playwright smoke E2E.
If you want, I can create the new files with stubs and patch the existing ones in small, reviewable steps.





High-Priority Conflicts to Resolve
instagram_webhook_server.py vs backend/api/webhooks.py
Recommendation: pick a single webhook entrypoint.
Prefer keeping backend/api/webhooks.py mounted by backend/main.py (cleaner, multi-tenant ready). Then delete instagram_webhook_server.py and update README.
If you prefer the standalone server, keep instagram_webhook_server.py and delete backend/api/webhooks.py. Update imports and tests accordingly.
Backend Agents: Overlapping Implementations
Multiple agent files likely superseded by backend/agents/prd_compliant_workflow.py:
Candidates to deprecate/move to backend/legacy/ (or delete if unused by imports/tests):
backend/agents/dynamic_workflow.py
backend/agents/enhanced_agents.py
backend/agents/enhanced_workflow.py
backend/agents/modular_agents.py
backend/agents/qualifier.py (if prd_compliant_workflow defines the active Qualifier)
backend/agents/scheduler.py and backend/agents/followup.py (same condition)
Next step: I can scan imports/tests to confirm which are unused before deletion.
Frontend Duplicates (same-purpose modules)
Supabase client duplication:
frontend/src/lib/supabase.ts and frontend/src/lib/supabaseClient.ts
Action: keep one (prefer supabaseClient.ts), update imports, delete the other.
Leads table component duplication:
frontend/src/components/LeadsTable.tsx and frontend/src/components/LeadTable.tsx
Action: keep the one actually used in App.tsx/routes; delete the other.
Login views overlap:
frontend/src/components/LoginForm.tsx and frontend/src/components/Login.tsx
Action: keep one canonical auth entry; remove the duplicate after updating references.
Repo-Level JS Package Duplication
Root vs frontend package management:
Root: package.json, package-lock.json, pnpm-lock.yaml
Frontend: frontend/package.json, frontend/pnpm-lock.yaml (active)
Action: If nothing in the root uses Node, delete root package.json and lockfiles; keep everything under frontend/ only.
Coverage/Results Artifacts (safe to delete)
Remove generated coverage/results:
Root: htmlcov/, test-results/
Backend: backend/htmlcov/
Frontend: frontend/test-results/
Remove Python caches:
backend/.pytest_cache, all __pycache__/ subfolders.
Database Scripts/Overlap
Potential duplication of DB setup paths:
Root: create_production_db.py
Backend: backend/scripts/create_database_schema.py, backend/scripts/setup_database.py
Action: consolidate on backend/scripts/* as the canonical location. Delete or move create_production_db.py after ensuring README/scripts reference the canonical path.
Webhook SQL Fix Script
backend/scripts/fix_webhook_database_schema.sql
If Alembic migrations fully cover schema, move to migrations/legacy/ or delete.
Tests Directory Duplication
Root tests/ vs frontend/tests/e2e/
If root tests/ is empty/redundant, delete. Frontend E2E lives under frontend/tests/e2e/ already. Backend tests are under backend/tests/.
Keep As-Is (likely in use)
backend/celery_supervisor.conf, docker-compose.yml (backend services), frontend/docker-compose.yml (FE dev) appear valid.
Proposed Next Steps
Choose webhook entrypoint (single source of truth).
Approve the duplicate removals above.
I’ll:
Remove files,
Update imports/README/scripts,
Run tests,
Open a cleanup PR.