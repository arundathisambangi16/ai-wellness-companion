import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Tuple

import pytesseract
from PIL import Image, ImageOps, ImageFilter

from database import get_connection

COMMON_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

METRIC_PATTERNS = [
    # ── Body Composition ─────────────────────────────────────────────────────
    ("weight_kg",        "Weight",        "kg",    [r"weight[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"wt[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("bmi",              "BMI",           "score", [r"\bbmi\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("body_fat_percent", "Body Fat",      "%",     [r"body\s*fat[^\r\n%:]*[:\s]+(\d+(?:\.\d+)?)\s*%", r"fat\s*%[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("muscle_mass_kg",   "Muscle Mass",   "kg",    [r"muscle\s*mass[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"skeletal\s*muscle[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("water_percent",    "Body Water",    "%",     [r"body\s*water[^\r\n%:]*[:\s]+(\d+(?:\.\d+)?)\s*%", r"water\s*%[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("visceral_fat",     "Visceral Fat",  "score", [r"visceral\s*fat[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("bmr_kcal",         "BMR",           "kcal",  [r"\bbmr\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"basal\s*metabolic\s*rate[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("protein_percent",  "Protein",       "%",     [r"protein[^\r\n%:]*[:\s]+(\d+(?:\.\d+)?)\s*%"]),

    # ── Complete Blood Count (CBC) ────────────────────────────────────────────
    ("haemoglobin",      "Haemoglobin",   "g/dL",       [r"h(?:a?e)?moglobin[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"\bhb\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("wbc_count",        "WBC Count",     "cells/cumm",  [r"(?:total\s*)?wbc\s*count[^\r\n:]*[:\s]+(\d+(?:[,\d]+)?)", r"white\s*blood\s*cell[^\r\n:]*[:\s]+(\d+(?:[,\d]+)?)"]),
    ("platelet_count",   "Platelet Count","cells/cumm",  [r"platelet\s*count[^\r\n:]*[:\s]+(\d+(?:[,\d]+)?)"]),
    ("haematocrit",      "Haematocrit",   "%",           [r"h(?:a?e)?matocrit[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"\bpcv\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("rbc_count",        "RBC Count",     "mill/cumm",   [r"rbc\s*count[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"red\s*blood\s*cell[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("mcv",              "MCV",           "fL",          [r"\bmcv\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("mch",              "MCH",           "pg",          [r"\bmch\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("mchc",             "MCHC",          "g/dL",        [r"\bmchc\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),

    # ── Blood Glucose & Diabetes ──────────────────────────────────────────────
    ("fasting_glucose",  "Fasting Blood Glucose", "mg/dL", [r"fasting\s*blood\s*glucose[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"fasting\s*glucose[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"blood\s*glucose[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("hba1c",            "HbA1c",         "%",           [r"hba?1?c[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"glycated\s*haemoglobin[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("avg_glucose",      "Avg Glucose",   "mg/dL",       [r"(?:estimated\s*)?avg\s*glucose[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),

    # ── Lipid Profile ─────────────────────────────────────────────────────────
    ("total_cholesterol","Total Cholesterol","mg/dL",    [r"total\s*cholesterol[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("hdl_cholesterol",  "HDL Cholesterol","mg/dL",     [r"hdl\s*cholesterol[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"\bhdl\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("ldl_cholesterol",  "LDL Cholesterol","mg/dL",     [r"ldl\s*cholesterol[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"\bldl\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("triglycerides",    "Triglycerides", "mg/dL",       [r"triglycerides?[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("vldl_cholesterol", "VLDL Cholesterol","mg/dL",    [r"vldl[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),

    # ── Liver Function ────────────────────────────────────────────────────────
    ("sgot_ast",         "SGOT / AST",    "U/L",         [r"sgot[^\r\n:/]*[:\s]+(\d+(?:\.\d+)?)", r"\bast\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("sgpt_alt",         "SGPT / ALT",    "U/L",         [r"sgpt[^\r\n:/]*[:\s]+(\d+(?:\.\d+)?)", r"\balt\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),

    # ── Kidney Function ───────────────────────────────────────────────────────
    ("creatinine",       "Serum Creatinine","mg/dL",    [r"(?:serum\s*)?creatinine[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("uric_acid",        "Uric Acid",     "mg/dL",       [r"uric\s*acid[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),

    # ── Vitamins & Iron ───────────────────────────────────────────────────────
    ("vitamin_d",        "Vitamin D",     "ng/mL",       [r"vitamin\s*d[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"25.?oh[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("vitamin_b12",      "Vitamin B12",   "pg/mL",       [r"vitamin\s*b\s*12[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)", r"\bb12\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("serum_ferritin",   "Serum Ferritin","ng/mL",       [r"(?:serum\s*)?ferritin[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("serum_iron",       "Serum Iron",    "ug/dL",       [r"serum\s*iron[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),

    # ── Thyroid ───────────────────────────────────────────────────────────────
    ("tsh",              "TSH",           "mIU/L",       [r"\btsh\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("t3",               "T3",            "ng/mL",       [r"\bt3\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
    ("t4",               "T4",            "ug/dL",       [r"\bt4\b[^\r\n:]*[:\s]+(\d+(?:\.\d+)?)"]),
]


def configure_tesseract() -> None:
    env_path = os.getenv("TESSERACT_CMD", "").strip()
    if env_path and Path(env_path).exists():
        pytesseract.pytesseract.tesseract_cmd = env_path
        return
    current = shutil.which("tesseract")
    if current:
        pytesseract.pytesseract.tesseract_cmd = current
        return
    for path in COMMON_TESSERACT_PATHS:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            return


def _clean_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return safe or "report_image.png"


def save_uploaded_report(upload_dir: Path, file_name: str, file_bytes: bytes) -> Tuple[str, str]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _clean_filename(file_name)
    target = upload_dir / safe_name
    counter = 1
    while target.exists():
        target = upload_dir / f"{target.stem}_{counter}{target.suffix}"
        counter += 1
    target.write_bytes(file_bytes)
    return target.name, str(target)


def preprocess_image(image_path: str) -> Image.Image:
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def extract_text_from_image(image_path: str) -> str:
    configure_tesseract()
    try:
        image = preprocess_image(image_path)
        text = pytesseract.image_to_string(image, config="--oem 3 --psm 6")
        return text.strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR is not installed or not found. Install Tesseract and restart the app."
        ) from exc


def _clean_number(raw: str) -> float:
    """Remove commas from numbers like 9,400 before converting to float."""
    return float(raw.replace(",", ""))


def parse_metrics(ocr_text: str) -> List[Dict]:
    text = re.sub(r"[\t]+", " ", ocr_text or "")
    metrics: List[Dict] = []
    seen = set()
    for metric_key, metric_name, unit, patterns in METRIC_PATTERNS:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                try:
                    value = _clean_number(match.group(1))
                except ValueError:
                    continue
                if metric_key in seen:
                    break
                metrics.append({
                    "metric_key":      metric_key,
                    "metric_name":     metric_name,
                    "metric_value":    value,
                    "metric_unit":     unit,
                    "extracted_text":  match.group(0),
                    "confidence_score": 0.85,
                })
                seen.add(metric_key)
                break
    return metrics


def create_report_record(user_id: int, file_name: str, file_path: str, report_type: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO uploaded_reports (user_id, file_name, file_path, report_type, processing_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, file_name, file_path, report_type or None, "pending"),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_report_processing(report_id: int, raw_text: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE uploaded_reports
            SET ocr_raw_text = ?, processing_status = ?
            WHERE id = ?
            """,
            (raw_text, status, report_id),
        )
        conn.commit()


def replace_report_metrics(report_id: int, user_id: int, metrics: List[Dict]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM report_metrics WHERE report_id = ?", (report_id,))
        for item in metrics:
            conn.execute(
                """
                INSERT INTO report_metrics (
                    report_id, user_id, metric_name, metric_value, metric_unit, extracted_text, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    user_id,
                    item["metric_name"],
                    item["metric_value"],
                    item["metric_unit"],
                    item["extracted_text"],
                    item["confidence_score"],
                ),
            )
        conn.commit()


def build_report_insights(metrics: List[Dict]) -> List[Tuple[str, str, str, str]]:
    metric_map = {m["metric_name"]: m for m in metrics}
    insights: List[Tuple[str, str, str, str]] = []

    # Body composition insights
    body_fat      = metric_map.get("Body Fat")
    bmi           = metric_map.get("BMI")
    water         = metric_map.get("Body Water")
    visceral_fat  = metric_map.get("Visceral Fat")
    muscle        = metric_map.get("Muscle Mass")

    if body_fat and body_fat["metric_value"] >= 32:
        insights.append(("report_insight", "ocr_report", "Body fat appears elevated. Focus on sustainable sleep, hydration, walking, and consistent exercise.", "high"))
    elif body_fat and body_fat["metric_value"] <= 20:
        insights.append(("report_insight", "ocr_report", "Body fat is in a lean range. Focus on consistency, strength, and recovery.", "medium"))
    if bmi and bmi["metric_value"] >= 25:
        insights.append(("report_insight", "ocr_report", "BMI is above 25. Track weekly trends and combine nutrition, movement, and sleep goals.", "medium"))
    if water and water["metric_value"] < 45:
        insights.append(("report_insight", "ocr_report", "Body water percentage is low. Increase hydration earlier in the day.", "medium"))
    if visceral_fat and visceral_fat["metric_value"] >= 10:
        insights.append(("report_insight", "ocr_report", "Visceral fat is higher than ideal. Prioritize walking, exercise, sleep, and nutrition.", "high"))
    if muscle and muscle["metric_value"] > 0:
        insights.append(("report_insight", "ocr_report", "Track muscle mass alongside body fat for a fuller picture of body composition.", "low"))

    # Lab report insights
    hb = metric_map.get("Haemoglobin")
    if hb and hb["metric_value"] < 13.0:
        insights.append(("report_insight", "ocr_report", f"Haemoglobin is low ({hb['metric_value']} g/dL) — mild anaemia likely. Consider iron-rich foods or supplementation as advised by your doctor.", "high"))

    glucose = metric_map.get("Fasting Blood Glucose")
    if glucose and glucose["metric_value"] >= 100:
        insights.append(("report_insight", "ocr_report", f"Fasting glucose ({glucose['metric_value']} mg/dL) is above normal. Reduce refined carbs, increase physical activity, and monitor regularly.", "high"))

    hba1c = metric_map.get("HbA1c")
    if hba1c and hba1c["metric_value"] >= 5.7:
        insights.append(("report_insight", "ocr_report", f"HbA1c ({hba1c['metric_value']}%) indicates pre-diabetic range. Dietary modification and regular monitoring are advised.", "high"))

    chol = metric_map.get("Total Cholesterol")
    if chol and chol["metric_value"] >= 200:
        insights.append(("report_insight", "ocr_report", f"Total Cholesterol ({chol['metric_value']} mg/dL) is borderline high. Reduce saturated fats and increase fibre intake.", "medium"))

    hdl = metric_map.get("HDL Cholesterol")
    if hdl and hdl["metric_value"] < 40:
        insights.append(("report_insight", "ocr_report", f"HDL Cholesterol ({hdl['metric_value']} mg/dL) is low. Regular aerobic exercise and healthy fats (nuts, olive oil) can help raise HDL.", "medium"))

    ldl = metric_map.get("LDL Cholesterol")
    if ldl and ldl["metric_value"] >= 130:
        insights.append(("report_insight", "ocr_report", f"LDL Cholesterol ({ldl['metric_value']} mg/dL) is elevated. Limit processed foods and consult your doctor about management.", "high"))

    vit_d = metric_map.get("Vitamin D")
    if vit_d and vit_d["metric_value"] < 30:
        insights.append(("report_insight", "ocr_report", f"Vitamin D ({vit_d['metric_value']} ng/mL) is deficient. Sun exposure and supplementation are commonly recommended.", "medium"))

    ferritin = metric_map.get("Serum Ferritin")
    if ferritin and ferritin["metric_value"] < 12:
        insights.append(("report_insight", "ocr_report", f"Serum Ferritin ({ferritin['metric_value']} ng/mL) is low — iron stores are depleted. Include iron-rich foods and pair with Vitamin C for absorption.", "high"))

    if not insights:
        insights.append(("report_insight", "ocr_report", "Report processed successfully. Use these metrics to track changes over time alongside your daily wellness logs.", "low"))

    return insights[:5]


def save_report_insights(user_id: int, report_id: int, related_date: str, metrics: List[Dict]) -> None:
    insights = build_report_insights(metrics)
    with get_connection() as conn:
        conn.execute(
            'DELETE FROM ai_recommendations WHERE user_id = ? AND source_reference = ? AND related_date = ?',
            (user_id, f"report:{report_id}", related_date),
        )
        for recommendation_type, source_reference, content, priority_level in insights:
            conn.execute(
                """
                INSERT INTO ai_recommendations (user_id, recommendation_type, source_reference, content, priority_level, related_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, recommendation_type, f"report:{report_id}", content, priority_level, related_date),
            )
        conn.commit()


def get_latest_report(user_id: int):
    with get_connection() as conn:
        report = conn.execute(
            """
            SELECT * FROM uploaded_reports
            WHERE user_id = ?
            ORDER BY upload_date DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not report:
            return None
        report_dict = dict(report)
        metrics = conn.execute(
            """
            SELECT * FROM report_metrics
            WHERE user_id = ? AND report_id = ?
            ORDER BY metric_name
            """,
            (user_id, report_dict["id"]),
        ).fetchall()
        report_dict["metrics"] = [dict(row) for row in metrics]
        return report_dict


def get_recent_reports(user_id: int, limit: int = 5):
    with get_connection() as conn:
        reports = conn.execute(
            """
            SELECT * FROM uploaded_reports
            WHERE user_id = ?
            ORDER BY upload_date DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        result = []
        for report in reports:
            item = dict(report)
            metric_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM report_metrics WHERE report_id = ?",
                (item["id"],),
            ).fetchone()["cnt"]
            item["metric_count"] = metric_count
            result.append(item)
        return result