# TripPilot AI

An AI travel planner that creates flight guidance, hotel suggestions, weather context, and day-by-day itineraries.

It uses a human-in-the-loop checkpoint: if a request is missing important trip details, the LangGraph workflow pauses and the React app shows a structured form. Planning resumes only after the user completes it.

## Stack

- React + Vite + Tailwind CSS
- FastAPI
- LangGraph with PostgreSQL checkpoints
- Neon Postgres
- Gemini 2.5 Flash
- Tavily, AviationStack, and OpenWeather APIs

## Project Structure

```text
Backend/            FastAPI, LangGraph workflow, MCP clients
frontend/           React application
frontend/public/    Static assets
render.yaml         Render backend deployment config
.env                Local secrets (not committed)
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- Neon Postgres database
- Gemini API key from Google AI Studio

## Environment Variables

Create `.env` in the project root:

```env
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
GEMINI_API_KEY=AIza_your_google_ai_studio_key
TAVILY_API_KEY=your_tavily_key
AVIATIONSTACK_API_KEY=your_aviationstack_key
OPENWEATHER_API_KEY=your_openweather_key
DEFAULT_ORIGIN_IATA=DAC
CORS_ORIGINS=http://localhost:5173
```

`GEMINI_API_KEY` must begin with `AIza`.

## Run Locally

Install backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r Backend\requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
```

Start the API in one terminal:

```powershell
cd "D:\Travel agent\Backend"
..\.venv\Scripts\python.exe app.py
```

Start React in another terminal:

```powershell
cd "D:\Travel agent\frontend"
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

## Human-in-the-Loop Flow

1. The graph parses the first travel request into structured fields.
2. If destination, duration, dates, budget, or style is missing, execution interrupts and state is saved in Postgres.
3. The frontend renders only missing fields as text inputs or select buttons.
4. Form values merge with the existing structured intent and are validated again.
5. When the intent is ready, the workflow runs flights, hotels, weather, itinerary, and final response nodes.

## Deploy

### Backend: Render

Push the repository to GitHub, then create a Render Web Service using [render.yaml](render.yaml), or configure:

```text
Runtime: Python
Root Directory: Backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

Set all environment variables from `.env`. Use the Neon connection string as `DATABASE_URL`.

### Frontend: Vercel

Import the same repository into Vercel:

```text
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
```

Add:

```env
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

Update the Render service:

```env
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

## API

`POST /api/travel`

Initial request:

```json
{
  "message": "Plan a Goa trip",
  "thread_id": null
}
```

If clarification is needed, the response includes `status: "needs_clarification"`, `thread_id`, and `missing_slots`.

Resume request:

```json
{
  "thread_id": "saved-thread-id",
  "answers": {
    "duration_days": 5,
    "travel_dates": "12-16 October 2026",
    "budget": "Mid-range",
    "travel_style": ["Relaxed", "Food"]
  }
}
```

## Health Check

```text
GET /health
```

Expected response:

```json
{"status":"ok","message":"AI Travel Planner API is running"}
```
