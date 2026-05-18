AI Wellness Companion - Step 5

This step adds daily wellness tracking to the working authentication and profile setup app.

What is included:
- User registration and login
- Session-based authentication
- Profile setup and save
- Daily wellness tracker page
- Daily log insert and update
- Dashboard summary using daily log data
- Recent daily log history table
- Password hashing switched to pbkdf2_sha256 for better compatibility

How to run:
1. Open this project folder.
2. Open terminal in the folder where main.py exists.
3. Run:
   python -m pip install -r requirements.txt
4. Run:
   python -m uvicorn main:app --reload
5. Open browser:
   http://127.0.0.1:8000

Important:
- The app uses the SQLite file in database/wellness_app.db
- If you already have a working database from previous steps, you can keep using it.
- This step uses the same schema and adds code to write into daily_wellness_logs.

Suggested test flow:
1. Register or login.
2. Save profile.
3. Open Daily Tracker.
4. Add a log for today.
5. Save it.
6. Open Dashboard and confirm the summary updates.
7. Open Daily Tracker again and edit the same date to confirm update works.
