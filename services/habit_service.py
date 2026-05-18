from database import get_connection


def create_habit(user_id: int, habit_name: str, description: str, category: str, target_frequency: str):
    habit_name = (habit_name or '').strip()
    if not habit_name:
        return False, 'Habit name is required.'

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO habits (user_id, habit_name, description, category, target_frequency)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                habit_name,
                (description or '').strip() or None,
                (category or '').strip() or None,
                (target_frequency or '').strip() or 'Daily',
            ),
        )
        conn.commit()
    return True, 'Habit created successfully.'


def get_active_habits(user_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM habits
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_habit_status(user_id: int, habit_id: int, log_date: str, status: str, notes: str = ''):
    with get_connection() as conn:
        existing = conn.execute(
            'SELECT id FROM habit_logs WHERE habit_id = ? AND user_id = ? AND log_date = ?',
            (habit_id, user_id, log_date),
        ).fetchone()

        clean_status = (status or '').strip() or 'completed'
        clean_notes = (notes or '').strip() or None

        if existing:
            conn.execute(
                """
                UPDATE habit_logs
                SET status = ?, notes = ?
                WHERE id = ?
                """,
                (clean_status, clean_notes, existing['id']),
            )
        else:
            conn.execute(
                """
                INSERT INTO habit_logs (habit_id, user_id, log_date, status, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (habit_id, user_id, log_date, clean_status, clean_notes),
            )
        conn.commit()


def get_habit_status_map(user_id: int, log_date: str):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT habit_id, status, notes
            FROM habit_logs
            WHERE user_id = ? AND log_date = ?
            """,
            (user_id, log_date),
        ).fetchall()
        return {r['habit_id']: {'status': r['status'], 'notes': r['notes']} for r in rows}


def get_recent_habit_logs(user_id: int, limit: int = 20):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT hl.log_date, hl.status, h.habit_name, h.category
            FROM habit_logs hl
            INNER JOIN habits h ON hl.habit_id = h.id
            WHERE hl.user_id = ?
            ORDER BY hl.log_date DESC, hl.created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_habit_summary(user_id: int):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM habits WHERE user_id = ? AND is_active = 1) AS total_active_habits,
                (SELECT COUNT(*) FROM habit_logs WHERE user_id = ? AND status = 'completed') AS total_completed_logs,
                (SELECT COUNT(*) FROM habit_logs WHERE user_id = ? AND status = 'missed') AS total_missed_logs,
                (SELECT COUNT(*) FROM habit_logs WHERE user_id = ? AND log_date = DATE('now')) AS today_logged_habits,
                (SELECT COUNT(*) FROM habit_logs WHERE user_id = ? AND log_date = DATE('now') AND status = 'completed') AS today_completed_habits
            """,
            (user_id, user_id, user_id, user_id, user_id),
        ).fetchone()
        return dict(row)


def get_habit_streaks(user_id: int):
    habits = get_active_habits(user_id)
    results = []
    with get_connection() as conn:
        for habit in habits:
            rows = conn.execute(
                """
                SELECT log_date, status
                FROM habit_logs
                WHERE user_id = ? AND habit_id = ?
                ORDER BY log_date DESC
                """,
                (user_id, habit['id']),
            ).fetchall()
            streak = 0
            for row in rows:
                if row['status'] == 'completed':
                    streak += 1
                else:
                    break
            results.append(
                {
                    'habit_id': habit['id'],
                    'habit_name': habit['habit_name'],
                    'category': habit.get('category'),
                    'streak': streak,
                }
            )
    return results
