from database import get_connection


def _to_int(v):
    return int(v) if str(v).strip() else None


def _to_float(v):
    return float(v) if str(v).strip() else None


def upsert_daily_log(
    user_id: int,
    log_date: str,
    sleep_hours: str,
    water_intake_liters: str,
    steps_count: str,
    exercise_minutes: str,
    calories_burned: str,
    mood: str,
    stress_level: str,
    notes: str,
) -> None:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_wellness_logs WHERE user_id = ? AND log_date = ?",
            (user_id, log_date),
        ).fetchone()

        values = (
            _to_float(sleep_hours),
            _to_float(water_intake_liters),
            _to_int(steps_count),
            _to_int(exercise_minutes),
            _to_float(calories_burned),
            mood.strip() or None,
            _to_int(stress_level),
            notes.strip() or None,
        )

        if existing:
            conn.execute(
                """
                UPDATE daily_wellness_logs
                SET sleep_hours = ?,
                    water_intake_liters = ?,
                    steps_count = ?,
                    exercise_minutes = ?,
                    calories_burned = ?,
                    mood = ?,
                    stress_level = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND log_date = ?
                """,
                values + (user_id, log_date),
            )
        else:
            conn.execute(
                """
                INSERT INTO daily_wellness_logs (
                    user_id, log_date, sleep_hours, water_intake_liters, steps_count,
                    exercise_minutes, calories_burned, mood, stress_level, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, log_date) + values,
            )
        conn.commit()


def get_daily_log_by_date(user_id: int, log_date: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_wellness_logs WHERE user_id = ? AND log_date = ?",
            (user_id, log_date),
        ).fetchone()
        return dict(row) if row else None


def get_recent_daily_logs(user_id: int, limit: int = 7):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM daily_wellness_logs
            WHERE user_id = ?
            ORDER BY log_date DESC, created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_tracking_days_count(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT log_date) AS tracking_days
            FROM daily_wellness_logs
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return int(row["tracking_days"] or 0) if row else 0


def get_dashboard_summary(user_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_logs,
                ROUND(AVG(sleep_hours), 1) AS avg_sleep,
                ROUND(AVG(water_intake_liters), 1) AS avg_water,
                ROUND(AVG(steps_count), 0) AS avg_steps,
                ROUND(AVG(exercise_minutes), 0) AS avg_exercise
            FROM daily_wellness_logs
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else {
            "total_logs": 0,
            "avg_sleep": None,
            "avg_water": None,
            "avg_steps": None,
            "avg_exercise": None,
        }
