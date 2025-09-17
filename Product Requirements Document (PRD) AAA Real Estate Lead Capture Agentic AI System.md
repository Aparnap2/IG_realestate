### Revised Product Requirements Document (PRD): AAA Real Estate Lead Capture Agentic AI System

This PRD refines the AAA Real Estate Lead Capture Agentic AI System, tailored for real estate agencies to automate lead capture, qualification, and meeting scheduling for property inquiries. It builds on the previous PRD, focusing on specific implementation details for the LangGraph swarm architecture, detailed database schema, exact API endpoints, and precise business logic for lead qualification. The system is a portfolio piece for the AAA AI Automation Agency to attract real estate clients for custom development work ($5k+ projects). It uses a Python backend (FastAPI, LangGraph), React (Vite + shadcn/ui) for the admin dashboard, Supabase for auth and DB, OpenRouter for LLMs, Redis for state and query caching, and integrations with Instagram, WhatsApp, Google Calendar, and HubSpot.

---

## 1. Overview
### 1.1 Product Description
The system automates lead capture from Instagram (IG) and WhatsApp, qualifies leads based on real estate-specific criteria (e.g., budget, location, property type), schedules property tours or consultations, and logs to HubSpot/Supabase. It replaces manual processes with a LangGraph-based swarm of autonomous agents (Qualifier, Scheduler, FollowUp) that communicate via defined patterns, persist state with Redis checkpoints, and use Supabase queries for context. A React dashboard (Vite + shadcn/ui) enables monitoring, customization, configuration, and data management, secured by Supabase auth. The system is optimized for real estate, ensuring precise qualification and seamless scheduling.

### 1.2 Target Audience and Use Cases
- **Users**: Real estate agents/brokers; AAA agency for portfolio demos.
- **Use Cases**:
  - Lead sends "2BHK in Miami, $300k" → Qualify (budget, timeline) → Schedule tour → Log to HubSpot.
  - Multi-turn chats (e.g., lead asks about amenities; agent queries Supabase for property details).
  - Human reviews high-value leads (budget >$500k) via dashboard.
  - Monitor leads, edit prompts, manage properties via dashboard.
- **Assumptions**: API keys for Meta, Google, HubSpot, OpenRouter; GDPR/CCPA compliance.

### 1.3 Goals and Objectives
- **Business**: Showcase AAA’s real estate AI expertise; Automate 80% of lead processes; Reduce manual effort by 90%.
- **Technical**: Implement LangGraph swarm with explicit communication patterns; Supabase for secure DB/auth; Redis for state/query caching; React dashboard for admin tasks. Handle 500 concurrent threads, 99% uptime.
- **Metrics**: Qualification accuracy >85%; Booking rate >30% for qualified leads; Demo inquiries >20%.

### 1.4 Scope
- **In Scope**: Lead ingestion, agentic qualification/scheduling, integrations, HITL, dashboard, Supabase auth/DB, Redis-backed DB queries.
- **Out of Scope**: RAG, temporal knowledge graphs, voice, payments, advanced analytics.

---

## 2. Features and Requirements
### 2.1 Core Features
1. **Lead Ingestion**:
   - Capture￼Webhooks from IG Graph API and WhatsApp Business API capture inquiries.
   - Queue in RabbitMQ for async processing.
   - **Requirements**: Verify Meta signatures; Parse user_id, message, channel; Text-only for MVP.

2. **Agentic Conversation and Qualification**:
   - LangGraph swarm with three agents:
     - **Qualifier**: Scores leads (0-1) using OpenRouter LLM based on budget, location, timeline, property type; Queries Supabase for property/lead context; Caches in Redis.
     - **Scheduler**: Queries Google Calendar for slots; Proposes/book events; Logs to HubSpot/Supabase.
     - **FollowUp**: Nurtures low-scoring leads with listing suggestions.
   - **Requirements**: Redis checkpoints for thread persistence; DB query tool for accurate responses; Handoffs based on score (>0.7 → Scheduler; else → FollowUp).

3. **Meeting Scheduling**:
   - Scheduler books Google Calendar events; Logs to HubSpot (contact/deal) and Supabase.
   - **Requirements**: Timezone handling (default agency’s); In-chat slot proposals; Confirmations.

