import json
import os
import re
import time
from typing import List, Optional

from env_loader import load_local_env
from database import get_connection
from services.auth_service import get_profile_by_user_id
from services.habit_service import get_active_habits, get_habit_streaks
from services.ocr_service import get_latest_report
from services.recovery_service import get_latest_recovery_plan
from services.score_service import get_latest_score
from services.wellness_service import get_recent_daily_logs

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - dependency guard
    OpenAI = None


load_local_env()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "300"))
COACH_SYSTEM_PROMPT = (
    "You are a premium wellness coach inside a personal wellness app.\n"
    "Use the provided wellness snapshot and chat history as the source of truth.\n"
    "Be warm, precise, and concise. Do not diagnose medical conditions.\n"
    "If the user mentions serious symptoms, medical issues, or self-harm, advise a licensed professional or emergency services.\n"
    "Prefer practical next steps, short bullet points, and explicit references to the user's data when relevant.\n"
    "If the app data is missing or conflicting, say so briefly and fall back to the safest general guidance.\n"
)


def create_chat_session(user_id: int, session_title: str | None = None) -> int:
    title = (session_title or "").strip() or "Wellness Coach"
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_sessions (user_id, session_title)
            VALUES (?, ?)
            """,
            (user_id, title),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_chat_session_title(session_id: int, session_title: str) -> None:
    title = (session_title or "").strip() or "Wellness Coach"
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE chat_sessions
            SET session_title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, session_id),
        )
        conn.commit()


def get_chat_session_by_id(user_id: int, session_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM chat_sessions
            WHERE user_id = ? AND id = ?
            LIMIT 1
            """,
            (user_id, session_id),
        ).fetchone()
        return dict(row) if row else None


