from datetime import date
from database import get_connection
from services.auth_service import get_profile_by_user_id
from services.wellness_service import get_daily_log_by_date, get_recent_daily_logs
from services.habit_service import get_habit_summary, get_active_habits, get_habit_status_map


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, round(value, 1)))


def _mood_score(mood: str | None) -> float:
    mapping = {
        'happy': 100,
        'good': 90,
        'calm': 85,
        'neutral': 70,
        'tired': 55,
        'stressed': 45,
        'anxious': 35,
        'sad': 30,
    }
    if not mood:
        return 65.0
    return float(mapping.get(mood.strip().lower(), 65))


def _score_ratio(actual: float | None, goal: float | None) -> float:
    if actual is None:
        return 0.0
    if goal is None or goal <= 0:
        return 70.0
    return _clamp((actual / goal) * 100)


def calculate_score_for_date(user_id: int, log_date: str):
    profile = get_profile_by_user_id(user_id)
    daily_log = get_daily_log_by_date(user_id, log_date)
    if not daily_log:
        return None

    sleep_goal = float(profile.get('sleep_goal_hours') or 8) if profile else 8
    water_goal = float(profile.get('water_goal_liters') or 2.5) if profile else 2.5
    steps_goal = int(profile.get('steps_goal') or 8000) if profile else 8000
    exercise_goal = int(profile.get('exercise_goal_minutes') or 30) if profile else 30

    sleep_score = _score_ratio(daily_log.get('sleep_hours'), sleep_goal)
    hydration_score = _score_ratio(daily_log.get('water_intake_liters'), water_goal)

    steps_score = _score_ratio(daily_log.get('steps_count'), steps_goal)
    exercise_score = _score_ratio(daily_log.get('exercise_minutes'), exercise_goal)
    activity_score = _clamp((steps_score * 0.6) + (exercise_score * 0.4))

    habits = get_active_habits(user_id)
    status_map = get_habit_status_map(user_id, log_date)
    if habits:
        completed = 0
        partial = 0
        for habit in habits:
            status = (status_map.get(habit['id'], {}) or {}).get('status')
            if status == 'completed':
                completed += 1
            elif status == 'partial':
                partial += 1
        habit_score = _clamp(((completed + (partial * 0.5)) / len(habits)) * 100)
    else:
        habit_score = 70.0

    mood_score = _mood_score(daily_log.get('mood'))

    total_score = _clamp(
        (sleep_score * 0.25)
        + (hydration_score * 0.15)
        + (activity_score * 0.25)
        + (habit_score * 0.20)
        + (mood_score * 0.15)
    )

    weak_areas = []
    if sleep_score < 70:
        weak_areas.append('sleep')
    if hydration_score < 70:
        weak_areas.append('hydration')
    if activity_score < 70:
        weak_areas.append('activity')
    if habit_score < 70:
        weak_areas.append('habit consistency')
    if mood_score < 60:
        weak_areas.append('mood balance')

    if weak_areas:
        explanation_summary = (
            f"Your wellness score for {log_date} is {total_score}/100. "
            f"The biggest areas affecting your score are {', '.join(weak_areas)}."
        )
    else:
        explanation_summary = (
            f"Your wellness score for {log_date} is {total_score}/100. "
            "Your main wellness indicators are balanced today."
        )

    result = {
        'log_date': log_date,
        'total_score': total_score,
        'sleep_score': sleep_score,
        'hydration_score': hydration_score,
        'activity_score': activity_score,
        'habit_score': habit_score,
        'mood_score': mood_score,
        'explanation_summary': explanation_summary,
    }
    save_score(user_id, result)
    save_recommendations(user_id, log_date, daily_log, profile, result)
    return result


