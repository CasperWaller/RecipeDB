# RecipeDB

Full-stack recipe app with:
- FastAPI backend (`backend/`)
- React + Vite frontend (`frontend/`)
- PostgreSQL database

## Quick Deploy Checklist

- [ ] Push latest code to GitHub
- [ ] Provision managed Postgres
- [ ] Deploy backend on Render using [render.yaml](render.yaml)
- [ ] Set backend env vars:
  - [ ] `DATABASE_URL`
  - [ ] `CORS_ORIGINS` (your frontend URL)
- [ ] Deploy frontend on Vercel from `frontend/`
- [ ] Set frontend env var:
  - [ ] `VITE_API_BASE_URL` (your backend URL)
- [ ] Verify in production:
  - [ ] login/register works
  - [ ] admin can create/remove recipes
  - [ ] non-admin cannot create/remove recipes

## Config Files

- Backend env example: [backend/.env.example](backend/.env.example)
- Frontend env example: [frontend/.env.example](frontend/.env.example)
- Full deploy guide: [DEPLOY.md](DEPLOY.md)
