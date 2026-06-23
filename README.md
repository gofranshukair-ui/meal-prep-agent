# Meal Prep Agent

A FastAPI service that uses LangGraph and Google Gemini to generate a five-day meal plan and shopping list from dietary preferences.

## Features

- Clean architecture with domain, adapter, workflow, and API layers
- Typed Python with `pydantic` request/response models
- LangGraph tasks and workflow orchestration
- Gemini-powered meal plan generation

## Setup

1. Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Copy the example env file:

```bash
cp .env.example .env
```

3. Set your Gemini API key in `.env`:

```text
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL_NAME=models/chat-bison-001
```

If `models/gemini-1.5-flash` is not available for your account, use a supported model from `genai.list_models()` or a fallback such as `models/chat-bison-001`.

4. Run the app:

```bash
uvicorn app.api:app --reload
```

Open http://127.0.0.1:8000 in your browser.

## Deploy to Render

1. Push this repo to GitHub:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/meal-prep-agent.git
git push -u origin main
```

2. Create a [Render](https://render.com) account and go to **New → Blueprint**.

3. Connect your GitHub repo. Render reads [`render.yaml`](render.yaml) and creates the web service.

4. When prompted, set `GEMINI_API_KEY` (from [Google AI Studio](https://aistudio.google.com/apikey)).

5. Wait for the build to finish (~2–5 min). Render assigns a public HTTPS URL such as `https://meal-prep-agent.onrender.com`.

6. Verify the deployment:
   - Open the Render URL — the meal planner UI should load
   - Generate a meal plan to confirm the Gemini API key works
   - Visit `/docs` for the API reference

**Notes:**
- The free tier spins down after ~15 minutes of inactivity; the first request after idle may take 30–60 seconds.
- Never commit `.env`. Use Render Environment variables for secrets.
- SQLite data is stored on a persistent disk at `/var/data/workflow_state.db`.

## API

POST `/meal-plan`

Request body:

```json
{
  "meals_per_day": 3,
  "calories_per_day": 2000,
  "dietary_restrictions": ["vegetarian"],
  "cuisines": ["Mediterranean", "Mexican"],
  "avoid_ingredients": ["peanuts", "shellfish"]
}
```

Response body:

```json
{
  "raw_meal_plan": "...",
  "raw_shopping_list": "...",
  "daily_plan": ["..."],
  "shopping_items": ["..."]
}
```
