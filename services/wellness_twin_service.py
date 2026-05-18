import json
import os
from statistics import mean
from typing import Any

from env_loader import load_local_env
from services.auth_service import get_profile_by_user_id
from services.habit_service import get_active_habits, get_habit_streaks, get_habit_summary
from services.ocr_service import get_latest_report
from services.recovery_service import get_latest_recovery_plan
from services.score_service import get_latest_score, get_score_history
from services.wellness_service import get_recent_daily_logs, get_tracking_days_count

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency guard
    OpenAI = None


load_local_env()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "220"))
WELLNESS_TWIN_SYSTEM_PROMPT = (
    "You are the Wellness Twin inside a premium personal wellness app.\n"
    "Your job is to explain a what-if simulation using the provided app data.\n"
    "Stay practical, vivid, and grounded in the user's actual data.\n"
    "Do not diagnose medical conditions or claim to know anything the data does not show.\n"
    "Use concise language, clear cause-and-effect, and a premium product tone.\n"
    "If the user asks for medical advice or urgent symptoms are implied, recommend medical care.\n"
)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, round(value, 1)))


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _mood_score(mood: str | None) -> float:
    mapping = {
        "happy": 100,
        "good": 90,
        "calm": 85,
        "neutral": 70,
        "tired": 55,
        "stressed": 45,
        "anxious": 35,
        "sad": 30,
    }
    if not mood:
        return 65.0
    return float(mapping.get(mood.strip().lower(), 65))


def _profile_completion(profile: dict | None) -> float:
    if not profile:
        return 0.0
    keys = (
        "age",
        "gender",
        "height_cm",
        "weight_kg",
        "target_weight_kg",
        "activity_level",
        "wellness_goal",
        "sleep_goal_hours",
        "water_goal_liters",
        "steps_goal",
        "exercise_goal_minutes",
    )
    filled = sum(1 for key in keys if profile.get(key) not in (None, "", 0))
    return _clamp((filled / len(keys)) * 100)


def _avg(values: list[float | int | None]) -> float | None:
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return round(mean(cleaned), 1)


def _recent_summary(recent_logs: list[dict]) -> dict:
    if not recent_logs:
        return {
            "sleep_hours": None,
            "water_intake_liters": None,
            "steps_count": None,
            "exercise_minutes": None,
            "stress_level": None,
            "mood": None,
        }
    return {
        "sleep_hours": _avg([log.get("sleep_hours") for log in recent_logs]),
        "water_intake_liters": _avg([log.get("water_intake_liters") for log in recent_logs]),
        "steps_count": _avg([log.get("steps_count") for log in recent_logs]),
        "exercise_minutes": _avg([log.get("exercise_minutes") for log in recent_logs]),
        "stress_level": _avg([log.get("stress_level") for log in recent_logs]),
        "mood": recent_logs[0].get("mood"),
    }


def _weighted_activity_score(steps_count: float | None, exercise_minutes: float | None, steps_goal: int, exercise_goal: int) -> float:
    steps_score = _clamp(((steps_count or 0) / max(steps_goal, 1)) * 100)
    exercise_score = _clamp(((exercise_minutes or 0) / max(exercise_goal, 1)) * 100)
    return _clamp((steps_score * 0.6) + (exercise_score * 0.4))


def _estimate_current_components(profile: dict | None, recent_logs: list[dict], latest_score: dict | None) -> dict:
    sleep_goal = _safe_float(profile.get("sleep_goal_hours"), 8.0) if profile else 8.0
    water_goal = _safe_float(profile.get("water_goal_liters"), 2.5) if profile else 2.5
    steps_goal = _safe_int(profile.get("steps_goal"), 8000) if profile else 8000
    exercise_goal = _safe_int(profile.get("exercise_goal_minutes"), 30) if profile else 30
    summary = _recent_summary(recent_logs)

    if latest_score:
        return {
            "sleep_score": float(latest_score.get("sleep_score") or 0),
            "hydration_score": float(latest_score.get("hydration_score") or 0),
            "activity_score": float(latest_score.get("activity_score") or 0),
            "habit_score": float(latest_score.get("habit_score") or 0),
            "mood_score": float(latest_score.get("mood_score") or 0),
            "total_score": float(latest_score.get("total_score") or 0),
        }

    sleep_score = _clamp(((summary["sleep_hours"] or 0) / max(sleep_goal, 1)) * 100) if summary["sleep_hours"] is not None else 70.0
    hydration_score = _clamp(((summary["water_intake_liters"] or 0) / max(water_goal, 1)) * 100) if summary["water_intake_liters"] is not None else 70.0
    activity_score = _weighted_activity_score(summary["steps_count"], summary["exercise_minutes"], steps_goal, exercise_goal)
    habit_score = 70.0
    mood_score = _mood_score(summary["mood"])
    total_score = _clamp((sleep_score * 0.25) + (hydration_score * 0.15) + (activity_score * 0.25) + (habit_score * 0.20) + (mood_score * 0.15))
    return {
        "sleep_score": sleep_score,
        "hydration_score": hydration_score,
        "activity_score": activity_score,
        "habit_score": habit_score,
        "mood_score": mood_score,
        "total_score": total_score,
    }


