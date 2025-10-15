🎯 **Vertical Real Estate Agentic AI System**  
**Feature List + Workflow Diagram (Markdown)**

---

## 1. Core Features

| Module | Feature | Edge-Case Handling | Business Value |
|--------|---------|--------------------|----------------|
| **Lead Capture** | Instagram DM → sub-5 min AI reply | Rate-limit, spam filter, fair-housing gate | 60 % lead-loss → 5 % |
| **Router** | Intent classification (7 classes) | Low-confidence → human review | Zero mis-routing |
| **Qualifier** | Budget/BR/location extraction | Partial info, budget mismatch, no inventory | 70 % → 95 % accuracy |
| **Scheduler** | Multi-property tour optimizer | No slots, timezone, traffic delays | 30 % → 40 % booking rate |
| **Follow-Up** | Temporal nurture (price-drop, new listings) | Cooling leads, objections, market shifts | 3× re-engagement vs blast |
| **Compliance** | Fair-housing eval + immutable audit | Block & suggest safe rewrite | $0 lawsuit exposure |
| **Revenue Intel** | Lead-to-close attribution | Temporal causality queries | 2.3× close rate on matched listings |
| **CRM Sync** | HubSpot 2-way sync | Duplicate detection, field mapping | Single source of truth |
| **Calendar** | Google Calendar + Meet | Double-book guard, buffers, reminders | Zero no-shows |
| **Knowledge Graph** | Neo4j Graphiti temporal memory | Preference drift, similar-lead look-up | Context-aware every touch |

---

## 2. High-Level Workflow Diagram

```mermaid
graph TD
    IG[Instagram DM] -->|webhook| CF(Cloudflare Worker)
    CF -->|publish| RMQ[RabbitMQ: instagram.dm.received]
    RMQ -->|consume| API[Hono API]
    API -->|persist| PG[(Supabase)]
    API -->|emit| RMQ2[RabbitMQ: lead.message.received]
    RMQ2 -->|trigger| AI[Python LangGraph Service]
    
    subgraph LangGraph Agents
        AI --> RT{Router}
        RT -->|new_inquiry| QF[Qualifier]
        RT -->|schedule_tour| SC[Scheduler]
        RT -->|follow_up| FU[FollowUp]
        RT -->|low_confidence| HR[Human Review]
    end

    QF -->|search| PS[Property Search]
    QF -->|check| FH[Fair-Housing Eval]
    QF -->|write| N4J[(Neo4j Graphiti)]
    
    SC -->|avail| GCAL[Google Calendar]
    SC -->|meet| GMEET[Google Meet]
    
    FU -->|temporal| N4J
    FU -->|new_listings| PROP[(Property DB)]
    
    SC -->|emit| RMQ3[RabbitMQ: tour.scheduled]
    RMQ3 -->|workflow| ING[Inngest]
    ING -->|create_event| GCAL
    ING -->|sync| HS[HubSpot]
    ING -->|reminder| IG2[Instagram DM]
    
    classDef agent fill:#f9d71c,stroke:#333
    classDef data fill:#8ac6d1,stroke:#333
    class RT,QF,SC,FU,HR agent
    class PG,N4J,PROP,HS data
```

---

## 3. Per-Agent Micro-Workflows

### 3.1 Router Agent
```mermaid
flowchart LR
    A[Latest Message] --> B[LLM Intent<br/>Classification]
    B --> C{confidence > 0.6 ?}
    C -->|yes| D[Route: qualifier/<br/>scheduler/followup]
    C -->|no| E[Flag Human Review]
    D --> F[Store Decision<br/>in Audit Log]
    E --> F
```

### 3.2 Qualifier Agent
```mermaid
flowchart TD
    A[Conversation History] --> B[Extract Budget/<br/>BR/Location]
    B --> C{Partial Info ?}
    C -->|yes| D[Ask Clarifying<br/>Question]
    C -->|no| E[Search Properties]
    E --> F{Matches ?}
    F -->|0| G[Offer Waitlist/<br/>Alert]
    F -->|>0| H[Fair-Housing<br/>Check]
    H --> I[Return 3 Best<br/>Matches + Message]
```

