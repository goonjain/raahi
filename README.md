# RAAHI | राही

### Beyond the Crowds. Into the Extraordinary.

**An AI-Powered Smart Tourism, Crowd Intelligence & Personalized Itinerary Planning Platform**

Raahi is a smart tourism platform designed to transform how travellers explore destinations. Starting with **Jaipur, Rajasthan**, Raahi combines AI-powered recommendations, rule-based itinerary generation, crowd intelligence, interactive maps, local discovery and community participation to make travel more personalized, efficient and informed.

Rather than simply recommending popular attractions, Raahi aims to help travellers make better decisions about **where to go, when to visit and what to explore next**.

**Project developed by:** Aditya Vinayak Singh
                          Goon Jain
                          Alice Sharma
                          Paridhi Poddar
**Project type:** Academic / Software Engineering / Smart Tourism  
**Initial destination:** Jaipur, Rajasthan, India

---

## 1. The Problem

Tourism in popular destinations often faces interconnected challenges:

- **Overcrowding:** Visitors frequently concentrate around a few famous attractions.
- **Inefficient planning:** Traditional itineraries may involve unnecessary travel and poorly arranged schedules.
- **Limited personalization:** Generic recommendations may not account for interests, budgets, travel pace or special requirements.
- **Hidden destinations:** Lesser-known places receive less attention than flagship attractions.
- **Fragmented information:** Tourists may need separate applications for planning, maps, food, crowd information and local experiences.
- **Limited decision support:** Tourism authorities benefit from tools that help monitor visitor pressure and explore crowd-management interventions.

Raahi addresses these challenges through an integrated, AI-assisted tourism planning platform.

## 2. Our Solution

Raahi combines several complementary systems:

1. **AI recommendation engine:** Interprets user interests and suggests attractions.
2. **Retrieval-Augmented Generation (RAG):** Retrieves relevant knowledge to support AI recommendations.
3. **Deterministic itinerary planner:** Converts recommended attractions into structured multi-day schedules while applying planning constraints.
4. **Geographical route optimization:** Reorders attractions to improve location-based travel efficiency.
5. **Crowd intelligence:** Displays crowd-related indicators and supports congestion-aware decisions.
6. **Community and rewards:** Encourages user participation and exploration.
7. **Tourism administration:** Provides dashboard functionality for monitoring and decision support.

The key design principle is that **AI assists with recommendations while deterministic algorithms control itinerary scheduling**.

## 3. Core Features

### AI-Powered Personalized Itineraries

- Interactive tourist preference questionnaire
- Multi-day itinerary generation
- Attraction recommendations using Groq-hosted LLMs
- Lexical RAG-based knowledge retrieval
- Canonical destination validation
- Must-visit attraction support
- Additional Notes for natural-language preferences
- AI-generated recommendation explanations
- Deterministic scheduling and attraction selection
- Automatic geographical reordering
- Replace and Undo functionality
- Fallback itinerary generation when the AI service is unavailable

### Crowd Intelligence

- Crowd-related indicators and congestion categories
- Crowd-aware attraction suggestions
- Visitor-pressure visualization
- Community-contributed crowd observations
- Separate crowd-diversion comparison demonstration

Crowd indicators and simulations should not be interpreted as verified live crowd measurements unless explicitly supported by live data.

### Smart Destination Discovery

- Jaipur attractions and heritage sites
- Popular destinations and lesser-known alternatives
- Hidden-gem discovery
- Interactive attraction information
- Local exploration and geographic visualization

### Food and Local Experiences

- Restaurant discovery
- Food-related recommendations
- Restaurant data enrichment and validation
- Nearby food exploration

**Planned enhancement:** Integrated meal stops within day-wise itinerary timelines, with automatic rescheduling when meals are changed.

### Community Features

- User-contributed tourism and crowd information
- Community interaction functionality
- Administrative moderation interface
- Reward-based participation concepts

**Under improvement:** Community comment verification, rejection, deletion and secure administration.

### Rewards

- Raahi Points concept
- Reward-related user interface and functionality
- Incentives encouraging participation and broader destination exploration

**Planned enhancement:** Persistent account-based reward balances and partner redemption mechanisms.

### Administration Dashboard

- Dedicated `/admin` interface
- Tourism-oriented information and analytics
- Crowd-related management functionality
- Community moderation interface
- Visitor-diversion and decision-support concepts

