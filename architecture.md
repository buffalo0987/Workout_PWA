# System Architecture & Technical Specification
## Self-Hosted Progressive Overload & Nutrition Workout PWA

---

## 1. Executive Summary & Tech Stack Choices

- **Backend Framework**: **Python (FastAPI)**
  - *Rationale*: High performance, native async support, first-class typing with Pydantic, seamless integration with AI/ML/data analysis libraries, background tasks for offline sync & LLM calls, and automatic OpenAPI documentation.
- **Database & ORM**: **PostgreSQL** (via `SQLAlchemy 2.0` async + `Alembic`) with SQLite compatibility for ultra-lightweight environments.
  - *Rationale*: Robust JSONB support for workout logs/snapshots, concurrent watch sync, and reliable long-term analytics.
- **Frontend / PWA**: **React / Vite + TypeScript + Tailwind CSS**
  - *Rationale*: PWA support via `@vite-pwa/plugin`, offline-first state management via Dexie.js (IndexedDB) with background synchronization to the backend.
- **Deployment**: **Docker Compose** optimized for Proxmox LXC / VM deployments, reverse-proxied via Nginx / Traefik.
- **External Integrations**:
  - **Ollama**: Local LLM endpoint (`http://host.docker.internal:11434` or custom URL) for progressive overload recommendation logic.
  - **SparkyFitness**: Self-hosted REST API client pulling daily calorie/macro totals and workout logs for holistic recovery analysis.

---

## 2. Directory Tree Structure

```text
workout-app/
├── docker-compose.yml
├── .env.example
├── README.md
├── architecture.md
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── app/
│       ├── main.py                     # FastAPI app factory, middleware, lifespan
│       ├── config.py                   # Environment & settings via Pydantic Settings
│       ├── database.py                 # Async SQLAlchemy engine & session dependency
│       │
│       ├── models/                     # SQLAlchemy ORM definitions
│       │   ├── __init__.py
│       │   ├── user.py
│       │   ├── exercise.py
│       │   ├── routine.py
│       │   ├── workout.py
│       │   ├── nutrition.py
│       │   └── watch_device.py
│       │
│       ├── schemas/                    # Pydantic models for request/response validation
│       │   ├── __init__.py
│       │   ├── common.py
│       │   ├── exercise.py
│       │   ├── routine.py
│       │   ├── workout.py
│       │   ├── nutrition.py
│       │   ├── ai.py
│       │   └── watch.py
│       │
│       ├── api/                        # Route controllers grouped by domain
│       │   ├── v1/
│       │   │   ├── __init__.py
│       │   │   ├── router.py           # API v1 aggregator
│       │   │   ├── auth.py             # Auth & user management
│       │   │   ├── exercises.py        # Exercise library & PR endpoints
│       │   │   ├── routines.py         # Workout templates / splits
│       │   │   ├── workouts.py         # Workout sessions & live logging
│       │   │   ├── nutrition.py        # SparkyFitness sync & macro history
│       │   │   ├── ai.py               # Ollama recommendation endpoints
│       │   │   └── watch.py            # Watch REST & WebSocket endpoints
│       │   └── deps.py                 # Dependency injections (Auth, DB session)
│       │
│       ├── services/                   # Business logic & external API clients
│       │   ├── __init__.py
│       │   ├── progressive_overload.py # Overload formula computation & prompt builder
│       │   ├── ollama_client.py        # Async client for local Ollama server
│       │   ├── sparky_client.py        # Async client for SparkyFitness REST API
│       │   └── watch_sync_service.py   # State synchronization for wearable devices
│       │
│       └── utils/
│           ├── logger.py
│           └── units.py                # kg/lbs conversions, RPE calculators
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   │   ├── favicon.ico
│   │   ├── icons/                      # PWA icons (192x192, 512x512, maskable)
│   │   └── manifest.webmanifest        # PWA Web Manifest
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── sw.ts                       # Custom Service Worker with background sync
│       │
│       ├── assets/
│       ├── components/                 # Reusable UI components
│       │   ├── common/                 # Button, Input, Modal, Drawer, Toast
│       │   ├── layout/                 # Mobile shell, Header, BottomNav
│       │   ├── workout/                # SetRow, RestTimer, ExercisePicker, OverloadBadge
│       │   └── nutrition/              # MacroSummaryCard, CalorieGauge
│       │
│       ├── pages/                      # Application route views
│       │   ├── DashboardPage.tsx       # Quick start, recent recovery & readiness
│       │   ├── WorkoutActivePage.tsx   # Mobile-optimized live logging screen
│       │   ├── HistoryPage.tsx         # Workout logs & volume charts
│       │   ├── RoutinesPage.tsx        # Split and template editor
│       │   ├── NutritionPage.tsx       # Sparky sync details & AI recovery suggestions
│       │   └── SettingsPage.tsx        # Ollama/Sparky configs, offline sync status
│       │
│       ├── db/                         # Client-side offline storage
│       │   ├── offlineDb.ts            # Dexie.js (IndexedDB) schema
│       │   └── syncEngine.ts           # Conflict resolution & bidirectional queue sync
│       │
│       ├── hooks/                      # Custom hooks
│       │   ├── useWorkoutSession.ts
│       │   ├── useOfflineSync.ts
│       │   └── useRestTimer.ts
│       │
│       ├── services/                   # API clients
│       │   ├── api.ts                  # Axios/Fetch wrapper with JWT/auth header
│       │   └── ws.ts                   # WebSocket client
│       │
│       └── types/                      # Frontend TypeScript contracts
│           └── index.ts
│
└── watch-spec/                         # Wearable protocol docs & payloads
    └── watch_protocol.md
```

