# Deployment Guide

## Backend (Railway)

This repo includes `railway.json` for Railway deploy.

1. Push repository to GitHub.
2. In Railway, create a new project and select **Deploy from GitHub repo**.
3. Railway will automatically detect the `railway.json` and build using the `Dockerfile`.
4. Set environment variables on the service:
   - `DATABASE_URL` = your managed Postgres URL (add a Railway Postgres plugin or use an external DB)
   - `CORS_ORIGINS` = your frontend URL (for example `https://your-app.vercel.app`)
5. Deploy. Backend will run with:
   - `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

## Backend (Render)

This repo includes `render.yaml` for blueprint deploy.

1. Push repository to GitHub.
2. In Render, create a new Blueprint instance from the repo.
3. Set environment variables on the `recipedb-backend` service:
   - `DATABASE_URL` = your managed Postgres URL
   - `CORS_ORIGINS` = your frontend URL (for example `https://your-app.vercel.app`)
4. Deploy. Backend will run with:
   - `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

## Frontend (Vercel)

This repo includes `frontend/vercel.json`.

1. Import the `frontend` folder as a Vercel project.
2. Set environment variable:
   - `VITE_API_BASE_URL` = your Render backend URL (for example `https://recipedb-backend.onrender.com`)
3. Deploy.

## Final Check

- Open frontend URL and test login.
- Confirm recipe load, create (admin), and delete (admin).
- If API calls fail, re-check `CORS_ORIGINS` and `VITE_API_BASE_URL`.
