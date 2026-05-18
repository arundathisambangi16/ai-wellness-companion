from database import get_connection
from services.auth_service import get_profile_by_user_id
from services.wellness_service import get_recent_daily_logs
from services.score_service import get_latest_score, get_score_history
from services.habit_service import get_active_habits, get_habit_streaks
from services.ocr_service import get_latest_report


def generate_recovery_plan(user_id: int, plan_date: str) -> dict:
    profile = get_profile_by_user_id(user_id)
    latest_score = get_latest_score(user_id)
    recent_logs = get_recent_daily_logs(user_id, limit=3)
    habits = get_active_habits(user_id)
    habit_streaks = get_habit_streaks(user_id)
    latest_report = get_latest_report(user_id)

    # Base targets from profile
    sleep_goal = float(profile.get("sleep_goal_hours") or 8) if profile else 8.0
    water_goal = float(profile.get("water_goal_liters") or 2.5) if profile else 2.5
    steps_goal = int(profile.get("steps_goal") or 8000) if profile else 8000
    exercise_goal = int(profile.get("exercise_goal_minutes") or 30) if profile else 30

    sleep_target = sleep_goal
    water_target = water_goal
    steps_target = steps_goal
    exercise_target = exercise_goal
    reasons = []

    # Adjust targets upward for weak score areas
    if latest_score:
        if (latest_score.get("sleep_score") or 100) < 70:
            sleep_target = min(sleep_goal + 0.5, 9.0)
            reasons.append("sleep score was below target")
        if (latest_score.get("hydration_score") or 100) < 70:
            water_target = min(water_goal + 0.5, 4.0)
            reasons.append("hydration was below target")
        if (latest_score.get("activity_score") or 100) < 70:
            exercise_target = min(exercise_goal + 10, 60)
            steps_target = min(steps_goal + 1000, 15000)
            reasons.append("activity score was below target")
        if (latest_score.get("mood_score") or 100) < 55:
            reasons.append("mood balance needed attention")

    # Focus habit: pick the habit with the lowest streak
    focus_habit = None
    if habit_streaks:
        lowest = min(habit_streaks, key=lambda h: h.get("streak", 9999))
        focus_habit = lowest.get("habit_name")
    elif habits:
        focus_habit = habits[0]["habit_name"]

    # Meal guidance — adjusted by OCR body composition metrics if available
    meal_guidance = (
        "Maintain balanced meals with lean protein, vegetables, and complex carbohydrates."
    )
    if latest_report and latest_report.get("metrics"):
        metric_map = {m["metric_name"]: m for m in latest_report["metrics"]}
        body_fat = metric_map.get("Body Fat")
        water_pct = metric_map.get("Body Water")
        bmi = metric_map.get("BMI")
        visceral = metric_map.get("Visceral Fat")

        if visceral and visceral["metric_value"] >= 10:
            meal_guidance = (
                "Reduce high-sugar, high-fat processed foods. Focus on fiber-rich vegetables, "
                "lean proteins, and avoid late-night eating to support visceral fat reduction."
            )
        elif body_fat and body_fat["metric_value"] >= 30:
            meal_guidance = (
                "Focus on a moderate caloric deficit. Prioritize lean protein and fiber-rich foods. "
                "Minimize processed carbs and sugary drinks."
            )
        elif water_pct and water_pct["metric_value"] < 45:
            meal_guidance = (
                "Eat hydrating foods such as cucumbers, watermelon, and leafy greens alongside "
                "your hydration targets throughout the day."
            )
        elif bmi and bmi["metric_value"] >= 25:
            meal_guidance = (
                "Keep portion sizes moderate and prioritize whole foods. Avoid skipping meals, "
                "and time larger meals earlier in the day."
            )

    # Motivational note based on overall score
    total_score = latest_score.get("total_score") if latest_score else None
    if total_score is None:
        motivational_note = (
            "Start today — even a small step toward your wellness goal makes a real difference."
        )
    elif total_score >= 80:
        motivational_note = (
            "You are performing well. Stay consistent and trust the process. "
            "Small daily habits compound into lasting results."
        )
    elif total_score >= 60:
        motivational_note = (
            "You are making steady progress. Focus on the areas highlighted in today's plan "
            "and keep showing up — consistency matters more than perfection."
        )
    else:
        motivational_note = (
            "Today is a fresh start. Use this plan as a guide, not a pressure. "
            "Every positive choice you make counts toward your progress."
        )

    # Check mood from most recent log for additional note
    if recent_logs:
        mood = (recent_logs[0].get("mood") or "").lower()
        if mood in {"stressed", "anxious"}:
            motivational_note += (
                " Your recent mood suggests you may need recovery time. "
                "Include a 10-minute breathing or relaxation break in your day."
            )
        elif mood in {"tired", "sad"}:
            motivational_note += (
                " Prioritise rest and avoid overcommitting today. "
                "A consistent sleep schedule is the fastest path to better energy."
            )

    generated_reason = (
        "This plan was generated based on your recent wellness data. "
        + (
            f"Key areas that shaped today's targets: {', '.join(reasons)}. "
            if reasons
            else "Your recent scores are balanced. "
        )
        + "Targets are adjusted from your profile goals to reflect your current progress."
    )

    return {
        "user_id": user_id,
        "plan_date": plan_date,
        "sleep_target_hours": round(sleep_target, 1),
        "water_target_liters": round(water_target, 1),
        "exercise_target_minutes": int(exercise_target),
        "steps_target": int(steps_target),
        "focus_habit": focus_habit,
        "meal_guidance": meal_guidance,
        "motivational_note": motivational_note,
        "generated_reason": generated_reason,
    }


def save_recovery_plan(plan: dict) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM recovery_plans WHERE user_id = ? AND plan_date = ?",
            (plan["user_id"], plan["plan_date"]),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE recovery_plans
                SET sleep_target_hours = ?, water_target_liters = ?, exercise_target_minutes = ?,
                    steps_target = ?, focus_habit = ?, meal_guidance = ?,
                    motivational_note = ?, generated_reason = ?
                WHERE user_id = ? AND plan_date = ?
                """,
                (
                    plan["sleep_target_hours"],
                    plan["water_target_liters"],
                    plan["exercise_target_minutes"],
                    plan["steps_target"],
                    plan["focus_habit"],
                    plan["meal_guidance"],
                    plan["motivational_note"],
                    plan["generated_reason"],
                    plan["user_id"],
                    plan["plan_date"],
                ),
            )
            conn.commit()
            return int(existing["id"])
        else:
            cursor = conn.execute(
                """
                INSERT INTO recovery_plans (
                    user_id, plan_date, sleep_target_hours, water_target_liters,
                    exercise_target_minutes, steps_target, focus_habit,
                    meal_guidance, motivational_note, generated_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan["user_id"],
                    plan["plan_date"],
                    plan["sleep_target_hours"],
                    plan["water_target_liters"],
                    plan["exercise_target_minutes"],
                    plan["steps_target"],
                    plan["focus_habit"],
                    plan["meal_guidance"],
                    plan["motivational_note"],
                    plan["generated_reason"],
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)


def get_recovery_plan_by_date(user_id: int, plan_date: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM recovery_plans WHERE user_id = ? AND plan_date = ? LIMIT 1",
            (user_id, plan_date),
        ).fetchone()
        return dict(row) if row else None


def get_latest_recovery_plan(user_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM recovery_plans WHERE user_id = ? ORDER BY plan_date DESC, id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def get_recent_recovery_plans(user_id: int, limit: int = 7):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM recovery_plans WHERE user_id = ? ORDER BY plan_date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