---

## 3. Database Schema

### 3.1 Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ ROUTINES : "creates"
    USERS ||--o{ WORKOUT_SESSIONS : "performs"
    USERS ||--o{ NUTRITION_LOGS : "syncs"
    USERS ||--o{ WATCH_DEVICES : "pairs"
    
    ROUTINES ||--o{ ROUTINE_EXERCISES : "contains"
    EXERCISES ||--o{ ROUTINE_EXERCISES : "referenced by"
    
    WORKOUT_SESSIONS ||--o{ WORKOUT_EXERCISES : "logs"
    EXERCISES ||--o{ WORKOUT_EXERCISES : "performed in"
    
    WORKOUT_EXERCISES ||--o{ EXERCISE_SETS : "has"
    WORKOUT_EXERCISES ||--o{ AI_RECOMMENDATIONS : "receives"

    USERS {
        uuid id PK
        string email
        string hashed_password
        string name
        string unit_preference "kg | lbs"
        jsonb settings
        timestamp created_at
        timestamp updated_at
    }

    EXERCISES {
        uuid id PK
        uuid user_id FK "nullable for global exercises"
        string name
        string category "barbell, dumbbell, machine, cable, bodyweight"
        string primary_muscle
        string[] secondary_muscles
        boolean is_custom
    }

    ROUTINES {
        uuid id PK
        uuid user_id FK
        string title
        text description
        boolean is_archived
        timestamp created_at
    }

    ROUTINE_EXERCISES {
        uuid id PK
        uuid routine_id FK
        uuid exercise_id FK
        int order_index
        int target_sets
        int min_reps
        int max_reps
        int rest_seconds
    }

    WORKOUT_SESSIONS {
        uuid id PK
        uuid user_id FK
        uuid routine_id FK "nullable"
        string name
        string status "in_progress | completed | discarded"
        timestamp started_at
        timestamp ended_at
        text notes
        string source "mobile_pwa | watch | web"
        string sync_id "id from offline client"
    }

    WORKOUT_EXERCISES {
        uuid id PK
        uuid workout_session_id FK
        uuid exercise_id FK
        int order_index
        text notes
    }

    EXERCISE_SETS {
        uuid id PK
        uuid workout_exercise_id FK
        int set_number
        string set_type "warmup | working | dropset | failure"
        numeric weight
        int reps
        numeric rpe "Rate of Perceived Exertion (1-10)"
        int rest_after_seconds
        boolean is_completed
        timestamp completed_at
    }

    AI_RECOMMENDATIONS {
        uuid id PK
        uuid workout_exercise_id FK "nullable"
        uuid user_id FK
        string recommendation_type "progressive_overload | recovery_nutrition"
        jsonb input_context
        jsonb suggested_targets "weight, reps, sets, rationale"
        string raw_response
        string model_used
        timestamp created_at
    }

    NUTRITION_LOGS {
        uuid id PK
        uuid user_id FK
        date log_date
        numeric calories
        numeric protein_grams
        numeric carbs_grams
        numeric fat_grams
        numeric water_ml
        jsonb raw_sparky_payload
        timestamp synced_at
    }

    WATCH_DEVICES {
        uuid id PK
        uuid user_id FK
        string device_id
        string device_type "wear_os | apple_watch"
        string device_name
        string pairing_token
        timestamp last_seen_at
    }
```

### 3.2 Key Database Design Considerations
- **Offline Idempotency**: `sync_id` (UUID generated on the client/watch) with unique constraints per user ensures offline duplicate logs do not double-record sets.
- **RPE & Intensity Tracking**: RPE (Rate of Perceived Exertion) and RIR (Reps in Reserve) are captured per set, vital for the Ollama progressive overload calculations.
- **JSONB Context Storage**: `AI_RECOMMENDATIONS.input_context` retains past set metrics and prompt data to evaluate recommendation accuracy over time.

---

## 4. REST & WebSocket API Specification

### 4.1 Authentication & Profile
- `POST /api/v1/auth/register` - Create account.
- `POST /api/v1/auth/login` - Obtain JWT access/refresh token pair.
- `GET /api/v1/auth/me` - Fetch active user profile and preferences.

---

### 4.2 Workouts & Progression Endpoints

#### `GET /api/v1/workouts/history`
- Query params: `limit`, `offset`, `from_date`, `to_date`, `exercise_id`
- Returns paginated list of past workouts with completed exercises, sets, and computed volumes.

#### `POST /api/v1/workouts/sessions`
- Initializes a new live workout session.
- **Request Body**:
```json
{
  "routine_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "name": "Push Day A",
  "source": "mobile_pwa",
  "sync_id": "c71e892d-f9e4-4d8b-8ee9-23c3b0de067f",
  "started_at": "2026-09-16T18:30:00Z"
}
```

#### `POST /api/v1/workouts/sessions/{id}/sets`
- Real-time logging of an individual set.
- **Request Body**:
```json
{
  "workout_exercise_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "set_number": 1,
  "set_type": "working",
  "weight": 80.0,
  "reps": 8,
  "rpe": 8.5,
  "is_completed": true,
  "completed_at": "2026-09-16T18:35:12Z"
}
```

#### `POST /api/v1/workouts/sync/batch`
- Used by PWA (Service Worker) and Watch devices when reconnecting after offline training.
- **Request Body**: Accepts an array of full or partial workout sessions, exercises, and sets with client-generated UUIDs.
- **Response**: `{ "synced": 1, "conflicts": [], "server_timestamp": "..." }`.

---

### 4.3 AI Integration 1: Ollama Progressive Overload Engine

#### `POST /api/v1/ai/progressive-overload/suggest`
- Calculates optimal progressive overload targets for an exercise before or during a workout.
- **Request Body**:
```json
{
  "exercise_id": "a2c16f21-7290-4c31-8ff8-e6b77be32e3a",
  "routine_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "current_weight": 80.0,
  "target_rep_range": [8, 12],
  "session_fatigue_score": 3
}
```
- **Service Operation**:
  1. Backend pulls the last 3-5 sessions of `exercise_id` (weight, reps, RPE, rest times).
  2. Aggregates trend (e.g. hit 80kg x 12 @ RPE 8 -> ready for weight increment).
  3. Constructs a structured prompt sent to local Ollama (`http://host.docker.internal:11434/api/generate` or `/api/chat`).
  4. Ollama returns a JSON schema response parsed into structured targets.
- **Response Payload**:
```json
{
  "exercise_id": "a2c16f21-7290-4c31-8ff8-e6b77be32e3a",
  "suggested_sets": 3,
  "suggested_weight": 82.5,
  "target_reps": "8-10",
  "strategy": "weight_increase",
  "rationale": "You completed 3x12 at 80kg with an average RPE of 8.0 in your previous session. Increasing weight by 2.5kg for 8 reps matches double-progression protocol.",
  "confidence_score": 0.92
}
```

---

### 4.4 AI Integration 2: SparkyFitness Sync & Recovery Advisor

#### `POST /api/v1/nutrition/sparky/sync`
- Pulls data from the configured SparkyFitness instance (or receives webhooks from SparkyFitness).
- **Backend Action**: Calls `GET {SPARKY_API_URL}/api/v1/nutrition/summary?date=YYYY-MM-DD` using the user's stored API token.
- Saves macros into `NUTRITION_LOGS`.

#### `POST /api/v1/ai/recovery-analysis`
- Correlates nutrition intake from SparkyFitness with workout volume to generate actionable recovery feedback.
- **Request Body**:
```json
{
  "workout_session_id": "c71e892d-f9e4-4d8b-8ee9-23c3b0de067f",
  "days_lookback": 3
}
```
- **Prompt Logic**:
  - Context passed to Ollama:
    - Recent volume load (total sets, tonnage).
    - Average protein intake vs body weight (e.g., 140g vs 80kg body weight = 1.75g/kg).
    - Caloric surplus/deficit estimated from SparkyFitness.
- **Response**:
```json
{
  "readiness_score": 78,
  "macro_evaluation": {
    "protein_status": "adequate",
    "calorie_balance": "slight_deficit"
  },
  "recommendation": "Yesterday's heavy leg session generated 14,200kg volume. Your protein intake was 165g (on target), but total calories were in a 350 kcal deficit. Prioritize carbohydrate replenishment before tomorrow's Push session to maintain training intensity.",
  "suggested_rest_hours": 36
}
```

---

### 4.5 Watch API (Wear OS & Apple Watch Sync)

#### `GET /api/v1/watch/active-workout`
- Lightweight minimal JSON (< 2KB) optimized for low-power watch network requests.
- Returns current exercise name, current set number, previous set weight/reps, and active rest timer.

#### `POST /api/v1/watch/log-set`
- Low-latency endpoint to log set completion and advance to the next set.
- Returns `{ "next_exercise": "Incline DB Press", "target_reps": 10, "target_weight": 28.0, "rest_seconds": 90 }`.

#### `WebSocket /api/v1/watch/ws?device_id={device_id}&token={token}`
- Bi-directional synchronization between Mobile PWA and Smartwatch.
- **Messages**:
  - `SET_COMPLETED`: Watch logs set -> Mobile immediately updates active UI.
  - `REST_TIMER_START`: Rest countdown broadcast to watch haptics.
  - `HEART_RATE_STREAM`: Watch streams HR data to session recorder.

---

## 5. Offline-First Architecture & Service Worker Strategy

1. **Client Storage**:
   - IndexedDB managed via **Dexie.js**.
   - Stores active workout sessions, routines, exercise catalog, and an `outbox_queue` of un-synced operations.
2. **Service Worker Sync**:
   - Uses `workbox-background-sync` or custom `SyncManager` API.
   - When offline, set logs and session changes are committed to IndexedDB immediately and queued with client timestamps.
   - On connection restoration (`navigator.onLine` / `sync` event), outbox events are batched to `POST /api/v1/workouts/sync/batch`.
3. **Conflict Resolution**:
   - Last-write-wins based on client monotonic timestamps for editable set fields.
   - Idempotent set IDs prevent duplicate rows.

---

## 6. Docker & Self-Hosted Proxmox Deployment

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: workout_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: workout_user
      POSTGRES_PASSWORD: workout_secure_password
      POSTGRES_DB: workout_app
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal_net

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: workout_backend
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql+asyncpg://workout_user:workout_secure_password@postgres:5432/workout_app
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
      - SPARKY_BASE_URL=http://sparky.internal:8080
      - JWT_SECRET=change_this_in_production
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - postgres
    networks:
      - internal_net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: workout_frontend
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      - backend
    networks:
      - internal_net

volumes:
  postgres_data:

networks:
  internal_net:
    driver: bridge
```