def _build_openai_client():
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _build_twin_prompt(snapshot: dict, controls: dict, simulation: dict) -> str:
    payload = {
        "snapshot": snapshot,
        "scenario": controls,
        "simulation": simulation,
    }
    return json.dumps(payload, default=str, ensure_ascii=True, indent=2)


def _build_local_narrative(snapshot: dict, controls: dict, simulation: dict) -> str:
    projected = simulation["projected"]
    baseline = simulation["baseline"]
    delta = simulation["delta"]
    best_lever = simulation["best_lever"]
    confidence = simulation["confidence"]
    horizon = simulation["days_horizon"]

    parts = [
        f"Your wellness twin projects a move from {baseline['total_score']} to {projected['total_score']} over {horizon} day(s).",
        f"The biggest lift comes from {best_lever['title'].lower()} ({best_lever['impact_label']}).",
        f"At this pace, your energy pattern should feel more stable and your recovery plan should become easier to maintain.",
    ]

    if delta["total_score"] >= 12:
        parts.append("That is a meaningful change. If you keep the same inputs for the full week, the twin expects a visible shift in consistency.")
    elif delta["total_score"] >= 5:
        parts.append("That is a solid gain. It is the kind of change that compounds quietly and shows up in your next score cycle.")
    elif delta["total_score"] <= -5:
        parts.append("The model is warning you that this pattern would gradually pull the score downward, mainly through recovery and habit drag.")

    if confidence < 60:
        parts.append("Confidence is moderate because the app has limited history for this account.")
    else:
        parts.append("Confidence is strong because the app has enough logs, habits, and report context to ground the estimate.")

    if snapshot.get("focus_habit"):
        parts.append(f"Your current focus habit, {snapshot['focus_habit']}, is also factored into the forecast.")

    return " ".join(parts)


def _generate_twin_voice(snapshot: dict, controls: dict, simulation: dict) -> str:
    client = _build_openai_client()
    if client:
        try:
            response = client.responses.create(
                model=DEFAULT_OPENAI_MODEL,
                instructions=WELLNESS_TWIN_SYSTEM_PROMPT,
                input=_build_twin_prompt(snapshot, controls, simulation),
                reasoning={"effort": "low"},
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                text={"verbosity": "low"},
            )
            reply = (getattr(response, "output_text", "") or "").strip()
            if reply:
                return reply
        except Exception:
            pass
    return _build_local_narrative(snapshot, controls, simulation)


