import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from . import crud, models, schemas
from .database import engine, get_db, Base

# Create tables
Base.metadata.create_all(bind=engine)


def ensure_users_admin_column():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_admin" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))


ensure_users_admin_column()


def ensure_at_least_one_admin():
    with engine.begin() as connection:
        admin_count = connection.execute(text("SELECT COUNT(*) FROM users WHERE is_admin = TRUE")).scalar()
        if admin_count and int(admin_count) > 0:
            return
        first_user_id = connection.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1")).scalar()
        if first_user_id is None:
            return
        connection.execute(text("UPDATE users SET is_admin = TRUE WHERE id = :user_id"), {"user_id": int(first_user_id)})


ensure_at_least_one_admin()

app = FastAPI(title="Recipe API")

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
allowed_origins = [
    origin.strip() for origin in os.getenv("CORS_ORIGINS", ",".join(default_origins)).split(",") if origin.strip()
]

# Allow cross-origin requests from frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = crud.get_user_by_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def require_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges are required")
    return current_user


@app.get("/")
def root():
    return {"message": "Recipe API is running"}


@app.post("/auth/register", response_model=schemas.UserPublic)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if len(payload.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = crud.register_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=409, detail="Username already exists")
    return user


@app.post("/auth/login", response_model=schemas.AuthTokenResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    result = crud.login_user(db, payload.username, payload.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, user = result
    return {"token": token, "user": user}


@app.get("/auth/me", response_model=schemas.UserPublic)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


# Recipe
@app.post("/recipes/", response_model=schemas.Recipe)
def create_recipe(
    recipe: schemas.RecipeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    return crud.create_recipe(db, recipe, user_id=current_user.id)

@app.get("/recipes/", response_model=list[schemas.Recipe])
def read_recipes(query: str | None = None, scope: str = "all", db: Session = Depends(get_db)):
    if query:
        scope = scope.strip().lower()
        allowed = {"all", "name", "ingredients", "tags"}
        if scope not in allowed:
            raise HTTPException(status_code=400, detail="Invalid scope")
        return crud.search_recipes(db, query, scope=scope)
    return crud.get_recipes(db)

@app.get("/recipes/{recipe_id}", response_model=schemas.Recipe)
def read_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = crud.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe

@app.delete("/recipes/{recipe_id}", response_model=schemas.Recipe)
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    recipe = crud.delete_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.get("/recipes/{recipe_id}/comments", response_model=list[schemas.Comment])
def read_recipe_comments(recipe_id: int, db: Session = Depends(get_db)):
    recipe = crud.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return crud.get_recipe_comments(db, recipe_id)


@app.post("/recipes/{recipe_id}/comments", response_model=schemas.Comment)
def add_recipe_comment(
    recipe_id: int,
    comment: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    recipe = crud.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not comment.content.strip():
        raise HTTPException(status_code=400, detail="Comment content is required")
    return crud.create_recipe_comment(db, recipe_id, comment, user_id=current_user.id)


@app.delete("/recipes/{recipe_id}/comments/{comment_id}", response_model=schemas.Comment)
def remove_recipe_comment(
    recipe_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    recipe = crud.get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if not crud.is_comment_owner(db, comment_id, current_user.id):
        raise HTTPException(status_code=403, detail="Only the comment author can remove this comment")

    deleted_comment = crud.delete_recipe_comment(db, recipe_id, comment_id)
    if deleted_comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return deleted_comment

@app.get("/recipes/search", response_model=list[schemas.Recipe])
def search(query: str, scope: str = "all", db: Session = Depends(get_db)):
    scope = scope.strip().lower()
    allowed = {"all", "name", "ingredients", "tags"}
    if scope not in allowed:
        raise HTTPException(status_code=400, detail="Invalid scope")
    return crud.search_recipes(db, query, scope=scope)

# Ingredients
@app.post("/ingredients/", response_model=schemas.Ingredient)
def create_ingredient(
    ingredient: schemas.IngredientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.create_ingredient(db, ingredient)

@app.get("/ingredients/", response_model=list[schemas.Ingredient])
def read_ingredients(db: Session = Depends(get_db)):
    return crud.get_ingredients(db)

# Tags
@app.post("/tags/", response_model=schemas.Tag)
def create_tag(
    tag: schemas.TagCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.create_tag(db, tag)

@app.get("/tags/", response_model=list[schemas.Tag])
def read_tags(db: Session = Depends(get_db)):
    return crud.get_tags(db)
