from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import crud, models, schemas
from .database import engine, get_db, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Recipe API")

# Allow cross-origin requests from frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Recipe API is running"}


# Recipe
@app.post("/recipes/", response_model=schemas.Recipe)
def create_recipe(recipe: schemas.RecipeCreate, db: Session = Depends(get_db)):
    return crud.create_recipe(db, recipe)

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
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = crud.delete_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe

@app.get("/recipes/search", response_model=list[schemas.Recipe])
def search(query: str, scope: str = "all", db: Session = Depends(get_db)):
    scope = scope.strip().lower()
    allowed = {"all", "name", "ingredients", "tags"}
    if scope not in allowed:
        raise HTTPException(status_code=400, detail="Invalid scope")
    return crud.search_recipes(db, query, scope=scope)

# Ingredients
@app.post("/ingredients/", response_model=schemas.Ingredient)
def create_ingredient(ingredient: schemas.IngredientCreate, db: Session = Depends(get_db)):
    return crud.create_ingredient(db, ingredient)

@app.get("/ingredients/", response_model=list[schemas.Ingredient])
def read_ingredients(db: Session = Depends(get_db)):
    return crud.get_ingredients(db)

# Tags
@app.post("/tags/", response_model=schemas.Tag)
def create_tag(tag: schemas.TagCreate, db: Session = Depends(get_db)):
    return crud.create_tag(db, tag)

@app.get("/tags/", response_model=list[schemas.Tag])
def read_tags(db: Session = Depends(get_db)):
    return crud.get_tags(db)
