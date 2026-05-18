AI Wellness Companion - Step 8

This step adds OCR-based health report upload and extraction.

WHAT IS NEW
- Upload a body composition or health report image
- OCR text extraction using Tesseract on your local machine
- Metric parsing for weight, BMI, body fat, muscle mass, body water, visceral fat, and BMR
- Structured values saved to the local SQLite database
- Report-based insights added into the recommendations table
- New page: /report-analyzer

WINDOWS TESSERACT INSTALLATION
1. Download Tesseract OCR for Windows.
   Recommended installer source:
   https://github.com/UB-Mannheim/tesseract/wiki
2. Install it to the default path:
   C:\Program Files\Tesseract-OCR3. During install, keep the main English language package selected.
4. After installation, close and reopen your command prompt.

OPTIONAL PATH CHECK
Open a fresh command prompt and run:
    tesseract --version
If that works, Tesseract is available in PATH.

IF tesseract --version DOES NOT WORK
You can still run this project if Tesseract was installed in the default folder.
The app checks these common locations automatically:
- C:\Program Files\Tesseract-OCR	esseract.exe
- C:\Program Files (x86)\Tesseract-OCR	esseract.exe

PYTHON PACKAGE INSTALL
Run this inside the project folder:
    python -m pip install -r requirements.txt

START THE APP
Run:
    python -m uvicorn main:app --reload

OPEN IN BROWSER
    http://127.0.0.1:8000

TEST FLOW
1. Login
2. Go to Report Analyzer
3. Upload a clear image with body/health metrics
4. Review extracted values and OCR raw text
5. Open Dashboard and confirm the latest OCR summary appears

NOTES
- No API key is required for this step.
- OCR quality depends on image clarity.
- This step is fully local and offline after Tesseract is installed.
