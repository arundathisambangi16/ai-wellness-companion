AI Wellness Companion - Step 10

This step adds the local Wellness Coach chat experience.

WHAT IS NEW
- New page: /coach
- Session-based wellness chat stored in SQLite
- OpenAI-backed responses using `OPENAI_MODEL=gpt-5.4-nano` by default
- New chat sessions can be created from the UI
- Dashboard and navigation now link to the coach
- Report analyzer now accepts pasted text as a fallback when OCR is not available locally

HOW TO RUN
1. Open the project folder where main.py lives.
2. Install dependencies if needed:
   python -m pip install -r requirements.txt
3. Start the app:
   python -m uvicorn main:app --reload
4. Open:
   http://127.0.0.1:8000

NOTE
- The app automatically reads local config from this project folder on startup.
- It prefers `./.env` if you create one later, but will also use `./.env.example` if that is the only local file you have.

TEST FLOW
1. Register or login.
2. Fill out your profile.
3. Add a daily log and a few habits.
4. Upload an OCR report if you have one.
5. Open the Wellness Coach and ask about sleep, hydration, habits, or recovery planning.
6. Start a new chat session and confirm it appears in the session sidebar.

NOTES
- The coach is fully local and does not require an API key.
- Responses are rule-based and grounded in the data already stored in the app.