def build_wellness_twin_snapshot(user_id: int) -> dict:
    profile = get_profile_by_user_id(user_id)
    latest_score = get_latest_score(user_id)
    score_history = get_score_history(user_id, limit=7)
    recent_logs = get_recent_daily_logs(user_id, limit=7)
    habits = get_active_habits(user_id)
    habit_summary = get_habit_summary(user_id)
    habit_streaks = get_habit_streaks(user_id)
    latest_report = get_latest_report(user_id)
    latest_plan = get_latest_recovery_plan(user_id)
    tracking_days = get_tracking_days_count(user_id)
    is_ready = tracking_days >= 7

    report_metrics = latest_report.get("metrics", []) if latest_report else []
    current_components = _estimate_current_components(profile, recent_logs, latest_score)
    if score_history and len(score_history) >= 2:
        trend_delta = float(score_history[0]["total_score"]) - float(score_history[-1]["total_score"])
    else:
        trend_delta = 0.0
    if trend_delta > 4:
        trend_label = "Improving"
    elif trend_delta < -4:
        trend_label = "Declining"
    else:
        trend_label = "Stable"

    profile_completion = _profile_completion(profile)
    confidence = _clamp(
        28
        + min(len(recent_logs), 7) * 8
        + min(len(habits), 8) * 4
        + min(len(report_metrics), 8) * 4
        + profile_completion * 0.18
        + min(len(score_history), 7) * 4,
        20,
        96,
    )

    return {
        "profile": profile,
        "latest_score": current_components,
        "recent_logs": recent_logs,
        "score_history": score_history,
        "habit_summary": habit_summary,
        "habit_streaks": habit_streaks,
        "latest_report": latest_report,
        "latest_plan": latest_plan,
        "tracking_days": tracking_days,
        "is_ready": is_ready,
        "days_required": 7,
        "tracking_progress_pct": _clamp((tracking_days / 7) * 100, 0, 100),
        "focus_habit": habit_streaks and min(habit_streaks, key=lambda item: item.get("streak", 9999)).get("habit_name")
        or (habits[0]["habit_name"] if habits else None),
        "goals": {
            "sleep_goal_hours": _safe_float(profile.get("sleep_goal_hours"), 8.0) if profile else 8.0,
            "water_goal_liters": _safe_float(profile.get("water_goal_liters"), 2.5) if profile else 2.5,
            "steps_goal": _safe_int(profile.get("steps_goal"), 8000) if profile else 8000,
            "exercise_goal_minutes": _safe_int(profile.get("exercise_goal_minutes"), 30) if profile else 30,
        },
        "data_strength": {
            "profile_completion": profile_completion,
            "logs_count": len(recent_logs),
            "habits_count": len(habits),
            "report_metric_count": len(report_metrics),
            "confidence": confidence,
            "trend_label": trend_label,
        },
    }


def _default_controls(snapshot: dict) -> dict:
    recent = snapshot.get("recent_logs") or []
    summary = _recent_summary(recent)
    goals = snapshot.get("goals") or {}
    latest = snapshot.get("latest_score") or {}

    sleep_goal = float(goals.get("sleep_goal_hours") or 8.0)
    water_goal = float(goals.get("water_goal_liters") or 2.5)
    steps_goal = int(goals.get("steps_goal") or 8000)
    exercise_goal = int(goals.get("exercise_goal_minutes") or 30)

    return {
        "mode": "stability",
        "days_horizon": 7,
        "sleep_hours": round(max(sleep_goal, summary.get("sleep_hours") or sleep_goal), 1),
        "water_liters": round(max(water_goal, summary.get("water_intake_liters") or water_goal), 1),
        "steps_count": int(max(steps_goal, summary.get("steps_count") or steps_goal)),
        "exercise_minutes": int(max(exercise_goal, summary.get("exercise_minutes") or exercise_goal)),
        "stress_minutes": int(max(10, min(30, (summary.get("stress_level") or 10) * 2))),
        "habit_completion_pct": int(
            max(
                55,
                min(
                    100,
                    (latest.get("habit_score") or 70) if latest else 70,
                ),
            )
        ),
        "recovery_minutes": 10,
    }


def _adjust_weights(mode: str, current_components: dict, controls: dict) -> dict:
    weights = {
        "sleep": 1.0,
        "water": 1.0,
        "activity": 1.0,
        "habit": 1.0,
        "mood": 1.0,
    }

    if mode == "recovery":
        weights["sleep"] = 1.25
        weights["mood"] = 1.25
        weights["habit"] = 1.12
        weights["activity"] = 0.85
    elif mode == "performance":
        weights["activity"] = 1.25
        weights["sleep"] = 1.08
        weights["habit"] = 1.05
    elif mode == "momentum":
        weights["habit"] = 1.20
        weights["activity"] = 1.12
    elif mode == "reset":
        weights["sleep"] = 1.30
        weights["water"] = 1.12
        weights["mood"] = 1.18
        weights["activity"] = 0.82

    if current_components.get("sleep_score", 100) < 70:
        weights["sleep"] *= 1.18
    if current_components.get("hydration_score", 100) < 70:
        weights["water"] *= 1.10
    if current_components.get("activity_score", 100) < 70:
        weights["activity"] *= 1.15
    if current_components.get("habit_score", 100) < 70:
        weights["habit"] *= 1.14
    if current_components.get("mood_score", 100) < 60:
        weights["mood"] *= 1.16

    if (controls.get("stress_minutes") or 0) >= 20:
        weights["mood"] *= 1.08
    return weights


