
STEP 4 - AUTHENTICATION AND PROFILE SETUP

WHAT THIS STEP ADDS
1. User registration
2. User login
3. Password hashing using passlib + bcrypt
4. Session-based login persistence
5. Protected dashboard
6. User profile form connected to SQLite

HOW TO RUN

1. Extract the project ZIP.
2. Open the AI_Wellness_Companion_Project folder.
3. Click the folder path bar, type cmd, and press Enter.

4. Install packages:
   python -m pip install -r requirements.txt

   If python does not work:
   py -m pip install -r requirements.txt

5. Start the app:
   python -m uvicorn main:app --reload

   If python does not work:
   py -m uvicorn main:app --reload

6. Open this in your browser:
   http://127.0.0.1:8000

PAGES AVAILABLE NOW
- /
- /register
- /login
- /dashboard
- /profile
- /health

TEST FLOW
1. Open the homepage.
2. Register a new user.
3. Login with that account.
4. Open Profile and save profile data.
5. Open Dashboard and verify the saved data appears.

IMPORTANT
- Run commands from the folder where main.py exists.
- The SQLite database file is created in:
  database/wellness_app.db
