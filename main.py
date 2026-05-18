import os
from datetime import date
from pathlib import Path
from fastapi import FastAPI, Form, Request, UploadFile, File, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from env_loader import load_local_env
from database import init_database
from services.auth_service import (
    create_user,
    authenticate_user,
    get_user_by_id,
    get_profile_by_user_id,
    upsert_profile,
)
from services.wellness_service import (
    upsert_daily_log,
    get_daily_log_by_date,
    get_recent_daily_logs,
    get_dashboard_summary,
)
from services.habit_service import (
    create_habit,
    get_active_habits,
    set_habit_status,
    get_habit_status_map,
    get_recent_habit_logs,
    get_habit_summary,
    get_habit_streaks,
)
from services.score_service import (
    calculate_score_for_date,
    get_score_by_date,
    get_latest_score,
    get_score_history,
    get_recommendations_for_date,
    get_latest_recommendations,
    get_score_overview,
)
from services.ocr_service import (
    save_uploaded_report,
    create_report_record,
    extract_text_from_image,
    parse_metrics,
    update_report_processing,
    replace_report_metrics,
    get_latest_report,
    get_recent_reports,
    save_report_insights,
)
from services.recovery_service import (
    generate_recovery_plan,
    save_recovery_plan,
    get_recovery_plan_by_date,
    get_latest_recovery_plan,
    get_recent_recovery_plans,
)
from services.wellness_twin_service import (
    build_wellness_twin_payload,
    simulate_wellness_twin,
)
from services.wellness_autopilot_service import (
    build_wellness_autopilot_payload,
    refresh_wellness_autopilot,
)
from services.chat_service import (
    add_chat_message,
    build_coach_snapshot,
    generate_coach_reply,
    get_chat_messages,
    get_chat_session_by_id,
    get_chat_sessions,
    get_or_create_chat_session,
    seed_welcome_message,
    create_chat_session,
    stream_and_store_coach_reply,
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("WELLNESS_UPLOAD_DIR", str(BASE_DIR / "uploads" / "reports")))

load_local_env()

app = FastAPI(title="AI Wellness Companion")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "change_this_secret_in_production"),
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

init_database()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(int(user_id))


@app.get("/health")
def health():
    return {"status": "ok", "app": "AI Wellness Companion"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if current_user(request):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "error": None, "success": None}
    )


@app.post("/register", response_class=HTMLResponse)
def register_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    if password != confirm_password:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match.", "success": None}
        )

    ok, message = create_user(full_name, email, password)
    if not ok:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": message, "success": None}
        )

    return templates.TemplateResponse(
        "register.html",
        {"request": request, "error": None, "success": "Account created successfully. Please login."}
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None}
    )


@app.post("/login", response_class=HTMLResponse)
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."}
        )

    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    profile = get_profile_by_user_id(user["id"])
    summary = get_dashboard_summary(user["id"])
    recent_logs = get_recent_daily_logs(user["id"], limit=7)
    latest_log = recent_logs[0] if recent_logs else None
    habit_summary = get_habit_summary(user["id"])
    habit_streaks = get_habit_streaks(user["id"])
    latest_score = get_latest_score(user["id"])
    score_history = get_score_history(user["id"], limit=7)
    score_overview = get_score_overview(user["id"])
    latest_recommendations = get_latest_recommendations(user["id"], limit=5)
    latest_report = get_latest_report(user["id"])
    latest_recovery_plan = get_latest_recovery_plan(user["id"])

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "summary": summary,
            "recent_logs": recent_logs,
            "latest_log": latest_log,
            "habit_summary": habit_summary,
            "habit_streaks": habit_streaks,
            "latest_score": latest_score,
            "score_history": score_history,
            "score_overview": score_overview,
            "latest_recommendations": latest_recommendations,
            "latest_report": latest_report,
            "latest_recovery_plan": latest_recovery_plan,
        }
    )


@app.get("/twin-lab", response_class=HTMLResponse)
def twin_lab_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    payload = build_wellness_twin_payload(user["id"])
    return templates.TemplateResponse(
        "wellness_twin.html",
        {
            "request": request,
            "user": user,
            "twin_payload": payload,
        },
    )