**Planned enhancement:** Secure role-based administrator authentication and protected backend operations.

## 4. Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Routing | TanStack Router / Start |
| Backend | Python, FastAPI |
| AI inference | Groq API and hosted language model |
| Retrieval | Python-based lexical knowledge retrieval |
| Data validation | Pydantic |
| Itinerary planning | TypeScript deterministic planning algorithms |
| Maps | Leaflet, OpenStreetMap |
| Visualizations | Recharts |
| Frontend testing | Vitest |
| Backend testing | Pytest |
| Version control | Git and GitHub |

Additional infrastructure and persistent storage technologies should be documented according to the actual deployment configuration.

## 5. How Raahi Works

```text
                     TOURIST
                        |
                        v
             Preference Questionnaire
                        |
                        v
                Structured Request
                        |
             +----------+----------+
             |                     |
             v                     v
       Knowledge Retrieval    Tourist Constraints
             |                     |
             v                     |
       Retrieved Context           |
             |                     |
             v                     |
       Groq LLM Recommendations    |
             |                     |
             v                     |
       Proposal Validation         |
             |                     |
             +----------+----------+
                        |
                        v
             Deterministic Planner
                        |
                        v
             Multi-Day Itinerary
                        |
                        v
             Geographic Optimization
                        |
                        v
              Interactive Day View
                        |
              +---------+---------+
              |                   |
              v                   v
       Replace / Undo         AI Explanations
```

### Step-by-Step Explanation

**Step 1 — Collect preferences:** The tourist selects their dates, budget, interests, travel pace, must-visit places and other requirements.

**Step 2 — Retrieve knowledge:** The backend searches relevant knowledge records using lexical retrieval.

**Step 3 — Generate recommendations:** Groq receives the structured request and retrieved context, then proposes suitable attraction IDs and explanations.

**Step 4 — Validate recommendations:** Backend validation filters unsupported identifiers and checks the response structure.

**Step 5 — Build the itinerary:** The deterministic planner uses the validated recommendations alongside scheduling rules and tourist constraints.

**Step 6 — Optimize routes:** Attraction ordering is optimized using available geographic information.

**Step 7 — Display results:** The application renders a day-wise itinerary, with AI explanations when corresponding valid recommendations are available.

**Step 8 — Allow modifications:** Tourists can replace attractions or undo changes without losing the overall planning workflow.

If the AI request fails, the deterministic planning system can still generate an itinerary.

## 6. Project Structure

Important files and directories:

```text
musafir-itinerary-v2/
|
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- schemas.py
|   |   |-- routers/
|   |   |   |-- itinerary_ai.py
|   |   |   |-- itinerary_food.py
|   |   |   |-- ...
|   |   |-- services/
|   |   |   |-- groq_wrapper.py
|   |   |   |-- knowledge.py
|   |   |   |-- ...
|   |   |-- data/
|   |       |-- canonical_destinations.py
|   |-- data/
|   |-- tests/
|
|-- src/
|   |-- components/
|   |   |-- musafir/
|   |       |-- PlannerWizard.tsx
|   |       |-- MultiDayItinerary.tsx
|   |       |-- ...
|   |-- lib/
|   |   |-- itinerary-planner.ts
|   |   |-- api.ts
|   |   |-- ...
|   |-- routes/
|   |   |-- index.tsx
|   |   |-- admin.tsx
|   |-- test/
|       |-- itinerary-flow.test.tsx
|       |-- ...
|
|-- public/
|-- package.json
```

## 7. Local Development

### Prerequisites

- Node.js and npm
- Python with the project's backend dependencies installed
- Git
- A Groq API key for live AI recommendations

### Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd musafir-itinerary-v2
```

### Install Frontend Dependencies

```bash
npm install
```

On Windows PowerShell, use `npm.cmd` if the `npm` script is blocked by your execution policy.

### Configure Environment Variables

Create a frontend environment file such as `.env.local`:

```dotenv
VITE_API_URL=http://localhost:8000/api
```

Configure the backend's environment with:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

`GROQ_MODEL` is optional if the backend uses its configured default.

**Security:** Never commit `.env`, `.env.local`, API keys or other credentials to GitHub. `GROQ_API_KEY` must remain server-side.

### Start the Backend

```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

The backend should be accessible at:

```text
http://127.0.0.1:8000
```

### Start the Frontend

```bash
npm run dev
```

On Windows PowerShell:

```powershell
npm.cmd run dev
```