def _compute_simulation(snapshot: dict, controls: dict) -> dict:
    goals = snapshot.get("goals") or {}
    current = snapshot.get("latest_score") or {}
    current_components = _estimate_current_components(snapshot.get("profile"), snapshot.get("recent_logs") or [], current if current and current.get("total_score") is not None else None)

    sleep_goal = float(goals.get("sleep_goal_hours") or 8.0)
    water_goal = float(goals.get("water_goal_liters") or 2.5)
    steps_goal = int(goals.get("steps_goal") or 8000)
    exercise_goal = int(goals.get("exercise_goal_minutes") or 30)
    days_horizon = int(controls.get("days_horizon") or 7)
    days_horizon = max(3, min(14, days_horizon))

    sleep_hours = _safe_float(controls.get("sleep_hours"), sleep_goal) or sleep_goal
    water_liters = _safe_float(controls.get("water_liters"), water_goal) or water_goal
    steps_count = _safe_int(controls.get("steps_count"), steps_goal) or steps_goal
    exercise_minutes = _safe_int(controls.get("exercise_minutes"), exercise_goal) or exercise_goal
    stress_minutes = _safe_int(controls.get("stress_minutes"), 10) or 10
    habit_completion_pct = _safe_int(controls.get("habit_completion_pct"), 70) or 70
    mode = (controls.get("mode") or "stability").strip().lower()

    weights = _adjust_weights(mode, current_components, controls)

    projected_sleep = _clamp((sleep_hours / max(sleep_goal, 1)) * 100)
    projected_water = _clamp((water_liters / max(water_goal, 1)) * 100)
    projected_activity = _weighted_activity_score(steps_count, exercise_minutes, steps_goal, exercise_goal)
    projected_habit = _clamp(habit_completion_pct)

    base_mood = current_components.get("mood_score", 65.0)
    recovery_gain = max(0, min(18, stress_minutes * 0.9 + controls.get("recovery_minutes", 10) * 0.35))
    sleep_bonus = (sleep_hours - sleep_goal) * 4.0
    movement_bonus = max(-6.0, min(8.0, ((exercise_minutes - exercise_goal) / max(exercise_goal, 1)) * 12.0))
    projected_mood = _clamp(base_mood + recovery_gain + sleep_bonus + movement_bonus)

    weighted_total = (
        (projected_sleep * 0.25 * weights["sleep"])
        + (projected_water * 0.15 * weights["water"])
        + (projected_activity * 0.25 * weights["activity"])
        + (projected_habit * 0.20 * weights["habit"])
        + (projected_mood * 0.15 * weights["mood"])
    )
    weight_divisor = (
        (0.25 * weights["sleep"])
        + (0.15 * weights["water"])
        + (0.25 * weights["activity"])
        + (0.20 * weights["habit"])
        + (0.15 * weights["mood"])
    )
    projected_total = _clamp(weighted_total / max(weight_divisor, 0.01))

    baseline_total = float(current_components.get("total_score") or 0)
    delta_total = round(projected_total - baseline_total, 1)

    component_deltas = {
        "sleep_score": round(projected_sleep - float(current_components.get("sleep_score") or 0), 1),
        "hydration_score": round(projected_water - float(current_components.get("hydration_score") or 0), 1),
        "activity_score": round(projected_activity - float(current_components.get("activity_score") or 0), 1),
        "habit_score": round(projected_habit - float(current_components.get("habit_score") or 0), 1),
        "mood_score": round(projected_mood - float(current_components.get("mood_score") or 0), 1),
    }

    contribution_map = {
        "sleep": component_deltas["sleep_score"] * 0.25,
        "water": component_deltas["hydration_score"] * 0.15,
        "activity": component_deltas["activity_score"] * 0.25,
        "habit": component_deltas["habit_score"] * 0.20,
        "mood": component_deltas["mood_score"] * 0.15,
    }
    best_key = max(contribution_map, key=lambda key: contribution_map[key])
    best_lever_titles = {
        "sleep": "Sleep",
        "water": "Hydration",
        "activity": "Activity",
        "habit": "Habit consistency",
        "mood": "Recovery",
    }
    best_lever = {
        "key": best_key,
        "title": best_lever_titles[best_key],
        "impact": round(contribution_map[best_key], 1),
        "impact_label": f"{'+' if contribution_map[best_key] >= 0 else ''}{round(contribution_map[best_key], 1)} score points",
    }

    forecast = []
    for day in range(1, days_horizon + 1):
        progress = day / days_horizon
        day_score = _clamp(baseline_total + (delta_total * progress))
        forecast.append(
            {
                "day": day,
                "label": f"Day {day}",
                "projected_score": day_score,
                "delta_from_baseline": round(day_score - baseline_total, 1),
            }
        )

    risk_notes = []
    if projected_sleep < current_components.get("sleep_score", 0):
        risk_notes.append("Sleep is not improving enough to pull the twin upward.")
    if projected_activity < current_components.get("activity_score", 0):
        risk_notes.append("Activity is slipping, which will slow your momentum quickly.")
    if projected_habit < current_components.get("habit_score", 0):
        risk_notes.append("Habit consistency is the first place the plan can leak.")
    if projected_mood < current_components.get("mood_score", 0):
        risk_notes.append("Stress recovery is too weak to stabilize the week.")
    if not risk_notes:
        risk_notes.append("The scenario looks sustainable if you keep the inputs consistent.")

    opportunities = []
    if projected_sleep >= current_components.get("sleep_score", 0):
        opportunities.append("Your sleep lever is doing useful work.")
    if projected_water >= current_components.get("hydration_score", 0):
        opportunities.append("Hydration is supporting the rest of the plan.")
    if projected_activity >= current_components.get("activity_score", 0):
        opportunities.append("Movement is strong enough to lift the weekly curve.")
    if projected_habit >= current_components.get("habit_score", 0):
        opportunities.append("Habit follow-through is reinforcing the score gain.")
    if projected_mood >= current_components.get("mood_score", 0):
        opportunities.append("Recovery minutes are paying off in the mood forecast.")

    data_strength = snapshot.get("data_strength") or {}
    confidence = float(data_strength.get("confidence") or 50)

    simulation = {
        "days_horizon": days_horizon,
        "mode": mode,
        "confidence": confidence,
        "baseline": {
            "total_score": _clamp(baseline_total),
            "sleep_score": _clamp(float(current_components.get("sleep_score") or 0)),
            "hydration_score": _clamp(float(current_components.get("hydration_score") or 0)),
            "activity_score": _clamp(float(current_components.get("activity_score") or 0)),
            "habit_score": _clamp(float(current_components.get("habit_score") or 0)),
            "mood_score": _clamp(float(current_components.get("mood_score") or 0)),
        },
        "projected": {
            "total_score": projected_total,
            "sleep_score": projected_sleep,
            "hydration_score": projected_water,
            "activity_score": projected_activity,
            "habit_score": projected_habit,
            "mood_score": projected_mood,
        },
        "delta": {
            "total_score": delta_total,
            **component_deltas,
        },
        "best_lever": best_lever,
        "forecast": forecast,
        "risk_notes": risk_notes,
        "opportunities": opportunities,
    }
    simulation["narrative"] = _generate_twin_voice(snapshot, controls, simulation)
    return simulation


def build_wellness_twin_payload(user_id: int, controls: dict | None = None) -> dict:
    snapshot = build_wellness_twin_snapshot(user_id)
    default_controls = _default_controls(snapshot)
    if controls:
        merged = dict(default_controls)
        for key, value in controls.items():
            if value in (None, "", []):
                continue
            merged[key] = value
        controls = merged
    else:
        controls = default_controls

    if not snapshot.get("is_ready"):
        return {
            "snapshot": snapshot,
            "controls": controls,
            "simulation": None,
            "is_ready": False,
            "lock_message": (
                "The Wellness Twin needs at least 7 days of tracking before it starts simulating future outcomes. "
                "Keep logging daily data so the forecast becomes reliable."
            ),
        }

    simulation = _compute_simulation(snapshot, controls)
    return {
        "snapshot": snapshot,
        "controls": controls,
        "simulation": simulation,
        "is_ready": True,
        "lock_message": None,
    }


def simulate_wellness_twin(user_id: int, controls: dict | None = None) -> dict:
    return build_wellness_twin_payload(user_id, controls)
