import json
import os
from typing import Any

from env_loader import load_local_env
from services.wellness_twin_service import build_wellness_twin_snapshot

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency guard
    OpenAI = None


load_local_env()

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "240"))
AUTOPILOT_SYSTEM_PROMPT = (
    "You are the Wellness Autopilot inside a premium personal wellness app.\n"
    "Your job is to produce the single best next action for the user given their actual data and time budget.\n"
    "Solve decision fatigue. Be practical, decisive, and specific.\n"
    "Do not diagnose medical conditions or claim certainty the data does not support.\n"
    "Explain what to do, when to do it, what not to do, and why this is the best move right now.\n"
    "If the user has limited time, choose the smallest action with the highest expected payoff.\n"
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


def _build_client():
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _priority_label(key: str) -> str:
    return {
        "sleep": "Sleep",
        "water": "Hydration",
        "activity": "Activity",
        "habit": "Habit consistency",
        "mood": "Recovery",
    }.get(key, "General wellbeing")


def _derive_priority(snapshot: dict) -> dict:
    scores = snapshot.get("latest_score") or {}
    recent = snapshot.get("recent_logs") or []
    latest_plan = snapshot.get("latest_plan") or {}
    report = snapshot.get("latest_report") or {}
    data_strength = snapshot.get("data_strength") or {}
    goals = snapshot.get("goals") or {}

    sleep_score = float(scores.get("sleep_score") or 0)
    hydration_score = float(scores.get("hydration_score") or 0)
    activity_score = float(scores.get("activity_score") or 0)
    habit_score = float(scores.get("habit_score") or 0)
    mood_score = float(scores.get("mood_score") or 0)

    priorities = [
        ("sleep", sleep_score, "sleep"),
        ("water", hydration_score, "water"),
        ("activity", activity_score, "movement"),
        ("habit", habit_score, "consistency"),
        ("mood", mood_score, "recovery"),
    ]
    priorities.sort(key=lambda item: item[1])
    key, score, label = priorities[0]

    time_budget = int(snapshot.get("controls", {}).get("time_budget_minutes") or 15)
    if time_budget <= 10 and key == "activity":
        key = "water" if hydration_score <= activity_score else "sleep"
        score = hydration_score if key == "water" else sleep_score
        label = "hydration" if key == "water" else "sleep"

    if report.get("metric_count", 0) and key in {"sleep", "water", "mood"} and float(data_strength.get("confidence") or 0) > 70:
        label = f"{label} with report context"

    if latest_plan and latest_plan.get("focus_habit") and key == "habit":
        label = f"focus on {latest_plan['focus_habit']}"

    return {
        "key": key,
        "label": _priority_label(key),
        "score": round(score, 1),
        "reason": label,
        "sleep_score": sleep_score,
        "hydration_score": hydration_score,
        "activity_score": activity_score,
        "habit_score": habit_score,
        "mood_score": mood_score,
        "time_budget_minutes": time_budget,
    }


def _choose_timebox_controls(priority: dict, snapshot: dict, controls: dict) -> dict:
    time_budget = int(controls.get("time_budget_minutes") or 15)
    mode = (controls.get("mode") or "optimize").strip().lower()
    energy = (controls.get("energy_level") or "medium").strip().lower()
    goals = snapshot.get("goals") or {}
    latest = snapshot.get("latest_score") or {}

    plan = {
        "mode": mode,
        "energy_level": energy,
        "time_budget_minutes": max(5, min(60, time_budget)),
        "priority": priority,
    }

    if priority["key"] == "sleep":
        if time_budget <= 10:
            action_title = "Lock the sleep window"
            action_steps = [
                "Set a hard cutoff for screens and caffeine.",
                "Prepare water and clothes for tomorrow.",
                "Keep lights low for the last 20 minutes before bed.",
            ]
            do_not = "Do not add a hard workout tonight; protect sleep first."
            payoff = "Small but immediate lift in sleep consistency and next-day recovery."
            minutes = 8
        elif time_budget <= 30:
            action_title = "Build a clean night routine"
            action_steps = [
                "Take a short walk or stretch to downshift.",
                "Prepare tomorrow's first task and remove friction.",
                "Go to bed at the same time as your target window.",
            ]
            do_not = "Do not chase a perfect routine; the goal is a repeatable one."
            payoff = "A noticeable shift in recovery quality across the next 2-3 days."
            minutes = 25
        else:
            action_title = "Reset your recovery rhythm"
            action_steps = [
                "Close the day early and avoid late stimulation.",
                "Anchor a fixed wake-up time.",
                "Reduce late-night eating and heavy training.",
            ]
            do_not = "Do not stack extra productivity tasks late at night."
            payoff = "The strongest long-term gain if sleep has been dragging your score down."
            minutes = 45
    elif priority["key"] == "water":
        if time_budget <= 10:
            action_title = "Front-load hydration"
            action_steps = [
                "Drink one glass immediately.",
                "Keep a bottle within arm's reach.",
                "Link water to the next two calendar events.",
            ]
            do_not = "Do not try to catch up with a huge amount at the end of the day."
            payoff = "Fastest low-effort way to stabilize energy and recovery."
            minutes = 6
        else:
            action_title = "Create hydration anchors"
            action_steps = [
                "Drink before coffee.",
                "Drink before lunch.",
                "Drink mid-afternoon and after movement.",
            ]
            do_not = "Do not wait until you feel behind."
            payoff = "Steadier hydration and fewer energy dips."
            minutes = 12
    elif priority["key"] == "activity":
        if time_budget <= 10:
            action_title = "Movement snack"
            action_steps = [
                "Walk briskly for 8-10 minutes.",
                "Take stairs once.",
                "Do not sit for the next hour without a 60-second reset.",
            ]
            do_not = "Do not use time pressure as a reason to skip movement entirely."
            payoff = "A surprisingly efficient boost to your daily activity curve."
            minutes = 10
        elif time_budget <= 30:
            action_title = "Score-boosting activity block"
            action_steps = [
                "Do a 20-minute walk or easy cycle.",
                "Break the session into two parts if needed.",
                "Finish with 2 minutes of breathing to lock in recovery.",
            ]
            do_not = "Do not turn this into an all-or-nothing workout."
            payoff = "The strongest lift for users with low activity scores."
            minutes = 22
        else:
            action_title = "Deep movement session"
            action_steps = [
                "Do a longer zone-2 session or a structured workout.",
                "Pair it with hydration and post-session recovery.",
                "Keep intensity moderate if sleep has been weak.",
            ]
            do_not = "Do not overload intensity if your sleep or mood is already under pressure."
            payoff = "Best when you have time and want a bigger score jump."
            minutes = 45
    elif priority["key"] == "habit":
        habit_name = snapshot.get("focus_habit") or "your focus habit"
        if time_budget <= 10:
            action_title = f"Win the {habit_name} streak"
            action_steps = [
                f"Complete {habit_name} before noon.",
                "Leave the rest of the day flexible.",
                "Mark it done immediately so the streak is visible.",
            ]
            do_not = "Do not start a new habit today; reinforce the one that already matters."
            payoff = "Habit momentum often beats trying to add another goal."
            minutes = 5
        else:
            action_title = f"Stabilize {habit_name}"
            action_steps = [
                f"Do {habit_name} at the same time as yesterday.",
                "Pair it with a pre-existing routine.",
                "Make the trigger obvious and easy to repeat tomorrow.",
            ]
            do_not = "Do not redesign your whole routine."
            payoff = "Consistency grows faster than novelty."
            minutes = 15
    else:
        if time_budget <= 10:
            action_title = "Recovery reset"
            action_steps = [
                "Breathe slowly for 2 minutes.",
                "Take a short walk outside if possible.",
                "Reduce one unnecessary decision today.",
            ]
            do_not = "Do not add a high-pressure task when the system needs recovery."
            payoff = "A simple nervous-system reset can improve the rest of the day."
            minutes = 8
        else:
            action_title = "Protect the system"
            action_steps = [
                "Preserve sleep and low stress windows.",
                "Keep meals simple and consistent.",
                "Use one 10-minute reset before the day gets noisy.",
            ]
            do_not = "Do not chase intensity while recovery is the bottleneck."
            payoff = "This is the fastest path to making the whole week feel easier."
            minutes = 20

    if mode == "protect":
        do_not = "Do not overcomplicate the day. Protect the single action and let the rest stay simple."
    elif mode == "push":
        payoff = f"{payoff} It is the strongest move if you want a visible change quickly."

    baseline = latest.get("total_score")
    baseline_score = float(baseline) if baseline is not None else 0.0
    if priority["key"] == "sleep":
        lift = min(18.0, max(4.0, (100 - priority["sleep_score"]) * 0.28))
    elif priority["key"] == "water":
        lift = min(10.0, max(3.0, (100 - priority["hydration_score"]) * 0.16))
    elif priority["key"] == "activity":
        lift = min(20.0, max(5.0, (100 - priority["activity_score"]) * 0.30))
    elif priority["key"] == "habit":
        lift = min(14.0, max(3.0, (100 - priority["habit_score"]) * 0.22))
    else:
        lift = min(12.0, max(3.0, (100 - priority["mood_score"]) * 0.18))

    if energy == "low":
        lift *= 0.92
    elif energy == "high":
        lift *= 1.08

    if time_budget <= 10:
        lift *= 0.7
    elif time_budget >= 45:
        lift *= 1.15

    projected_score = _clamp(baseline_score + lift)
    skip_score = _clamp(max(0.0, baseline_score - (3.0 if priority["key"] != "habit" else 1.5)))

    plan.update(
        {
            "action_title": action_title,
            "action_steps": action_steps,
            "do_not": do_not,
            "payoff": payoff,
            "expected_lift": round(lift, 1),
            "projected_score": projected_score,
            "skip_score": skip_score,
            "success_signals": [
                "You finished the action without negotiating with yourself.",
                "The action fit the time you actually had.",
                "You preserved tomorrow's energy instead of spending it all today.",
            ],
            "micro_contract": f"Commit to {minutes} minute(s) and complete the chosen action before the day gets noisy.",
        }
    )

    if goals.get("sleep_goal_hours") and priority["key"] == "sleep":
        plan["action_steps"].append(f"Protect your {goals['sleep_goal_hours']} hour sleep target tonight.")
    if goals.get("water_goal_liters") and priority["key"] == "water":
        plan["action_steps"].append(f"Work toward your {goals['water_goal_liters']} liter goal without backloading it.")

    return plan


def _openai_voice(snapshot: dict, plan: dict) -> str | None:
    client = _build_client()
    if not client:
        return None
    try:
        response = client.responses.create(
            model=DEFAULT_OPENAI_MODEL,
            instructions=AUTOPILOT_SYSTEM_PROMPT,
            input=json.dumps({"snapshot": snapshot, "plan": plan}, default=str, ensure_ascii=True, indent=2),
            reasoning={"effort": "low"},
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            text={"verbosity": "low"},
        )
        reply = (getattr(response, "output_text", "") or "").strip()
        return reply or None
    except Exception:
        return None


def _local_voice(snapshot: dict, plan: dict) -> str:
    priority = plan["priority"]
    baseline = snapshot["latest_score"]["total_score"]
    projected = plan["projected_score"]
    return (
        f"Your best move is {plan['action_title'].lower()} because {priority['label'].lower()} is the limiting factor right now. "
        f"If you complete the {plan['time_budget_minutes']}-minute version today, your score could move from {baseline} to about {projected}. "
        f"Do this before the day gets noisy: {plan['micro_contract']} "
        f"Do not {plan['do_not'].rstrip('.')}. "
        f"This is the highest-payoff use of your time based on the data the app has."
    )


def build_wellness_autopilot_payload(user_id: int, controls: dict | None = None) -> dict:
    snapshot = build_wellness_twin_snapshot(user_id)
    if not snapshot.get("is_ready"):
        return {
            "snapshot": snapshot,
            "controls": {
                "time_budget_minutes": int((controls or {}).get("time_budget_minutes") or 15),
                "energy_level": (controls or {}).get("energy_level") or "medium",
                "mode": (controls or {}).get("mode") or "optimize",
            },
            "is_ready": False,
            "confidence": snapshot.get("data_strength", {}).get("confidence", 0),
            "lock_message": (
                "Wellness Autopilot needs at least 7 days of tracking before it starts choosing actions. "
                "Track daily logs for one full week so the recommendation engine has enough evidence."
            ),
            "priority": {
                "key": None,
                "label": "Locked",
                "score": None,
                "reason": "Not enough tracking history yet",
            },
            "plan": None,
            "forecast": [],
            "narrative": "Keep tracking for one full week to unlock Autopilot.",
            "reasoning": {
                "why_now": "The app does not have enough tracking history yet.",
                "why_this": "The engine waits for a 7-day baseline before making decisions.",
                "why_not_other_things": "A recommendation would be too noisy before enough daily logs exist.",
            },
        }
    default_controls = {
        "time_budget_minutes": 15,
        "energy_level": "medium",
        "mode": "optimize",
    }
    if controls:
        merged = dict(default_controls)
        for key, value in controls.items():
            if value in (None, "", []):
                continue
            merged[key] = value
        controls = merged
    else:
        controls = default_controls

    snapshot["controls"] = controls
    priority = _derive_priority(snapshot)
    plan = _choose_timebox_controls(priority, snapshot, controls)
    narrative = _openai_voice(snapshot, plan) or _local_voice(snapshot, plan)

    forecast = [
        {
            "day": 1,
            "label": "Today",
            "baseline": _clamp(snapshot["latest_score"]["total_score"]),
            "after_action": _clamp(plan["projected_score"] * 0.84),
            "after_skip": _clamp(plan["skip_score"]),
        },
        {
            "day": 3,
            "label": "72h",
            "baseline": _clamp(snapshot["latest_score"]["total_score"]),
            "after_action": _clamp(plan["projected_score"] * 0.94),
            "after_skip": _clamp(plan["skip_score"] - 2),
        },
        {
            "day": 7,
            "label": "7d",
            "baseline": _clamp(snapshot["latest_score"]["total_score"]),
            "after_action": _clamp(plan["projected_score"]),
            "after_skip": _clamp(plan["skip_score"] - 4),
        },
    ]

    confidence = _clamp(
        30
        + snapshot["data_strength"]["confidence"] * 0.55
        + min(int(controls.get("time_budget_minutes") or 15), 60) * 0.35,
        25,
        95,
    )
    if priority["score"] >= 80:
        confidence -= 6

    return {
        "snapshot": snapshot,
        "controls": controls,
        "priority": priority,
        "plan": plan,
        "forecast": forecast,
        "confidence": confidence,
        "is_ready": True,
        "lock_message": None,
        "narrative": narrative,
        "reasoning": {
            "why_now": f"{priority['label']} is currently the clearest bottleneck.",
            "why_this": "It fits the time budget and gives the biggest score lift per minute.",
            "why_not_other_things": "The app avoids asking you to do everything at once.",
        },
    }


def refresh_wellness_autopilot(user_id: int, controls: dict | None = None) -> dict:
    return build_wellness_autopilot_payload(user_id, controls)
