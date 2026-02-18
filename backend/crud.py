from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, and_, func
import re
from .models import Recipe, Ingredient, Tag
from .schemas import RecipeCreate, IngredientCreate, TagCreate

def get_recipes(db: Session):
    return db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags)
    ).all()

def get_recipe(db: Session, recipe_id: int):
    return db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags)
    ).filter(Recipe.id == recipe_id).first()

def create_recipe(db: Session, recipe: RecipeCreate):
    recipe_data = recipe.dict(exclude={"ingredients", "tags"})
    db_recipe = Recipe(**recipe_data)
    db.add(db_recipe)
    db.flush()

    ingredients = []
    for item in recipe.ingredients or []:
        for raw in _split_names(item.name):
            name = raw.strip().lower()
            if not name:
                continue
            existing = db.query(Ingredient).filter(func.lower(Ingredient.name) == name).first()
            if not existing:
                existing = Ingredient(name=name)
                db.add(existing)
                db.flush()
            ingredients.append(existing)

    tags = []
    for item in recipe.tags or []:
        for raw in _split_names(item.name):
            name = raw.strip().lower()
            if not name:
                continue
            existing = db.query(Tag).filter(func.lower(Tag.name) == name).first()
            if not existing:
                existing = Tag(name=name)
                db.add(existing)
                db.flush()
            tags.append(existing)

    db_recipe.ingredients = ingredients
    db_recipe.tags = tags
    db.commit()
    db.refresh(db_recipe)
    return db_recipe

def delete_recipe(db: Session, recipe_id: int):
    db_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if db_recipe:
        db.delete(db_recipe)
        db.commit()
    return db_recipe


def _split_terms(query: str):
    terms = [t.strip() for t in re.split(r"[,;:\n]+", query or "")]
    return [t for t in terms if t]

def _split_names(value: str):
    return _split_terms(value)

def search_recipes(db: Session, query: str, scope: str = "all"):
    terms = _split_terms(query)
    base = db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags)
    )

    if not terms:
        return base.all()

    if scope == "name":
        clauses = [or_(
            Recipe.title.ilike(f"%{t}%"),
            Recipe.description.ilike(f"%{t}%")
        ) for t in terms]
        return base.filter(and_(*clauses)).all()
    if scope == "ingredients":
        clauses = [
            Recipe.ingredients.any(Ingredient.name.ilike(f"%{t}%"))
            for t in terms
        ]
        return base.filter(and_(*clauses)).all()
    if scope == "tags":
        clauses = [
            Recipe.tags.any(Tag.name.ilike(f"%{t}%"))
            for t in terms
        ]
        return base.filter(and_(*clauses)).all()

    clauses = [or_(
        Recipe.title.ilike(f"%{t}%"),
        Recipe.description.ilike(f"%{t}%"),
        Recipe.ingredients.any(Ingredient.name.ilike(f"%{t}%")),
        Recipe.tags.any(Tag.name.ilike(f"%{t}%"))
    ) for t in terms]
    return base.filter(and_(*clauses)).all()

# Ingredients

def get_ingredients(db: Session):
    return db.query(Ingredient).all()

def create_ingredient(db: Session, ingredient: IngredientCreate):
    data = ingredient.dict()
    data["name"] = data["name"].strip().lower()
    db_ingredient = Ingredient(**data)
    db.add(db_ingredient)
    db.commit()
    db.refresh(db_ingredient)
    return db_ingredient

# Tags
def get_tags(db: Session):
    return db.query(Tag).all()

def create_tag(db: Session, tag: TagCreate):
    data = tag.dict()
    data["name"] = data["name"].strip().lower()
    db_tag = Tag(**data)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag
