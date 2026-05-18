AI Wellness Companion - Step 9

This step adds the Daily Recovery Planner - a fully local, rule-based feature
that generates a personalised daily wellness plan for each user.

WHAT IS NEW
- New page: /recovery-planner
- Generates a daily plan with personalised targets for sleep, water, exercise, and steps
- Identifies the habit with the lowest current streak as the Focus Habit for the day
- Provides meal guidance adapted from OCR body composition report metrics (if available)
- Includes a motivational note adjusted to the user's recent wellness score and mood
- Explains why each plan was generated (reason summary)
- Plans are saved to the recovery_plans table (already in the schema) and can be regenerated
- Dashboard shows the latest recovery plan as a summary card with a link to the full page
- Navigation bar updated with Recovery Planner link

HOW THE PLAN IS GENERATED
- Sleep, water, steps, and exercise targets are pulled from your profile goals
- If your latest wellness score shows a weak area (below 70/100), that target is increased slightly
- Focus Habit is the active habit with the lowest current streak
- Meal guidance is based on any OCR report metrics you have uploaded:
    - High visceral fat       > anti-inflammatory, low-sugar guidance
    - High body fat (>= 30%)  > moderate caloric deficit guidance
    - Low body water (< 45%)  > hydrating foods guidance
    - High BMI (>= 25)        > portion and meal timing guidance
    - No report uploaded      > general balanced meal guidance
- Motivational note is based on your latest total wellness score
- Recent mood data from your daily log adjusts the motivational note further

NO API KEY REQUIRED
This step is fully offline and local. No external services are used.

HOW TO RUN
1. Open terminal in the project folder (where main.py is).
2. Run: python -m pip install -r requirements.txt
3. Run: python -m uvicorn main:app --reload
4. Open: http://127.0.0.1:8000

TEST FLOW
1. Login
2. Make sure you have at least one daily log saved (for scores to exist)
3. Open Recovery Planner from the navigation bar
4. Click Generate Today's Plan
5. Review the targets, focus habit, meal guidance, and motivational note
6. Open Dashboard and confirm the recovery plan summary card appears
7. Upload an OCR health report from the Report Analyzer, then regenerate the plan
   and verify that meal guidance reflects your body composition metrics

NOTES
- Plans are stored per user per date. Regenerating replaces the existing plan for that date.
- If no score data exists yet, default profile goals are used as plan targets.
- If no habits exist, the Focus Habit section shows a prompt to create habits.
