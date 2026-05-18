from typing import Optional
from passlib.context import CryptContext
from database import get_connection

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)

def create_user(full_name: str, email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    full_name = full_name.strip()

    if len(password) < 6:
        return False, "Password must be at least 6 characters long."

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            return False, "An account with this email already exists."

        conn.execute(
            """
            INSERT INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (full_name, email, hash_password(password))
        )
        conn.commit()

    return True, "Account created successfully."

def authenticate_user(email: str, password: str) -> Optional[dict]:
    email = email.strip().lower()
    with get_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if not user:
            return None

        if not verify_password(password, user["password_hash"]):
            return None

        return dict(user)

def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(user) if user else None

def get_profile_by_user_id(user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        profile = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return dict(profile) if profile else None

def upsert_profile(
    user_id: int,
    age: str,
    gender: str,
    height_cm: str,
    weight_kg: str,
    target_weight_kg: str,
    activity_level: str,
    wellness_goal: str,
    sleep_goal_hours: str,
    water_goal_liters: str,
    steps_goal: str,
    exercise_goal_minutes: str,
) -> None:
    def to_int(v):
        return int(v) if str(v).strip() else None

    def to_float(v):
        return float(v) if str(v).strip() else None

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM user_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        params = (
            user_id,
            to_int(age),
            gender.strip() or None,
            to_float(height_cm),
            to_float(weight_kg),
            to_float(target_weight_kg),
            activity_level.strip() or None,
            wellness_goal.strip() or None,
            to_float(sleep_goal_hours),
            to_float(water_goal_liters),
            to_int(steps_goal),
            to_int(exercise_goal_minutes),
        )

        if existing:
            conn.execute(
                """
                UPDATE user_profiles
                SET age = ?, gender = ?, height_cm = ?, weight_kg = ?, target_weight_kg = ?,
                    activity_level = ?, wellness_goal = ?, sleep_goal_hours = ?,
                    water_goal_liters = ?, steps_goal = ?, exercise_goal_minutes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    to_int(age),
                    gender.strip() or None,
                    to_float(height_cm),
                    to_float(weight_kg),
                    to_float(target_weight_kg),
                    activity_level.strip() or None,
                    wellness_goal.strip() or None,
                    to_float(sleep_goal_hours),
                    to_float(water_goal_liters),
                    to_int(steps_goal),
                    to_int(exercise_goal_minutes),
                    user_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO user_profiles (
                    user_id, age, gender, height_cm, weight_kg, target_weight_kg,
                    activity_level, wellness_goal, sleep_goal_hours, water_goal_liters,
                    steps_goal, exercise_goal_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        conn.commit()