@app.get("/autopilot", response_class=HTMLResponse)
def autopilot_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    payload = build_wellness_autopilot_payload(user["id"])
    return templates.TemplateResponse(
        "wellness_autopilot.html",
        {
            "request": request,
            "user": user,
            "autopilot_payload": payload,
        },
    )


@app.post("/api/wellness-twin/simulate")
async def wellness_twin_simulate_api(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    data = await request.json()
    try:
        payload = simulate_wellness_twin(user["id"], data or {})
        return JSONResponse(payload)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.post("/api/wellness-autopilot/refresh")
async def wellness_autopilot_refresh_api(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    data = await request.json()
    try:
        payload = refresh_wellness_autopilot(user["id"], data or {})
        return JSONResponse(payload)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    profile = get_profile_by_user_id(user["id"])
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "success": None,
        }
    )


@app.post("/profile", response_class=HTMLResponse)
def save_profile(
    request: Request,
    age: str = Form(""),
    gender: str = Form(""),
    height_cm: str = Form(""),
    weight_kg: str = Form(""),
    target_weight_kg: str = Form(""),
    activity_level: str = Form(""),
    wellness_goal: str = Form(""),
    sleep_goal_hours: str = Form(""),
    water_goal_liters: str = Form(""),
    steps_goal: str = Form(""),
    exercise_goal_minutes: str = Form(""),
):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    upsert_profile(
        user["id"],
        age,
        gender,
        height_cm,
        weight_kg,
        target_weight_kg,
        activity_level,
        wellness_goal,
        sleep_goal_hours,
        water_goal_liters,
        steps_goal,
        exercise_goal_minutes,
    )

    profile = get_profile_by_user_id(user["id"])
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "success": "Profile saved successfully.",
        }
    )


@app.get("/daily-tracker", response_class=HTMLResponse)
def daily_tracker_page(request: Request, log_date: str | None = None):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    selected_date = log_date or str(date.today())
    daily_log = get_daily_log_by_date(user["id"], selected_date)
    recent_logs = get_recent_daily_logs(user["id"], limit=10)

    return templates.TemplateResponse(
        "daily_tracker.html",
        {
            "request": request,
            "user": user,
            "daily_log": daily_log,
            "selected_date": selected_date,
            "recent_logs": recent_logs,
            "success": None,
            "score_data": (calculate_score_for_date(user["id"], selected_date) or get_score_by_date(user["id"], selected_date)) if daily_log else None,
            "recommendations": get_recommendations_for_date(user["id"], selected_date),
        }
    )


@app.post("/daily-tracker", response_class=HTMLResponse)
def save_daily_tracker(
    request: Request,
    log_date: str = Form(...),
    sleep_hours: str = Form(""),
    water_intake_liters: str = Form(""),
    steps_count: str = Form(""),
    exercise_minutes: str = Form(""),
    calories_burned: str = Form(""),
    mood: str = Form(""),
    stress_level: str = Form(""),
    notes: str = Form(""),
):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    upsert_daily_log(
        user["id"],
        log_date,
        sleep_hours,
        water_intake_liters,
        steps_count,
        exercise_minutes,
        calories_burned,
        mood,
        stress_level,
        notes,
    )

    calculate_score_for_date(user["id"], log_date)
    daily_log = get_daily_log_by_date(user["id"], log_date)
    recent_logs = get_recent_daily_logs(user["id"], limit=10)
    score_data = get_latest_score(user["id"])
    recommendations = get_recommendations_for_date(user["id"], log_date)

    return templates.TemplateResponse(
        "daily_tracker.html",
        {
            "request": request,
            "user": user,
            "daily_log": daily_log,
            "selected_date": log_date,
            "recent_logs": recent_logs,
            "success": "Daily wellness log saved successfully.",
            "score_data": score_data,
            "recommendations": recommendations,
        }
    )