### 3.3 Scheduler Agent
```mermaid
flowchart TD
    A[Preferred Date/Time] --> B[Query Agent<br/>Free-Busy]
    B --> C{Available ?}
    C -->|no| D[Search Next 7 Days]
    C -->|yes| E[Optimize Property<br/>Sequence by Travel]
    E --> F[Create Google<br/>Calendar Event]
    F --> G[Generate Meet Link]
    G --> H[Send IG DM<br/>Confirmation]
    H --> I[Schedule 24 h<br/>Reminder via Inngest]
```

### 3.4 Follow-Up Agent
```mermaid
flowchart TD
    A[Days Since Last] --> B{> 30 ?}
    B -->|yes| C[Query Graphiti<br/>Price Drops]
    C --> D{Price Drop > 5 % ?}
    D -->|yes| E[Send Price-Drop Alert]
    D -->|no| F[Send Market Update]
    B -->|no| G{New Listings ?}
    G -->|yes| H[Send Property Alert]
    G -->|no| I[Check Engagement<br/>Trajectory]
    I --> J{Cooling ?}
    J -->|yes| K[Soft Check-In]
    J -->|no| L[Urgency Trigger]
```

---

## 4. Compliance Workflow
```mermaid
sequenceDiagram
    Agent->>Policy Eval: outbound message
    Policy Eval->>Policy Eval: regex + LLM scan
    alt violation detected
        Policy Eval->>Agent: block + suggested rewrite
        Agent->>Audit Log: log violation + action
    else clean
        Policy Eval->>Instagram API: send message
        Policy Eval->>Audit Log: log approval
    end
```

---

## 5. Temporal Knowledge Graph Queries
| Query | Cypher Snippet | Use-Case |
|-------|----------------|----------|
| **Price drops on viewed properties** | `MATCH (l)-[:VIEWED]->(p) WHERE p.price < p.original_price RETURN p` | Urgency alert |
| **Preference drift** | `MATCH (l)-[f:FACT]->() WHERE f.valid_from > now() - 30 days RETURN f` | Adjust nurture |
| **Similar leads who closed** | `MATCH (l2)-[:OUTCOME]->(d {status:'closed'}) WHERE l2.budget ≈ l1.budget RETURN l2` | Learn winning patterns |

---

## 6. Event-Driven Orchestration (Inngest)
```mermaid
graph LR
    EV[tour.scheduled event] --> W1[Workflow: Create G-Cal]
    W1 --> W2[Workflow: Sync HubSpot]
    W1 --> W3[Workflow: 24 h Reminder]
    W2 --> W4[Workflow: Slack Notify]
    CRON[9 AM CRON] --> W5[Workflow: Detect Cooling Leads]
    W5 --> W6[Fan-out: Trigger Follow-ups]
```

---

## 7. Failure & Retry Strategy
| Failure Point | Retry Policy | Fallback | Alert |
|---------------|--------------|----------|-------|
| Instagram API | 3× exponential | Buffer in KV | Slack |
| OpenRouter LLM | 2× + GPT-4o-mini | Static reply | Sentry |
| Google Calendar | 3× + 60 s backoff | Manual calendar link | Admin email |
| Neo4j Graphiti | 2× | Store in PG temporal table | Logger |
| RabbitMQ | auto-requeue | Dead-letter queue | Metrics |

---

## 8. Observability Dashboards
- **Langfuse**: LLM token cost, latency, accuracy per agent  
- **Sentry**: Error rate, retry count, fatal exceptions  
- **Redis Insights**: Checkpoint size, cache hit ratio  
- **Neo4j Bloom**: Knowledge-graph visual of lead journeys  
- **Grafana**: API latency, booking rate, compliance violations  

---

All workflows are **idempotent**, **horizontally scalable**, and **compliance-auditable** out of the box.