def save_score(user_id: int, score_data: dict):
    with get_connection() as conn:
        existing = conn.execute(
            'SELECT id FROM wellness_scores WHERE user_id = ? AND log_date = ?',
            (user_id, score_data['log_date']),
        ).fetchone()

        values = (
            score_data['total_score'],
            score_data['sleep_score'],
            score_data['hydration_score'],
            score_data['activity_score'],
            score_data['habit_score'],
            score_data['mood_score'],
            score_data['explanation_summary'],
        )
        if existing:
            conn.execute(
                '''
                UPDATE wellness_scores
                SET total_score = ?, sleep_score = ?, hydration_score = ?, activity_score = ?,
                    habit_score = ?, mood_score = ?, explanation_summary = ?
                WHERE user_id = ? AND log_date = ?
                ''',
                values + (user_id, score_data['log_date']),
            )
        else:
            conn.execute(
                '''
                INSERT INTO wellness_scores (
                    user_id, log_date, total_score, sleep_score, hydration_score,
                    activity_score, habit_score, mood_score, explanation_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (user_id, score_data['log_date']) + values,
            )
        conn.commit()


def _build_recommendations(daily_log: dict, profile: dict | None, score_data: dict):
    recommendations = []
    sleep_goal = float(profile.get('sleep_goal_hours') or 8) if profile else 8
    water_goal = float(profile.get('water_goal_liters') or 2.5) if profile else 2.5
    steps_goal = int(profile.get('steps_goal') or 8000) if profile else 8000
    exercise_goal = int(profile.get('exercise_goal_minutes') or 30) if profile else 30

    if (daily_log.get('sleep_hours') or 0) < sleep_goal:
        deficit = round(sleep_goal - float(daily_log.get('sleep_hours') or 0), 1)
        recommendations.append(('daily_tip', 'daily_log', f'Try to add about {deficit} more hour(s) of sleep to reach your target of {sleep_goal} hours.', 'high'))
    if (daily_log.get('water_intake_liters') or 0) < water_goal:
        gap = round(water_goal - float(daily_log.get('water_intake_liters') or 0), 1)
        recommendations.append(('daily_tip', 'daily_log', f'Increase hydration by about {gap} liters to reach your water goal of {water_goal} L.', 'medium'))
    if (daily_log.get('steps_count') or 0) < steps_goal:
        gap = int(steps_goal - int(daily_log.get('steps_count') or 0))
        recommendations.append(('daily_tip', 'daily_log', f'You are {gap} steps below your daily goal. A short evening walk can help close the gap.', 'medium'))
    if (daily_log.get('exercise_minutes') or 0) < exercise_goal:
        gap = int(exercise_goal - int(daily_log.get('exercise_minutes') or 0))
        recommendations.append(('daily_tip', 'daily_log', f'Aim for at least {gap} more minute(s) of movement to strengthen your activity score.', 'medium'))

    mood = (daily_log.get('mood') or '').lower()
    if mood in {'stressed', 'anxious', 'tired', 'sad'}:
        recommendations.append(('wellness_guidance', 'daily_log', 'Your mood suggests recovery is important today. Consider 10 minutes of breathing, stretching, or a low-stress walk.', 'high'))

    if score_data['total_score'] >= 80:
        recommendations.append(('daily_tip', 'score_engine', 'Your score is strong today. Focus on consistency and keep your current routine stable.', 'low'))

    if not recommendations:
        recommendations.append(('daily_tip', 'score_engine', 'Your metrics look balanced. Maintain your routine and log again tomorrow for a stronger trend analysis.', 'low'))

    return recommendations[:4]


def save_recommendations(user_id: int, log_date: str, daily_log: dict, profile: dict | None, score_data: dict):
    recs = _build_recommendations(daily_log, profile, score_data)
    with get_connection() as conn:
        conn.execute(
            'DELETE FROM ai_recommendations WHERE user_id = ? AND related_date = ? AND recommendation_type IN ("daily_tip", "wellness_guidance")',
            (user_id, log_date),
        )
        for recommendation_type, source_reference, content, priority_level in recs:
            conn.execute(
                '''
                INSERT INTO ai_recommendations (user_id, recommendation_type, source_reference, content, priority_level, related_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (user_id, recommendation_type, source_reference, content, priority_level, log_date),
            )
        conn.commit()



def get_score_by_date(user_id: int, log_date: str):
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM wellness_scores WHERE user_id = ? AND log_date = ? LIMIT 1',
            (user_id, log_date),
        ).fetchone()
        return dict(row) if row else None

def get_latest_score(user_id: int):
    with get_connection() as conn:
        row = conn.execute(
            '''
            SELECT *
            FROM wellness_scores
            WHERE user_id = ?
            ORDER BY log_date DESC, id DESC
            LIMIT 1
            ''',
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def get_score_history(user_id: int, limit: int = 7):
    with get_connection() as conn:
        rows = conn.execute(
            '''
            SELECT log_date, total_score, sleep_score, hydration_score, activity_score, habit_score, mood_score
            FROM wellness_scores
            WHERE user_id = ?
            ORDER BY log_date DESC, id DESC
            LIMIT ?
            ''',
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recommendations_for_date(user_id: int, related_date: str):
    with get_connection() as conn:
        rows = conn.execute(
            '''
            SELECT * FROM ai_recommendations
            WHERE user_id = ? AND related_date = ?
            ORDER BY CASE priority_level WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id DESC
            ''',
            (user_id, related_date),
        ).fetchall()
        return [dict(r) for r in rows]


def get_latest_recommendations(user_id: int, limit: int = 5):
    with get_connection() as conn:
        rows = conn.execute(
            '''
            SELECT * FROM ai_recommendations
            WHERE user_id = ?
            ORDER BY related_date DESC, id DESC
            LIMIT ?
            ''',
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_score_overview(user_id: int):
    recent_logs = get_recent_daily_logs(user_id, limit=7)
    if not recent_logs:
        return {
            'avg_total_score': None,
            'best_score': None,
            'score_trend_label': 'No data yet',
        }

    for log in recent_logs:
        calculate_score_for_date(user_id, log['log_date'])

    history = get_score_history(user_id, limit=7)
    if not history:
        return {
            'avg_total_score': None,
            'best_score': None,
            'score_trend_label': 'No data yet',
        }

    scores = [item['total_score'] for item in history if item.get('total_score') is not None]
    avg_total_score = round(sum(scores) / len(scores), 1) if scores else None
    best_score = max(scores) if scores else None

    trend_label = 'Stable'
    if len(scores) >= 2:
        if scores[0] > scores[-1]:
            trend_label = 'Improving'
        elif scores[0] < scores[-1]:
            trend_label = 'Needs attention'

    return {
        'avg_total_score': avg_total_score,
        'best_score': best_score,
        'score_trend_label': trend_label,
    }