@app.get("/habits", response_class=HTMLResponse)
def habits_page(request: Request, log_date: str | None = None):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    selected_date = log_date or str(date.today())
    habits = get_active_habits(user["id"])
    status_map = get_habit_status_map(user["id"], selected_date)
    recent_habit_logs = get_recent_habit_logs(user["id"], limit=20)
    habit_summary = get_habit_summary(user["id"])
    habit_streaks = get_habit_streaks(user["id"])
    return templates.TemplateResponse(
        "habits.html",
        {
            "request": request,
            "user": user,
            "selected_date": selected_date,
            "habits": habits,
            "status_map": status_map,
            "recent_habit_logs": recent_habit_logs,
            "habit_summary": habit_summary,
            "habit_streaks": habit_streaks,
            "create_success": None,
            "track_success": None,
            "create_error": None,
        },
    )


@app.post("/habits/create", response_class=HTMLResponse)
def create_habit_route(
    request: Request,
    habit_name: str = Form(...),
    description: str = Form(""),
    category: str = Form(""),
    target_frequency: str = Form("Daily"),
):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    ok, message = create_habit(user["id"], habit_name, description, category, target_frequency)
    selected_date = str(date.today())
    habits = get_active_habits(user["id"])
    status_map = get_habit_status_map(user["id"], selected_date)
    recent_habit_logs = get_recent_habit_logs(user["id"], limit=20)
    habit_summary = get_habit_summary(user["id"])
    habit_streaks = get_habit_streaks(user["id"])
    return templates.TemplateResponse(
        "habits.html",
        {
            "request": request,
            "user": user,
            "selected_date": selected_date,
            "habits": habits,
            "status_map": status_map,
            "recent_habit_logs": recent_habit_logs,
            "habit_summary": habit_summary,
            "habit_streaks": habit_streaks,
            "create_success": message if ok else None,
            "track_success": None,
            "create_error": None if ok else message,
        },
    )


@app.post("/habits/track", response_class=HTMLResponse)
async def track_habits_route(
    request: Request,
    log_date: str = Form(...),
):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()
    for key, value in form.items():
        if key.startswith("status_"):
            habit_id = int(key.split("_")[1])
            notes_key = f"notes_{habit_id}"
            set_habit_status(user["id"], habit_id, log_date, value, form.get(notes_key, ""))

    recent_daily_log = get_daily_log_by_date(user["id"], log_date)
    if recent_daily_log:
        calculate_score_for_date(user["id"], log_date)

    habits = get_active_habits(user["id"])
    status_map = get_habit_status_map(user["id"], log_date)
    recent_habit_logs = get_recent_habit_logs(user["id"], limit=20)
    habit_summary = get_habit_summary(user["id"])
    habit_streaks = get_habit_streaks(user["id"])
    return templates.TemplateResponse(
        "habits.html",
        {
            "request": request,
            "user": user,
            "selected_date": log_date,
            "habits": habits,
            "status_map": status_map,
            "recent_habit_logs": recent_habit_logs,
            "habit_summary": habit_summary,
            "habit_streaks": habit_streaks,
            "create_success": None,
            "track_success": "Habit statuses saved successfully.",
            "create_error": None,
        },
    )


@app.get("/report-analyzer", response_class=HTMLResponse)
def report_analyzer_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "report_analyzer.html",
        {
            "request": request,
            "user": user,
            "success": None,
            "error": None,
            "latest_report": get_latest_report(user["id"]),
            "recent_reports": get_recent_reports(user["id"], limit=8),
        },
    )