4. **Human-in-the-Loop (HITL)**:
   - Interrupt for high-value leads (budget >$500k).
   - **Requirements**: Email notifications; Dashboard review/resume via /human/* endpoints.

5. **Admin Dashboard (React Vite + shadcn/ui)**:
   - **Monitoring**: Real-time lead pipeline (DataTable); Metrics (bookings, scores); Plotly charts.
   - **Customization**: Edit agent prompts, thresholds (e.g., HITL at 0.9).
   - **Configuration**: Update API keys, HITL toggle.
   - **Data Management**: Add/edit properties/leads via CSV or forms.
   - **Requirements**: Supabase auth (JWT); Realtime updates; shadcn components (DataTable, Forms).

6. **Persistence and State Management**:
   - Redis: LangGraph checkpointer (thread_id = user_id); Cache DB queries (TTL 24h).
   - Supabase: Store leads, properties, configs.
   - **Requirements**: Resume multi-turn chats; Cache property queries for speed.

7. **Error Handling**:
   - **Requirements**: Retry API failures (Celery backoff); Graceful replies; Escalate LLM errors to HITL.

### 2.2 Non-Functional Requirements
- **Performance**: <5s response; 500 concurrent threads.
- **Security**: Supabase JWT; RLS for DB; Encrypt PII.
- **Reliability**: Idempotent queuing; Redis checkpoints.
- **Usability**: Intuitive React dashboard; Dockerized setup.

### 2.3 Dependencies and Integrations
- **APIs**: Meta (IG/WhatsApp), Google Calendar, HubSpot, OpenRouter.
- **Libraries**: `fastapi`, `uvicorn`, `langgraph`, `langgraph-swarm`, `celery`, `redis`, `sqlalchemy`, `supabase`, `openai` (OpenRouter), `meta-business-sdk`, `google-api-python-client`, `hubspot-api-client`, `@supabase/supabase-js`, `@tanstack/react-query`, `shadcn/ui`.

---

## 3. Specific Implementation Details
### 3.1 LangGraph Swarm Architecture and Agent Communication Patterns
The LangGraph swarm orchestrates three ReAct agents (Qualifier, Scheduler, FollowUp) with explicit communication patterns for real estate lead processing. Each agent is a node in a StateGraph, using tools for DB queries, API calls, and handoffs. The swarm ensures adaptive, persistent workflows with HITL interrupts.

#### Swarm Architecture
- **State Definition**: `AgentState` (TypedDict):
  ```python
  from typing import Annotated, TypedDict
  from pydantic import BaseModel
  from datetime import datetime
  from operator import add

  class Lead(BaseModel):
      id: str
      channel: str  # "ig" or "whatsapp"
      user_id: str
      message: str
      qualified_score: float | None = None
      budget: int | None = None  # e.g., 300000
      location: str | None = None  # e.g., "Miami"
      property_type: str | None = None  # e.g., "2BHK"
      timeline: str | None = None  # e.g., "3 months"
      name: str | None = None
      email: str | None = None
      meeting_slot: datetime | None = None
      status: str = "new"  # new, qualified, scheduled, booked

  class AgentState(TypedDict):
      lead: Lead
      messages: Annotated[list[dict[str, str]], add]  # [{"role": "user", "content": "..."}, ...]
      human_feedback: str | None  # HITL input
      next_agent: str  # "qualifier", "scheduler", "followup"
  ```
- **Checkpointer**: RedisSaver (`langgraph-checkpoint-redis`, or custom Redis client if unavailable). Thread ID = `lead.user_id`. Persists state for multi-turn resumption.
- **Nodes**:
  - **Qualifier**: Entry node; Invokes OpenRouter LLM; Tools: `query_properties_db`, `send_reply`, `handoff_to_*`.
  - **Scheduler**: Invokes for high-scoring leads; Tools: `find_calendar_slot`, `book_event`, `log_to_hubspot`, `handoff_to_followup`.
  - **FollowUp**: Nurtures low-scoring leads; Tools: `send_reply`, `handoff_to_end`.
- **Edges**:
  - Conditional: Qualifier → Scheduler (score >0.7), FollowUp (score ≤0.7), or END.
  - Static: Scheduler → FollowUp (post-booking); FollowUp → END.
- **Interrupt**: Before Scheduler node (`interrupt_before=["scheduler"]`) for HITL (budget >$500k).

#### Communication Patterns
- **Request-Reply**: Qualifier responds to user messages (e.g., "What’s your budget?") via Meta APIs, appending to `state.messages`.
- **Handoffs**: Explicit tools (`handoff_to_scheduler`, `handoff_to_followup`, `handoff_to_end`) update `state.next_agent`:
  ```python
  from langgraph.types import Command
  from langgraph.prebuilt import tool

  @tool
  def handoff_to_scheduler(state: Annotated[AgentState, InjectedState], tool_call_id: str) -> Command:
      return Command(goto="scheduler", update={"next_agent": "scheduler"})
  ```
- **Contextual Queries**: Qualifier uses `query_properties_db` to fetch relevant listings (e.g., `SELECT * FROM properties WHERE price <= :budget`). Results cached in Redis (key: `query:{user_id}:{hash(query)}`, TTL: 24h).
- **Asynchronous Updates**: Celery tasks invoke swarm; Redis checkpoints ensure state consistency across messages.
- **HITL**: Interrupt pauses swarm; FastAPI endpoint (`/human/approve`) updates `state.human_feedback` and resumes.

#### Example Flow
1. Lead: "2BHK in Miami, $300k" → Qualifier queries DB → Scores 0.8 → Asks "Timeline?" → Handoffs to Scheduler.
2. Scheduler: Queries calendar → Proposes "Tuesday 2PM?" → Pauses for HITL (if budget >$500k) → Books on approval.

### 3.2 Database Schema (Supabase)
Supabase (Postgres) with Row Level Security (RLS) for secure access. Tables:
- **leads**:
  - `id`: UUID (primary key)
  - `user_id`: VARCHAR (Meta PSID or WhatsApp number)
  - `channel`: VARCHAR (ig/whatsapp)
  - `message`: TEXT (initial inquiry)
  - `qualified_score`: FLOAT (0-1, NULLable)
  - `budget`: INTEGER (e.g., 300000, NULLable)
  - `location`: VARCHAR (e.g., "Miami", NULLable)
  - `property_type`: VARCHAR (e.g., "2BHK", NULLable)
  - `timeline`: VARCHAR (e.g., "3 months", NULLable)
  - `name`: VARCHAR (NULLable)
  - `email`: VARCHAR (NULLable)
  - `meeting_slot`: TIMESTAMP (NULLable)
  - `status`: VARCHAR (new/qualified/scheduled/booked)
  - `history`: JSONB (conversation history, e.g., [{"message": "...", "timestamp": "..."}])
  - `created_at`: TIMESTAMP (default now())
  - **RLS**: `select` for authenticated users; `insert/update` for admins.
- **properties**:
  - `id`: UUID (primary key)
  - `price`: INTEGER (e.g., 300000)
  - `location`: VARCHAR (e.g., "Miami")
  - `property_type`: VARCHAR (e.g., "2BHK")
  - `amenities`: JSONB (e.g., {"pool": true, "parking": false})
  - `details`: JSONB (e.g., {"sqft": 1200, "year_built": 2020})
  - **RLS**: `select` for all; `insert/update` for admins.
- **configs**:
  - `key`: VARCHAR (e.g., "qualifier_prompt")
  - `value`: TEXT (e.g., "Ask about budget, location, timeline")
  - **RLS**: `select` for authenticated; `upsert` for admins.
- **Relationships**:
  - No direct FKs (denormalized for simplicity).
  - `leads` references `properties` implicitly via `budget`, `location`, `property_type` for queries (e.g., match lead criteria to properties).
  - Dashboard queries join `leads` and `properties` for analytics (e.g., `SELECT l.*, p.* FROM leads l JOIN properties p ON p.price <= l.budget`).

### 3.3 API Integration Details
#### Meta (Instagram Graph API, WhatsApp Business API)
- **Endpoints**:
  - **Webhooks**: `POST /webhook/{channel}` (ig/whatsapp) to receive messages.
    - Payload: `{ "entry": [{ "messaging": [{ "sender": { "id": "<PSID>" }, "message": { "text": "<text>" } }] }]}`
    - Verification: Validate `hub.signature` (SHA256 HMAC with app secret).
  - **Send Message**:
    - IG: `POST /v18.0/me/messages?access_token=<token>`
      - Payload: `{"recipient": {"id": "<PSID>"}, "message": {"text": "<reply>"}}`
    - WhatsApp: `POST /v18.0/<PHONE_ID>/messages`
      - Payload: `{"messaging_product": "whatsapp", "to": "<number>", "type": "text", "text": {"body": "<reply>"}}`
- **Features**: Real-time message receipt; Reply delivery; Text-only support.

#### Google Calendar
- **Endpoints**:
  - **Freebusy**: `POST /calendar/v3/calendars/primary/freebusy`
    - Payload: `{"timeMin": "<ISO8601>", "timeMax": "<ISO8601>", "items": [{"id": "primary"}]}`
    - Returns: Available slots (e.g., 30min gaps).
  - **Insert Event**: `POST /calendar/v3/calendars/primary/events`
    - Payload: `{"summary": "Tour with <name>", "start": {"dateTime": "<ISO8601>", "timeZone": "America/New_York"}, "end": {...}, "attendees": [{"email": "<lead.email>"}]}`
- **Features**: Query slots; Create events with invites; Timezone support (default agency’s).

#### HubSpot
- **Endpoints**:
  - **Create Contact**: `POST /crm/v3/objects/contacts`
    - Payload: `{"properties": {"email": "<lead.email>", "firstname": "<lead.name>", "phone": "<lead.user_id>", "lifecyclestage": "lead"}}`
  - **Create Deal**: `POST /crm/v3/objects/deals`
    - Payload: `{"properties": {"dealname": "Tour for <lead.user_id>", "amount": "<lead.budget>", "dealstage": "appointmentscheduled"}}`
- **Features**: Log leads as contacts; Associate meetings with deals.

#### OpenRouter
- **Endpoint**: `POST /api/v1/chat/completions`
  - Payload: `{"model": "anthropic/claude-3.5-sonnet", "messages": [{"role": "user", "content": "<prompt with DB context>"}]}`
  - Headers: `Authorization: Bearer <OPENROUTER_API_KEY>`
- **Features**: Dynamic model selection; Cost-efficient LLM calls (~$0.01/1k tokens).

### 3.4 Business Logic: Lead Qualification Criteria
- **Criteria**:
  - **Budget**: INTEGER (e.g., $300,000); Must be >$100,000 for qualification.
  - **Location**: VARCHAR; Must match available properties in DB (e.g., "Miami").
  - **Property Type**: VARCHAR (e.g., "2BHK", "Condo"); Must align with DB listings.
  - **Timeline**: VARCHAR (e.g., "3 months"); Urgent (<6 months) increases score.
- **Scoring Logic** (Qualifier Agent):
  - Prompt: "Score lead (0-1) for real estate interest based on: Budget: {lead.budget}, Location: {lead.location}, Type: {lead.property_type}, Timeline: {lead.timeline}. DB properties: {db_results}. High score if budget >$100k, location/type match, timeline <6 months."
  - Scoring:
    - Budget: >$500k (+0.4), $100k-$500k (+0.2), <$100k (0).
    - Location Match: Exact (+0.3), Partial (+0.1).
    - Type Match: Exact (+0.2).
    - Timeline: <3 months (+0.2), 3-6 months (+0.1).
    - Example: Lead ($400k, Miami, 2BHK, 2 months) → 0.8 (0.2 + 0.3 + 0.2 + 0.1).
  - **Thresholds**:
    - >0.7: Handoff to Scheduler.
    - ≤0.7: Handoff to FollowUp.
    - >0.9: HITL interrupt (high-value lead, e.g., budget >$500k).

---

## 4. User Stories
1. **As a real estate agent**, I want leads captured from IG/WhatsApp so inquiries are processed automatically. (Acceptance: Webhook queues lead to RabbitMQ, logs to Supabase.)
2. **As a developer**, I want a LangGraph swarm to qualify leads and handoff tasks. (Acceptance: Qualifier scores via OpenRouter; DB queries for context; Handoffs based on score.)
3. **As a bot**, I want Redis-cached DB queries to provide accurate property info. (Acceptance: Supabase query cached; LLM uses results for replies.)
4. **As a sales manager**, I want HITL for high-value leads ($500k+). (Acceptance: Pause at score >0.9; Dashboard review; Email alert.)
5. **As an agent**, I want automated tour scheduling. (Acceptance: Google Calendar slots booked; HubSpot/Supabase logged.)
6. **As an admin**, I want a React dashboard to monitor leads, edit prompts, configure APIs, manage properties. (Acceptance: shadcn DataTable; Supabase auth; Realtime updates.)
7. **As a developer**, I want Redis persistence for seamless multi-turn chats. (Acceptance: Checkpointer resumes threads; Thread ID = user_id.)
8. **As an admin**, I want robust error handling for demos. (Acceptance: Retry API calls; Log errors in dashboard.)

---

## 5. Workflow
1. **Lead Arrival**: User sends "2BHK in Miami, $300k" → Webhook → RabbitMQ task.
2. **Celery Processing**: Pulls task → Loads thread from Redis (thread_id = user_id) or inits AgentState.
3. **Swarm Execution**:
   - **Qualifier**: Queries Supabase (`SELECT * FROM properties WHERE price <= :budget AND location = :location`) → Caches in Redis → Scores via OpenRouter → Replies (e.g., "Timeline?") → Handoffs:
     - Score >0.7 → Scheduler.
     - Score ≤0.7 → FollowUp.
     - Budget >$500k → HITL interrupt.
   - **Scheduler**: Queries Google Calendar freebusy → Proposes slot → Books on confirmation → Logs to HubSpot/Supabase.
   - **FollowUp**: Sends "New listings available!" → Ends or loops.
4. **HITL**: Pauses at interrupt → Email notification → Admin reviews via dashboard (/human/review) → Approves (/human/approve) → Resumes.
5. **Completion**: Updates Supabase/HubSpot → Confirms via channel → Persists state.

**Error Flows**: API failure → Retry (3x, 5s backoff); Invalid input → Reply "Please clarify"; Timeout → FollowUp nurture.

---

## 6. Design
### 6.1 Architecture
- **Frontend**: React (Vite), shadcn/ui, `@supabase/supabase-js`, `@tanstack/react-query`.
- **Backend**: FastAPI, LangGraph (swarm), Celery, RabbitMQ.
- **State**: Redis (checkpointer, query cache).
- **DB/Auth**: Supabase (Postgres with RLS, JWT auth).
- **LLM**: OpenRouter (Claude-3.5-sonnet).
- **Integrations**: Meta, Google, HubSpot APIs as tools.
- **Deployment**: Docker Compose (FastAPI, Redis, RabbitMQ, Supabase); Vite for frontend; Ngrok for webhooks.

### 6.2 Database Schema
See section 3.2. Supabase tables (`leads`, `properties`, `configs`) with RLS; JSONB for flexible history/details.

### 6.3 React Dashboard (Vite + shadcn/ui)
- **Components**: DataTable (leads), Card (metrics), Form (prompts/configs), FileUpload (CSV properties).
- **Auth**: Supabase JWT; Login page; RLS policies (e.g., `auth.role = 'admin'` for updates).
- **Realtime**: Supabase Realtime for lead updates (e.g., `supabase.from('leads').on('INSERT', ...)`).
- **Code Example** (src/App.jsx):
  ```jsx
  import { createClient } from "@supabase/supabase-js";
  import { useQuery, useMutation } from "@tanstack/react-query";
  import { Button, Input, DataTable } from "@/components/ui";

  const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_KEY);

  function App() {
    const { data: user } = useQuery({
      queryKey: ["user"],
      queryFn: () => supabase.auth.getUser(),
    });

    if (!user?.data?.user) {
      const login = async () => {
        await supabase.auth.signInWithPassword({
          email: "admin@example.com",
          password: "pass",
        });
        window.location.reload();
      };
      return (
        <div className="p-4">
          <Input placeholder="Email" />
          <Input type="password" placeholder="Password" />
          <Button onClick={login}>Login</Button>
        </div>
      );
    }

    const { data: leads } = useQuery({
      queryKey: ["leads"],
      queryFn: async () => (await supabase.from("leads").select("*")).data,
    });

    const updatePrompt = useMutation({
      mutationFn: async (prompt) => supabase.from("configs").upsert({ key: "qualifier_prompt", value: prompt }),
    });

    return (
      <div className="p-4">
        <h1>Real Estate Lead Dashboard</h1>
        <DataTable
          columns={[
            { accessorKey: "user_id", header: "User" },
            { accessorKey: "status", header: "Status" },
            { accessorKey: "qualified_score", header: "Score" },
          ]}
          data={leads || []}
        />
        <Input
          placeholder="Qualifier Prompt"
          defaultValue="Ask about budget, location, timeline"
          onBlur={(e) => updatePrompt.mutate(e.target.value)}
        />
        <Button
          onClick={() =>
            supabase.from("properties").insert({ price: 300000, location: "Miami", property_type: "2BHK" })
          }
        >
          Add Property
        </Button>
      </div>
    );
  }
  export default App;
  ```

### 6.4 Scalability
- Supabase: Cloud scaling; RLS for multi-user.
- Redis: Cluster for high concurrency.
- Celery: Multiple workers.

---

### Setup Instructions
1. **Frontend**: `pnpm create vite@latest --template react`, `pnpm install @supabase/supabase-js @tanstack/react-query`, `pnpx shadcn-ui@latest init`.
2. **Backend**: `uv install fastapi uvicorn langgraph langgraph-swarm celery redis sqlalchemy supabase openai meta-business-sdk google-api-python-client hubspot-api-client`.
3. **Supabase**: Create project; Set up `leads`, `properties`, `configs` with RLS.
4. **Redis/RabbitMQ**: `docker-compose up`.
5. **Run**: `uvicorn app.main:app`, `celery -A celery_worker worker`, `pnpm run dev`.
6. **Webhooks**: Ngrok for Meta APIs.

This PRD refines the system for real estate, detailing LangGraph communication, Supabase schema, API endpoints, and qualification logic. For implementation code (e.g., DB query tool), let me know!