def get_latest_chat_session(user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM chat_sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def get_or_create_chat_session(user_id: int) -> dict:
    session = get_latest_chat_session(user_id)
    if session:
        return session

    session_id = create_chat_session(user_id, "Wellness Coach")
    created = get_chat_session_by_id(user_id, session_id)
    if not created:
        raise RuntimeError("Unable to create a chat session.")
    return created


def get_chat_sessions(user_id: int, limit: int = 10) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cs.*,
                   COUNT(cm.id) AS message_count,
                   MAX(cm.created_at) AS last_message_at
            FROM chat_sessions cs
            LEFT JOIN chat_messages cm ON cm.session_id = cs.id
            WHERE cs.user_id = ?
            GROUP BY cs.id
            ORDER BY cs.updated_at DESC, cs.id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def add_chat_message(
    session_id: int,
    user_id: int,
    sender_type: str,
    message_text: str,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_messages (session_id, user_id, sender_type, message_text)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user_id, sender_type, message_text),
        )
        conn.execute(
            """
            UPDATE chat_sessions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (session_id,),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_chat_messages(session_id: int, limit: int = 50) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        messages = [dict(row) for row in rows]
        messages.reverse()
        return messages


def _pick_focus_habit_name(user_id: int) -> str | None:
    streaks = get_habit_streaks(user_id)
    if streaks:
        return min(streaks, key=lambda item: item.get("streak", 9999)).get("habit_name")

    habits = get_active_habits(user_id)
    if habits:
        return habits[0].get("habit_name")
    return None


def _build_context_summary(user_id: int) -> dict:
    profile = get_profile_by_user_id(user_id)
    latest_score = get_latest_score(user_id)
    recent_logs = get_recent_daily_logs(user_id, limit=3)
    latest_plan = get_latest_recovery_plan(user_id)
    latest_report = get_latest_report(user_id)
    focus_habit = _pick_focus_habit_name(user_id)

    return {
        "profile": profile,
        "latest_score": latest_score,
        "recent_logs": recent_logs,
        "latest_plan": latest_plan,
        "latest_report": latest_report,
        "focus_habit": focus_habit,
    }


def _format_recent_logs(recent_logs: list[dict]) -> list[dict]:
    formatted = []
    for log in recent_logs[:5]:
        formatted.append(
            {
                "date": log.get("log_date"),
                "sleep_hours": log.get("sleep_hours"),
                "water_liters": log.get("water_intake_liters"),
                "steps": log.get("steps_count"),
                "exercise_minutes": log.get("exercise_minutes"),
                "mood": log.get("mood"),
                "stress_level": log.get("stress_level"),
            }
        )
    return formatted


def _build_chat_history(session_id: int, limit: int = 10) -> list[dict]:
    messages = get_chat_messages(session_id, limit=limit)
    history = []
    for msg in messages:
        role = "assistant" if msg["sender_type"] == "assistant" else "user"
        history.append(
            {
                "role": role,
                "content": msg["message_text"],
                "created_at": msg.get("created_at"),
            }
        )
    return history


def build_coach_snapshot(user_id: int) -> dict:
    context = _build_context_summary(user_id)
    latest_score = context["latest_score"] or {}
    latest_report = context["latest_report"] or {}
    latest_plan = context["latest_plan"] or {}

    return {
        "profile": context["profile"],
        "latest_score": {
            "total_score": latest_score.get("total_score"),
            "sleep_score": latest_score.get("sleep_score"),
            "hydration_score": latest_score.get("hydration_score"),
            "activity_score": latest_score.get("activity_score"),
            "habit_score": latest_score.get("habit_score"),
            "mood_score": latest_score.get("mood_score"),
            "explanation_summary": latest_score.get("explanation_summary"),
            "log_date": latest_score.get("log_date"),
        }
        if latest_score
        else None,
        "recent_logs": context["recent_logs"],
        "latest_plan": {
            "plan_date": latest_plan.get("plan_date"),
            "sleep_target_hours": latest_plan.get("sleep_target_hours"),
            "water_target_liters": latest_plan.get("water_target_liters"),
            "exercise_target_minutes": latest_plan.get("exercise_target_minutes"),
            "steps_target": latest_plan.get("steps_target"),
            "focus_habit": latest_plan.get("focus_habit"),
            "meal_guidance": latest_plan.get("meal_guidance"),
            "motivational_note": latest_plan.get("motivational_note"),
            "generated_reason": latest_plan.get("generated_reason"),
        }
        if latest_plan
        else None,
        "latest_report": {
            "file_name": latest_report.get("file_name"),
            "report_type": latest_report.get("report_type"),
            "processing_status": latest_report.get("processing_status"),
            "metric_count": len(latest_report.get("metrics", [])),
        }
        if latest_report
        else None,
        "focus_habit": context["focus_habit"],
    }


def build_coach_context(user_id: int, session_id: int, user_message: str) -> dict:
    context = _build_context_summary(user_id)
    history = _build_chat_history(session_id, limit=10)
    latest_score = context["latest_score"] or {}
    latest_plan = context["latest_plan"] or {}
    latest_report = context["latest_report"] or {}

    return {
        "user_profile": context["profile"],
        "latest_score": {
            "total_score": latest_score.get("total_score"),
            "sleep_score": latest_score.get("sleep_score"),
            "hydration_score": latest_score.get("hydration_score"),
            "activity_score": latest_score.get("activity_score"),
            "habit_score": latest_score.get("habit_score"),
            "mood_score": latest_score.get("mood_score"),
            "explanation_summary": latest_score.get("explanation_summary"),
            "log_date": latest_score.get("log_date"),
        }
        if latest_score
        else None,
        "recent_logs": _format_recent_logs(context["recent_logs"]),
        "latest_plan": {
            "plan_date": latest_plan.get("plan_date"),
            "sleep_target_hours": latest_plan.get("sleep_target_hours"),
            "water_target_liters": latest_plan.get("water_target_liters"),
            "exercise_target_minutes": latest_plan.get("exercise_target_minutes"),
            "steps_target": latest_plan.get("steps_target"),
            "focus_habit": latest_plan.get("focus_habit"),
            "meal_guidance": latest_plan.get("meal_guidance"),
            "motivational_note": latest_plan.get("motivational_note"),
            "generated_reason": latest_plan.get("generated_reason"),
        }
        if latest_plan
        else None,
        "latest_report": {
            "file_name": latest_report.get("file_name"),
            "report_type": latest_report.get("report_type"),
            "processing_status": latest_report.get("processing_status"),
            "metrics": latest_report.get("metrics", []),
        }
        if latest_report
        else None,
        "focus_habit": context["focus_habit"],
        "conversation_history": history,
        "user_message": (user_message or "").strip(),
    }


def _infer_topic(message: str, history: list[dict] | None = None) -> str:
    text = (message or "").strip().lower()
    history_text = " ".join(
        (item.get("content") or "") for item in (history or [])[-4:]
    ).lower()
    combined = f"{text} {history_text}"

    if any(word in combined for word in ("heart", "cardio", "cardiac", "bp", "blood pressure", "cholesterol")):
        return "heart"
    if "sleep" in combined or "rest" in combined:
        return "sleep"
    if "water" in combined or "hydration" in combined or "drink" in combined:
        return "hydration"
    if any(word in combined for word in ("exercise", "workout", "activity", "movement", "walk", "steps")):
        return "activity"
    if "habit" in combined or "streak" in combined or "routine" in combined:
        return "habit"
    if any(word in combined for word in ("report", "ocr", "metric", "body fat", "bmi", "scale")):
        return "report"
    if any(word in combined for word in ("plan", "recovery", "tomorrow", "today")):
        return "plan"
    if text in {"hi", "hello", "hey", "start", "help"} or any(word in combined for word in ("how are you", "what can you do")):
        return "greeting"
    return "general"


def _format_latest_log_summary(recent_logs: list[dict]) -> str | None:
    if not recent_logs:
        return None

    latest = recent_logs[0]
    parts = []
    if latest.get("sleep_hours") is not None:
        parts.append(f"sleep {latest['sleep_hours']}h")
    if latest.get("water_intake_liters") is not None:
        parts.append(f"water {latest['water_intake_liters']}L")
    if latest.get("steps_count") is not None:
        parts.append(f"steps {latest['steps_count']}")
    if latest.get("exercise_minutes") is not None:
        parts.append(f"exercise {latest['exercise_minutes']}m")
    if latest.get("mood"):
        parts.append(f"mood {latest['mood']}")
    if latest.get("stress_level") is not None:
        parts.append(f"stress {latest['stress_level']}/10")
    if not parts:
        return None
    return f"Latest log ({latest.get('date')}): " + ", ".join(parts) + "."


def _local_coach_reply(user_id: int, user_message: str, session_id: int | None = None) -> str:
    message = (user_message or "").strip().lower()
    context = _build_context_summary(user_id)
    history = _build_chat_history(session_id, limit=10) if session_id else []
    latest_score = context["latest_score"]
    latest_plan = context["latest_plan"]
    latest_report = context["latest_report"]
    recent_logs = context["recent_logs"]
    profile = context["profile"]
    focus_habit = context["focus_habit"]
    topic = _infer_topic(message, history)
    latest_log_summary = _format_latest_log_summary(recent_logs)

    if not message:
        return (
            "Tell me what you want help with today, and I'll turn it into a practical wellness plan. "
            "You can ask about sleep, hydration, workouts, habits, reports, or recovery."
        )

    parts: list[str] = []

    if latest_score:
        parts.append(
            f"Your latest wellness score is {int(round(latest_score['total_score']))}/100."
        )
        if latest_score.get("explanation_summary"):
            parts.append(latest_score["explanation_summary"])

    if latest_log_summary:
        parts.append(latest_log_summary)

    if topic == "greeting":
        if latest_score:
            parts.append(
                "If you want, I can look at your sleep, hydration, activity, habits, report metrics, or recovery plan next."
            )
        else:
            parts.append(
                "I can help you build a wellness baseline. Start with sleep, hydration, activity, habits, or a report upload."
            )

    if topic == "sleep":
        sleep_goal = profile.get("sleep_goal_hours") if profile else None
        if sleep_goal:
            parts.append(f"Your current sleep goal is {sleep_goal} hours.")
        if recent_logs and recent_logs[0].get("sleep_hours") is not None:
            sleep_value = recent_logs[0].get("sleep_hours")
            parts.append(f"Your most recent sleep log is {sleep_value} hours.")
            if sleep_goal:
                delta = round(float(sleep_goal) - float(sleep_value), 1)
                if delta > 0:
                    parts.append(f"That is {delta} hours below goal.")
                elif delta == 0:
                    parts.append("That matches your current sleep goal exactly.")
                else:
                    parts.append("That is above your target, which is a good sign if you feel rested.")
        else:
            parts.append("I do not see a sleep log yet for your account, so I cannot judge sleep quality from data.")
        parts.append(
            "For better sleep, keep bedtime consistent, reduce late caffeine, and protect the same wake-up time."
        )

    if topic == "hydration":
        water_goal = profile.get("water_goal_liters") if profile else None
        if water_goal:
            parts.append(f"Your water goal is {water_goal} liters.")
        if recent_logs and recent_logs[0].get("water_intake_liters") is not None:
            water_value = recent_logs[0].get("water_intake_liters")
            parts.append(f"Your most recent water log is {water_value} liters.")
        parts.append("Spread water across the day instead of trying to catch up all at once.")

    if topic == "activity":
        if profile and profile.get("steps_goal"):
            parts.append(f"Your step target is {profile['steps_goal']} steps.")
        if profile and profile.get("exercise_goal_minutes"):
            parts.append(f"Your exercise target is {profile['exercise_goal_minutes']} minutes.")
        if recent_logs and recent_logs[0].get("steps_count") is not None:
            parts.append(f"Your latest step count is {recent_logs[0]['steps_count']}.")
        parts.append("A short walk still counts. Consistency matters more than one hard workout.")

    if topic == "habit":
        if focus_habit:
            parts.append(f"Your current focus habit is {focus_habit}.")
        else:
            parts.append(
                "You do not have any active habits yet. Add a few simple daily habits to unlock streak tracking."
            )

    if topic == "report":
        if latest_report and latest_report.get("metrics"):
            metric_names = ", ".join(metric["metric_name"] for metric in latest_report["metrics"][:4])
            parts.append(f"Your latest uploaded report includes: {metric_names}.")
            parts.append("I can use those metrics to shape recovery and nutrition guidance.")
        else:
            parts.append("No report has been uploaded yet, so I'll fall back to your profile and daily logs.")

    if topic == "plan":
        if latest_plan:
            parts.append(
                "Your latest recovery plan already sets targets for sleep, water, exercise, and steps."
            )
            if latest_plan.get("focus_habit"):
                parts.append(f"It also prioritizes {latest_plan['focus_habit']} as today's focus habit.")
        else:
            parts.append("I do not see a saved recovery plan yet. Generate today's plan to get a daily target set.")

    if topic == "heart":
        parts.append(
            "I do not measure heart health directly from the current app data. I can infer general wellness signals such as sleep, activity, stress, and report metrics."
        )
        if latest_report and latest_report.get("metrics"):
            metric_names = ", ".join(metric["metric_name"] for metric in latest_report["metrics"][:4])
            parts.append(f"Your uploaded reports currently include: {metric_names}.")
        if latest_score:
            parts.append(
                "From the wellness data I do have, the safest interpretation is that your heart-health support depends mainly on improving sleep consistency, activity, hydration, and stress control."
            )
        parts.append(
            "If you have chest pain, shortness of breath, fainting, or other urgent symptoms, please seek medical care promptly."
        )

    if "stress" in message or "anxious" in message:
        parts.append(
            "For stress, keep the response simple: slow breathing for 5 minutes, a short walk, and one task at a time."
        )

    if topic == "general" and not parts:
        parts.append(
            "I can help you review your sleep, hydration, movement, habits, body report, or recovery plan."
        )
        parts.append(
            "If you ask one specific question, I can answer using your current data and chat history."
        )

    if "exercise" in message or "workout" in message or "activity" in message:
        if profile and profile.get("exercise_goal_minutes"):
            parts.append(f"Your exercise target is {profile['exercise_goal_minutes']} minutes.")
        parts.append("A short walk counts. Consistency beats one very hard session.")

    if latest_score and latest_score.get("total_score", 0) < 60:
        parts.append(
            "Because your score is still building, the best next move is to pick one small action and complete it today."
        )
    elif latest_score and latest_score.get("total_score", 0) >= 80:
        parts.append(
            "You are in a strong spot. Keep the routine stable and avoid changing too many things at once."
        )

    return " ".join(parts)


def _build_openai_prompt(
    user_id: int,
    session_id: int,
    user_message: str,
) -> str:
    context = build_coach_context(user_id, session_id, user_message)
    payload = dict(context)
    history = list(payload.get("conversation_history") or [])
    if history:
        payload["conversation_history"] = history[:-1]
    return json.dumps(payload, default=str, ensure_ascii=True, indent=2)


def _get_openai_client():
    if OpenAI is None:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    return OpenAI(api_key=api_key)


def _build_openai_input(user_id: int, session_id: int, user_message: str) -> str:
    context = build_coach_context(user_id, session_id, user_message)
    history_lines = []
    for message in context.get("conversation_history", [])[:-1]:
        speaker = "Assistant" if message.get("role") == "assistant" else "User"
        history_lines.append(f"{speaker}: {message.get('content', '')}")

    history_text = "\n".join(history_lines) if history_lines else "No prior chat messages."
    return (
        f"Wellness snapshot:\n{json.dumps(context, default=str, ensure_ascii=True, indent=2)}\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"Current user message:\n{user_message}\n"
    )


def _stream_text_chunks(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(\n+|(?<=[.!?])\s+)", text)
    chunks: list[str] = []
    buffer = ""
    for part in parts:
        if not part:
            continue
        buffer += part
        if part.isspace() or part.endswith(("\n", "!", "?", ".")) or len(buffer) > 120:
            chunks.append(buffer)
            buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks


def generate_coach_reply(user_id: int, session_id: int, user_message: str) -> str:
    clean_message = (user_message or "").strip()
    if not clean_message:
        return (
            "Tell me what you want help with today, and I'll turn it into a practical wellness plan. "
            "You can ask about sleep, hydration, workouts, habits, reports, or recovery."
        )

    client = _get_openai_client()
    if client:
        try:
            response = client.responses.create(
                model=DEFAULT_OPENAI_MODEL,
                instructions=COACH_SYSTEM_PROMPT,
                input=_build_openai_input(user_id, session_id, clean_message),
                reasoning={"effort": "low"},
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                text={"verbosity": "low"},
            )
            reply = (getattr(response, "output_text", "") or "").strip()
            if reply:
                return reply
        except Exception:
            pass

    return _local_coach_reply(user_id, clean_message, session_id)


def stream_coach_reply(user_id: int, session_id: int, user_message: str):
    clean_message = (user_message or "").strip()
    if not clean_message:
        yield (
            "Tell me what you want help with today, and I'll turn it into a practical wellness plan. "
            "You can ask about sleep, hydration, workouts, habits, reports, or recovery."
        )
        return

    client = _get_openai_client()
    if client:
        try:
            response = client.responses.create(
                model=DEFAULT_OPENAI_MODEL,
                instructions=COACH_SYSTEM_PROMPT,
                input=_build_openai_input(user_id, session_id, clean_message),
                reasoning={"effort": "low"},
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                stream=True,
                text={"verbosity": "low"},
            )
            streamed = ""
            for event in response:
                if event.type == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        streamed += delta
                        yield delta
                elif event.type == "response.completed":
                    break
            if streamed.strip():
                return
        except Exception:
            pass

    fallback = _local_coach_reply(user_id, clean_message, session_id)
    for chunk in _stream_text_chunks(fallback):
        yield chunk
        time.sleep(0.01)


def stream_and_store_coach_reply(user_id: int, session_id: int, user_message: str):
    buffer = []
    for chunk in stream_coach_reply(user_id, session_id, user_message):
        buffer.append(chunk)
        yield chunk

    reply = "".join(buffer).strip()
    if reply:
        add_chat_message(session_id, user_id, "assistant", reply)


def get_chat_overview(user_id: int) -> dict:
    sessions = get_chat_sessions(user_id, limit=8)
    active_session = get_or_create_chat_session(user_id)
    messages = get_chat_messages(active_session["id"])
    return {
        "sessions": sessions,
        "active_session": active_session,
        "messages": messages,
    }


def seed_welcome_message(user_id: int, session_id: int) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM chat_messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row and row["cnt"]:
            return

    latest_score = get_latest_score(user_id)
    if latest_score:
        message = (
            f"Welcome back. Your latest wellness score is {int(round(latest_score['total_score']))}/100. "
            "Ask me about any area you want to improve today."
        )
    else:
        message = (
            "Welcome to your wellness coach. Start by telling me how you're feeling or what you want to improve today."
        )
    add_chat_message(session_id, user_id, "assistant", message)


def get_or_create_thread_for_user(user_id: int) -> dict:
    session = get_or_create_chat_session(user_id)
    seed_welcome_message(user_id, session["id"])
    return session
