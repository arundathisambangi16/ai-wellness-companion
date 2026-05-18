# Publishing AI Wellness Companion to Render

Follow these steps in order. The whole process takes about 10–15 minutes.

---

## Step 1 — Create a GitHub repository

1. Go to https://github.com and sign in (or create a free account).
2. Click the **+** icon (top-right) → **New repository**.
3. Name it `ai-wellness-companion` (or anything you like).
4. Set it to **Private** (recommended — keeps your data out of public search).
5. Do **not** check "Add a README" or "Add .gitignore" — the project already has those.
6. Click **Create repository**.
7. Copy the repository URL shown on the next screen — it will look like:
   ```
   https://github.com/YOUR-USERNAME/ai-wellness-companion.git
   ```

---

## Step 2 — Push the project to GitHub

Open a Command Prompt or PowerShell window, navigate to the project folder, and run these commands one at a time:

```powershell
cd "C:\Users\manoj.arasada\Downloads\AI_Wellness_Companion_Project_Step8\AI_Wellness_Companion_Project_Step8\AI_Wellness_Companion_Project"

# Tell git your GitHub repo URL (replace the URL with yours from Step 1)
git remote add origin https://github.com/YOUR-USERNAME/ai-wellness-companion.git

# Stage everything and make the first commit
git add .
git commit -m "Initial publish"

# Push to GitHub
git push -u origin main
```

> If git asks for your GitHub password, use a **Personal Access Token** instead
> (GitHub no longer accepts plain passwords). Create one at:
> https://github.com/settings/tokens → Generate new token → check "repo" scope.

---

## Step 3 — Deploy on Render

1. Go to https://render.com and sign in (or create a free account — the Starter plan is free).
2. Click **New +** → **Blueprint**.
3. Connect your GitHub account if prompted, then select your `ai-wellness-companion` repository.
4. Render will detect `render.yaml` automatically and show the service configuration.
5. Click **Apply**.

---

## Step 4 — Set your OpenAI API key

After clicking Apply, Render will show a list of environment variables. One of them — `OPENAI_API_KEY` — is marked as requiring a value:

1. Paste your real OpenAI API key into the `OPENAI_API_KEY` field.
2. Leave all other values as-is (they are already configured in `render.yaml`).
3. Click **Apply** to start the deployment.

> Get an OpenAI API key at: https://platform.openai.com/api-keys

---

## Step 5 — Wait for the build to finish

Render will:
- Pull your code from GitHub
- Build the Docker image (installs Python, Tesseract OCR, and all dependencies)
- Start the web service

This usually takes **3–5 minutes** on the first deploy.

Once the build is green, Render shows a URL like:
```
https://ai-wellness-companion.onrender.com
```

Open it in your browser — your app is live!

---

## After deployment — things to know

- **Auto-deploy:** Every time you push a new commit to GitHub, Render automatically rebuilds and redeploys. This is enabled by `autoDeploy: true` in `render.yaml`.
- **Persistent data:** Your SQLite database and uploaded reports are stored on a 1 GB persistent disk at `/var/data`. Data survives restarts and redeploys.
- **Free tier sleep:** On Render's free Starter plan, your service may sleep after 15 minutes of inactivity. The first request after sleep takes ~30 seconds to wake up. Upgrade to a paid instance type to avoid this.
- **PWA:** The app includes a service worker and web manifest, so users on mobile can install it from the browser like a native app.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build fails with "pip install" error | Check that `requirements.txt` is committed |
| App starts but Coach returns no AI reply | Check that `OPENAI_API_KEY` is set correctly in Render Environment tab |
| OCR returns no text | Tesseract is installed in the Docker image — ensure the uploaded image is clear and high-contrast |
| 500 error on first load | Check Render logs → likely a missing env var or DB path issue |