Open the local URL printed by the development server.

### AI Recommendation Endpoint

```http
POST /v1/itinerary/recommendations
```

The request is processed by the FastAPI backend.

This endpoint provides validated AI proposals; final multi-day scheduling is performed by the existing deterministic frontend planner.

## 8. Deployment Configuration

Raahi's frontend and backend must both be reachable for live AI features to work across devices.

### Frontend Environment

```dotenv
VITE_API_URL=https://YOUR_BACKEND_DOMAIN/api
```

The recommendation endpoint is located outside the `/api` prefix. The frontend derives the backend origin from the configured API URL and calls:

```text
https://YOUR_BACKEND_DOMAIN/v1/itinerary/recommendations
```

### Backend Environment

```dotenv
GROQ_API_KEY=your_production_groq_key
GROQ_MODEL=openai/gpt-oss-20b
```

**Important deployment notes:**

- Do not use `localhost` or `127.0.0.1` as a production browser API destination.
- `VITE_API_URL` must be available during the frontend build.
- The FastAPI service must be deployed and publicly reachable.
- Configure HTTPS, appropriate CORS policies and secure secret management.
- The Groq API key must never be included in frontend environment variables.
- Test the deployed site from a separate device before considering AI deployment verified.

## 9. Testing and Validation

Raahi uses frontend and backend automated tests.

### Frontend Tests

```powershell
npm.cmd test
```

### Production Build

```powershell
npm.cmd run build
```

### Backend Tests

```powershell
python -m pytest backend/tests -q
```

### Git Whitespace Validation

```powershell
git diff --check
```

**Latest reported verification (27 November 2026):**

| Check | Result |
|---|---|
| Frontend tests | 63 passed |
| Backend tests | 28 passed in previous verification |
| Production build | Passed |
| Local multi-day itinerary workflow | Manually verified |
| Cross-device AI Insight | Deployment fix implemented; production verification pending |

These results describe the observed development state and should be updated as the project evolves.

## 10. Data Sources and Limitations

Raahi combines curated destination data, knowledge records, tourist inputs and crowd-related information.

The project has also used publicly available Rajasthan tourism statistics for selected Jaipur destinations.

One official reference is:

Government of Rajasthan — Economic Review 2025–26:  
https://finance.rajasthan.gov.in/docs/budget/statebudget/2026-2027/Economicreviewe.pdf

Historical annual visitor counts must not be described as real-time crowd counts.

Likewise, estimated route ordering should not be presented as guaranteed real-time traffic optimization.

AI-generated recommendations may be incomplete or unavailable during API failures; fallback planning helps maintain application functionality.

## 11. Current Development Status

### Implemented or Prototyped

- AI-assisted attraction recommendations
- Lexical RAG integration
- Validated recommendation API
- Deterministic multi-day scheduling
- Automatic geographical attraction ordering
- Replace and Undo
- AI explanations for matching recommendations
- Jaipur attraction discovery
- Crowd-related interfaces and simulations
- Interactive maps
- Food discovery
- Community participation features
- Rewards prototype
- Admin dashboard
- Legacy crowd-diversion comparison

### In Progress

- Cross-device production verification of AI Insights
- Community Verify / Reject / Delete moderation fixes
- Improved personalization validation
- Data and prediction reliability evaluation

### Planned

- Chronologically integrated meal scheduling
- Secure user and administrator authentication
- Protected backend admin endpoints
- User-specific saved itineraries and profiles
- Persistent account-based rewards
- Improved tourism analytics and data integration
- Further destination coverage beyond Jaipur

## 12. Future Scope

Raahi can evolve into a broader smart tourism platform through:

- Expansion to other cities and tourism circuits
- Better crowd forecasting using verified historical and live observations
- Travel-time-aware itinerary optimization
- Real-time destination advisories
- Local business and experience partnerships
- Offline itinerary access
- Group and collaborative planning
- Multilingual travel assistance
- Data-supported tourism policy and destination management

These are development possibilities, not currently verified production features.

## 13. Project Vision

Raahi is designed around a simple idea:

**Better tourism is not only about visiting more places. It is about making smarter choices, discovering meaningful experiences and reducing unnecessary pressure on popular destinations.**

By combining AI recommendations with structured planning, community insights and destination intelligence, Raahi aims to build a more personalized and responsible way to explore.

---

**RAAHI | राही**  
*Beyond the Crowds. Into the Extraordinary.*


