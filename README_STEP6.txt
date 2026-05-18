AI Wellness Companion - Step 6

What this step adds:
- Habit creation
- Habit status tracking by date
- Habit summary KPIs
- Habit streak overview on dashboard
- Recent habit activity table

How to run:
1. Open terminal in this folder (where main.py exists)
2. Run: python -m pip install -r requirements.txt
3. Run: python -m uvicorn main:app --reload
4. Open: http://127.0.0.1:8000

What to test:
1. Login
2. Open /habits
3. Create at least 2 habits
4. Save status for today's date
5. Open dashboard and verify habit KPIs/streaks appear