@app.post("/report-analyzer", response_class=HTMLResponse)
async def upload_report_analyzer(
    request: Request,
    report_type: str = Form("body_composition"),
    report_file: UploadFile | None = File(None),
    report_text: str = Form(""),
):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    success = None
    error = None
    latest_report = None

    try:
        clean_text = (report_text or "").strip()
        if report_file and report_file.filename:
            file_bytes = await report_file.read()
            if not file_bytes:
                raise ValueError("Uploaded file is empty.")

            saved_name, saved_path = save_uploaded_report(UPLOAD_DIR, report_file.filename, file_bytes)
            report_id = create_report_record(user["id"], saved_name, saved_path, report_type)
            raw_text = extract_text_from_image(saved_path)
        elif clean_text:
            saved_name, saved_path = save_uploaded_report(
                UPLOAD_DIR,
                f"manual_report_{date.today().isoformat()}.txt",
                clean_text.encode("utf-8"),
            )
            report_id = create_report_record(user["id"], saved_name, saved_path, report_type)
            raw_text = clean_text
        else:
            raise ValueError("Please upload an image or paste report text before submitting.")

        metrics = parse_metrics(raw_text)
        status_label = "processed"
        update_report_processing(report_id, raw_text, status_label)
        replace_report_metrics(report_id, user["id"], metrics)
        save_report_insights(user["id"], report_id, str(date.today()), metrics)
        latest_report = get_latest_report(user["id"])
        metric_count = len(latest_report.get("metrics", [])) if latest_report else 0
        success = f"Report processed successfully. {metric_count} metric(s) extracted from the uploaded image."
    except Exception as exc:
        error = str(exc)
        latest_report = get_latest_report(user["id"])

    return templates.TemplateResponse(
        "report_analyzer.html",
        {
            "request": request,
            "user": user,
            "success": success,
            "error": error,
            "latest_report": latest_report,
            "recent_reports": get_recent_reports(user["id"], limit=8),
        },
    )


