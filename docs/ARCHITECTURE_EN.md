# System Architecture and Design Principles

[简体中文](ARCHITECTURE.md) | English

## Overall Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     AI Agent Security Gateway                  │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Admin Console│  │ Detection API│  │ Data Screen  │        │
│  │ (Vue3 SPA)   │  │  /guard/*    │  │  WebSocket   │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │                 │                  │                │
│         └─────────────────┼──────────────────┘                │
│                           ▼                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  FastAPI Application Layer              │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │  │
│  │  │  Routing  │  │ Business │  │ Persistence      │     │  │
│  │  │  (api/)   │  │(services/│  │ (models/schemas/)│     │  │
│  │  └──────────┘  └──────────┘  └──────────────────┘     │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                   │
│                           ▼                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │            SQLAlchemy ORM + Database                   │  │
│  │         SQLite (local) / PostgreSQL (production)       │  │
│  └────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Model Invoker

Location: `backend/app/services/model_invoker.py`

**Responsibilities**:
- Unifies the invocation logic for the two integration methods: REST and script
- REST: builds the request and determines safety based on the JsonPath result plus status code
- Script: executes user code in a separate subprocess with an agreed return format
- Returns a structured `InvokeResult` (safe/unsafe/timeout/error + elapsed time)

**Isolation Mechanisms**:
- REST calls go through `httpx`'s async client with a configured timeout
- Script calls run via `asyncio.create_subprocess_exec`, providing natural isolation

### 2. Strategy Engine

Location: `backend/app/services/strategy_engine.py`

**Responsibilities**: executes the orchestration of a single policy, implementing the invocation rules of the models bound to the policy. Two rules are currently supported: sequential detection and random detection.

#### Sequential Detection

**Flow**:
1. Invokes the detection models bound to the policy one by one in order
2. As soon as any model returns unsafe, terminates immediately and returns unsafe
3. If all models pass, the overall verdict is safe

**Advantages**:
- **Fail fast**: the first unsafe verdict terminates execution, reducing latency
- **Resource savings**: subsequent model calls are never triggered

**Suitable for**: high-throughput scenarios where response speed comes first

#### Random Detection

**Flow**:
1. Randomly selects one detection capability from the pool of detection models bound to the policy and invokes it
2. The selected model's verdict becomes the overall policy result (safe/unsafe)
3. A single-model timeout is still accounted for according to the policy's configured timeout policy (safe/unsafe)

**Advantages**:
- **Low invocation cost**: only one detection model is called per request, with predictable latency and overhead
- **Uncertain protection**: callers cannot predict which detection capability will be hit, raising the difficulty of evasion

**Suitable for**: scenarios where multiple detection capabilities in the model pool can substitute for one another, or where low-cost spot checks are needed

### 3. Gateway Orchestration

Location: `backend/app/services/gateway.py`

**Responsibilities**:
- Extracts the inspected content from the user request via JsonPath
- Executes the policy chain bound to the API path in order
- If any policy is unsafe, terminates immediately and returns unsafe
- If all policies pass, returns safe
- Persists request logs and detection-model invocation logs
- Pushes real-time events to WebSocket clients through the `broadcaster`

**Policy chain example**:
- Policy 1 (PII detection) → Policy 2 (jailbreak detection) → Policy 3 (inappropriate content detection)
- The three policies run in sequence; the request is allowed through only if all are safe

### 4. Broadcaster

Location: `backend/app/services/broadcaster.py`

**Responsibilities**:
- Maintains the WebSocket connection pool
- Pushes four types of events: `request_received` / `strategy_start` / `strategy_result` / `final_result`
- Consumed by the dashboard frontend to render the real-time detection flow and sequential-detection animations

**Event flow**:
```
1. request_received   → the dashboard shows the request arriving; the AI app node flashes
2. strategy_start     → a policy block appears, displaying the model pool
3. strategy_result    → per-model verdicts arrive one by one; sequential-detection progress animation
4. final_result       → the final verdict; data packet return animation
```

## Data Model Design

### Core Table Relationships

```
User
ApiKey
SafetyTag
  ├── ModelTagLink ───▶ DetectionModel
  │                        ├── REST configuration fields
  │                        └── script content field
  └── Strategy
         ├── StrategyModelLink ───▶ DetectionModel
         └── ApiPathStrategyLink ───▶ ApiPath (external path)

RequestLog
  └── DetectionLog (model invocation log)
```

### Key Design Points

- **Tag ↔ model**: many-to-many; one detection model can provide multiple detection capabilities
- **Policy → model pool**: many-to-many; the policy selects models carrying the same tag to form the detection model pool
- **Path → policy chain**: ordered many-to-many (`order_index`), executed in order

## Security and Isolation

### 1. Script Sandbox

User-uploaded Python scripts execute in separate subprocesses:
- The main process starts the Python interpreter via `asyncio.create_subprocess_exec`
- Scripts are fully isolated from the main service process; infinite loops or crashes do not affect the main service
- Subprocesses have a timeout and are force-killed when it expires

**Further isolation recommendations** (for production):
- Run inside containers and use cgroups to limit CPU/memory
- Use dedicated sandboxes (e.g., Firecracker, gVisor)

### 2. REST Call Safety

- Uses the `httpx` async client with a configured invocation timeout
- Does not follow redirects by default (reducing SSRF risk)

### 3. Authentication and Authorization

- Admin console: JWT Bearer token, obtained from `/api/auth/login`
- External detection: API Key (`X-API-Key` header); each path can bind an independent key
- Role separation: `admin` can manage users; `operator` only operates business resources

## Performance Optimization

### 1. Async Concurrency

- FastAPI is built on ASGI and naturally supports high concurrency
- The strategy engine calls models asynchronously with asyncio; sequential detection does not block the event loop
- WebSocket broadcasts are asynchronous and non-blocking

### 2. Database Connection Pool

- SQLAlchemy's `sessionmaker` is configured with a connection pool
- `pool_pre_ping=True` automatically detects dead connections

### 3. Frontend Build Optimization

- Vite lazy-loaded routes (`() => import()`)
- On-demand ECharts imports
- Compression and chunk splitting enabled in production builds

## Observability and Monitoring

### Log Levels

- `RequestLog`: one entry per external detection request, including the final result and total elapsed time
- `DetectionLog`: invocation details for each detection model, including per-model elapsed time and verdict status

### Statistical Dimensions

- Cumulative request count, safe/unsafe counts
- Average latency
- Risk type distribution
- Last 7 days trend

### Real-time Observability

- The dashboard receives events pushed over WebSocket; monitoring works with zero configuration
- Admin console query APIs support filtering and pagination

## Extensibility

### Horizontal Scaling

- The backend is stateless and can be deployed in multiple replicas (behind a load balancer)
- WebSocket broadcasts work within a single instance; multiple replicas require Redis Pub/Sub

### Vertical Scaling

- Add detection models: configure them in the admin console, no code changes required
- Add policy rules: extend the invocation rules beyond the existing sequential and random rules
- Add safety tags: users can define arbitrary custom tags

### Integrating External Systems

- Integrate any HTTP detection service via REST
- Integrate security tools from the Python ecosystem (e.g., transformers models) via scripts

## Technology Choices

| Technology | Reason |
|------------|--------|
| FastAPI | Native async, automatic OpenAPI docs, type safety |
| SQLAlchemy 2.x | Mature ORM, multi-database support, async-friendly in 2.x |
| Pydantic | Data validation and serialization, deeply integrated with FastAPI |
| Vue 3 | Composition API, lightweight, mature ecosystem |
| ECharts | Open-source charting library, well suited for data dashboards |
| WebSocket | Real-time push, avoiding polling overhead |
| PBKDF2 | Standard-library implementation with no compile-time dependencies (bcrypt requires local compilation) |
| Docker | Standard containerization; build once, run anywhere |

## Future Improvements

1. **Distributed tracing**: integrate OpenTelemetry to trace cross-model invocation chains
2. **Caching layer**: short-term caching (Redis) of detection results for frequent identical content
3. **A/B testing**: configure multiple policy sets for the same path and distribute traffic by proportion
4. **Model performance profiling**: collect per-model accuracy, latency, and stability statistics to assist policy configuration

---

**Related documents**
- [Quick Start and Deployment](../README_EN.md)
- [API Integration Guide](./INTEGRATION_EN.md)
