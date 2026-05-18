# Deployment

This project is set up to deploy as a public web app on Render.

## Render deployment

1. Push this project to a GitHub repository.
2. In Render, create a new **Blueprint** service from the repository.
3. Render will read [render.yaml](/C:/Users/manoj.arasada/Downloads/AI_Wellness_Companion_Project_Step8/AI_Wellness_Companion_Project_Step8/AI_Wellness_Companion_Project/render.yaml).
4. Set `OPENAI_API_KEY` in Render.
5. Deploy the service.

### What Render will configure

- Docker build using the included [Dockerfile](/C:/Users/manoj.arasada/Downloads/AI_Wellness_Companion_Project_Step8/AI_Wellness_Companion_Project_Step8/AI_Wellness_Companion_Project/Dockerfile)
- Persistent disk mounted at `/var/data`
- SQLite database stored at `/var/data/database/wellness_app.db`
- Uploaded report files stored at `/var/data/uploads/reports`
- A generated `SESSION_SECRET_KEY`
- `OPENAI_MODEL=gpt-5-mini`

## Local Docker test

```powershell
docker build -t ai-wellness-companion .
docker run --rm -p 8000:8000 `
  -e OPENAI_API_KEY="your_key_here" `
  -e OPENAI_MODEL="gpt-5-mini" `
  -e SESSION_SECRET_KEY="replace_with_a_long_random_string" `
  -e WELLNESS_DB_PATH="/var/data/database/wellness_app.db" `
  -e WELLNESS_UPLOAD_DIR="/var/data/uploads/reports" `
  -v ${PWD}\data:/var/data `
  ai-wellness-companion
```

Open:

```text
http://127.0.0.1:8000
```

## Production notes

- The app does not rely on `.env.example` in production.
- The app is responsive and includes a PWA manifest and service worker, so it can be installed on mobile from the browser.
- If you want zero data loss across restarts, keep the persistent disk enabled in Render.