@app.get("/recovery-planner", response_class=HTMLResponse)
def recovery_planner_page(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    today = str(date.today())
    plan = get_recovery_plan_by_date(user["id"], today)
    recent_plans = get_recent_recovery_plans(user["id"], limit=7)

    return templates.TemplateResponse(
        "recovery_planner.html",
        {
            "request": request,
            "user": user,
            "today": today,
            "plan": plan,
            "recent_plans": recent_plans,
            "success": None,
            "error": None,
        },
    )


@app.get("/coach", response_class=HTMLResponse)
def coach_page(request: Request, session_id: int | None = None):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    active_session = None
    if session_id is not None:
        active_session = get_chat_session_by_id(user["id"], session_id)
    if active_session is None:
        active_session = get_or_create_chat_session(user["id"])

    sessions = get_chat_sessions(user["id"], limit=8)
    seed_welcome_message(user["id"], active_session["id"])
    messages = get_chat_messages(active_session["id"])

    return templates.TemplateResponse(
        "coach.html",
        {
            "request": request,
            "user": user,
            "sessions": sessions,
            "active_session": active_session,
            "messages": messages,
            "success": None,
            "error": None,
        },
    )


@app.get("/api/coach/bootstrap")
def coach_bootstrap(request: Request, session_id: int | None = None):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    active_session = None
    if session_id is not None:
        active_session = get_chat_session_by_id(user["id"], session_id)
    if active_session is None:
        active_session = get_or_create_chat_session(user["id"])
    seed_welcome_message(user["id"], active_session["id"])

    return JSONResponse(
        {
            "active_session": active_session,
            "sessions": get_chat_sessions(user["id"], limit=8),
            "messages": get_chat_messages(active_session["id"]),
            "snapshot": build_coach_snapshot(user["id"]),
        }
    )


@app.post("/api/coach/message")
async def coach_message_api(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    data = await request.json()
    session_id = int(data.get("session_id") or 0)
    message_text = (data.get("message_text") or "").strip()
    if not session_id:
        return JSONResponse({"error": "Missing session_id"}, status_code=400)
    if not message_text:
        return JSONResponse({"error": "Please type a message before sending."}, status_code=400)

    active_session = get_chat_session_by_id(user["id"], session_id)
    if not active_session:
        return JSONResponse({"error": "That chat session could not be found."}, status_code=404)

    add_chat_message(active_session["id"], user["id"], "user", message_text)
    reply = generate_coach_reply(user["id"], active_session["id"], message_text)
    add_chat_message(active_session["id"], user["id"], "assistant", reply)

    return JSONResponse(
        {
            "active_session": active_session,
            "message": {
                "role": "assistant",
                "text": reply,
            },
            "messages": get_chat_messages(active_session["id"]),
            "sessions": get_chat_sessions(user["id"], limit=8),
            "snapshot": build_coach_snapshot(user["id"]),
        }
    )


@app.post("/api/coach/message/stream")
async def coach_message_stream_api(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    data = await request.json()
    session_id = int(data.get("session_id") or 0)
    message_text = (data.get("message_text") or "").strip()
    if not session_id:
        return JSONResponse({"error": "Missing session_id"}, status_code=400)
    if not message_text:
        return JSONResponse({"error": "Please type a message before sending."}, status_code=400)

    active_session = get_chat_session_by_id(user["id"], session_id)
    if not active_session:
        return JSONResponse({"error": "That chat session could not be found."}, status_code=404)

    add_chat_message(active_session["id"], user["id"], "user", message_text)

    def event_stream():
        yield from stream_and_store_coach_reply(user["id"], active_session["id"], message_text)

    return StreamingResponse(
        event_stream(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/coach/new-session")
def coach_new_session_api(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    session_id = create_chat_session(user["id"], f"Wellness Coach {date.today().isoformat()}")
    active_session = get_chat_session_by_id(user["id"], session_id)
    seed_welcome_message(user["id"], session_id)

    return JSONResponse(
        {
            "active_session": active_session,
            "messages": get_chat_messages(session_id),
            "sessions": get_chat_sessions(user["id"], limit=8),
            "snapshot": build_coach_snapshot(user["id"]),
        }
    )


@app.post("/coach", response_class=HTMLResponse)
def send_coach_message(
    request: Request,
    session_id: int = Form(...),
    message_text: str = Form(...),
):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    success = None
    error = None

    try:
        active_session = get_chat_session_by_id(user["id"], session_id)
        if not active_session:
            raise ValueError("That chat session could not be found.")

        clean_message = (message_text or "").strip()
        if not clean_message:
            raise ValueError("Please type a message before sending.")

        add_chat_message(active_session["id"], user["id"], "user", clean_message)
        reply = generate_coach_reply(user["id"], active_session["id"], clean_message)
        add_chat_message(active_session["id"], user["id"], "assistant", reply)
        seed_welcome_message(user["id"], active_session["id"])
        success = "Message sent."
    except Exception as exc:
        error = str(exc)
        active_session = get_chat_session_by_id(user["id"], session_id) or get_or_create_chat_session(user["id"])

    sessions = get_chat_sessions(user["id"], limit=8)
    messages = get_chat_messages(active_session["id"])

    return templates.TemplateResponse(
        "coach.html",
        {
            "request": request,
            "user": user,
            "sessions": sessions,
            "active_session": active_session,
            "messages": messages,
            "success": success,
            "error": error,
        },
    )


@app.post("/coach/new", response_class=HTMLResponse)
def new_coach_session(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    session_id = create_chat_session(user["id"], f"Wellness Coach {date.today().isoformat()}")
    active_session = get_chat_session_by_id(user["id"], session_id)
    seed_welcome_message(user["id"], session_id)
    sessions = get_chat_sessions(user["id"], limit=8)
    messages = get_chat_messages(session_id)

    return templates.TemplateResponse(
        "coach.html",
        {
            "request": request,
            "user": user,
            "sessions": sessions,
            "active_session": active_session,
            "messages": messages,
            "success": "New chat session created.",
            "error": None,
        },
    )


@app.post("/recovery-planner", response_class=HTMLResponse)
def generate_recovery_planner(
    request: Request,
    plan_date: str = Form(...),
):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    success = None
    error = None
    plan = None

    try:
        plan = generate_recovery_plan(user["id"], plan_date)
        save_recovery_plan(plan)
        plan = get_recovery_plan_by_date(user["id"], plan_date)
        success = f"Recovery plan for {plan_date} has been generated and saved."
    except Exception as exc:
        error = str(exc)
        plan = get_recovery_plan_by_date(user["id"], plan_date)

    recent_plans = get_recent_recovery_plans(user["id"], limit=7)

    return templates.TemplateResponse(
        "recovery_planner.html",
        {
            "request": request,
            "user": user,
            "today": str(date.today()),
            "plan": plan,
            "recent_plans": recent_plans,
            "success": success,
            "error": error,
        },
    )
