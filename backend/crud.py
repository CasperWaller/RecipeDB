from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, and_, func
import re
import secrets
import hashlib
from .models import Recipe, Ingredient, Tag, RecipeComment, User, AuthToken, RecipeAuthor, CommentAuthor
from .schemas import RecipeCreate, IngredientCreate, TagCreate, CommentCreate


def _hash_password(password: str, salt: str | None = None):
    final_salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), final_salt.encode("utf-8"), 100000)
    return f"{final_salt}${hashed.hex()}"


def _verify_password(password: str, password_hash: str):
    try:
        salt, _ = password_hash.split("$", 1)
    except ValueError:
        return False
    return _hash_password(password, salt) == password_hash


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(func.lower(User.username) == username.strip().lower()).first()


def get_user_by_token(db: Session, token: str):
    token_row = db.query(AuthToken).filter(AuthToken.token == token).first()
    if not token_row:
        return None
    return db.query(User).filter(User.id == token_row.user_id).first()


def register_user(db: Session, username: str, password: str):
    normalized = username.strip().lower()
    if get_user_by_username(db, normalized):
        return None
    has_admin = db.query(User.id).filter(User.is_admin.is_(True)).first() is not None
    user = User(username=normalized, password_hash=_hash_password(password), is_admin=not has_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not _verify_password(password, user.password_hash):
        return None
    token_value = secrets.token_urlsafe(32)
    token = AuthToken(user_id=user.id, token=token_value)
    db.add(token)
    db.commit()
    return token_value, user

def get_recipes(db: Session):
    recipes = db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags),
        selectinload(Recipe.comments)
    ).all()
    _attach_recipe_authors(db, recipes)
    _attach_comment_authors(db, recipes)
    return recipes

def get_recipe(db: Session, recipe_id: int):
    recipe = db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags),
        selectinload(Recipe.comments)
    ).filter(Recipe.id == recipe_id).first()
    if recipe:
        _attach_recipe_authors(db, [recipe])
        _attach_comment_authors(db, [recipe])
    return recipe

def create_recipe(db: Session, recipe: RecipeCreate, user_id: int):
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
    db.add(RecipeAuthor(recipe_id=db_recipe.id, user_id=user_id))
    db.commit()
    db.refresh(db_recipe)
    _attach_recipe_authors(db, [db_recipe])
    _attach_comment_authors(db, [db_recipe])
    return db_recipe

def delete_recipe(db: Session, recipe_id: int):
    db_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if db_recipe:
        comment_ids = [comment.id for comment in db_recipe.comments]
        if comment_ids:
            db.query(CommentAuthor).filter(CommentAuthor.comment_id.in_(comment_ids)).delete(synchronize_session=False)
        db.query(RecipeAuthor).filter(RecipeAuthor.recipe_id == recipe_id).delete(synchronize_session=False)
        db.delete(db_recipe)
        db.commit()
    return db_recipe


def is_recipe_owner(db: Session, recipe_id: int, user_id: int):
    return db.query(RecipeAuthor).filter(
        RecipeAuthor.recipe_id == recipe_id,
        RecipeAuthor.user_id == user_id,
    ).first() is not None


def _split_terms(query: str):
    terms = [t.strip() for t in re.split(r"[,;:\n]+", query or "")]
    return [t for t in terms if t]

def _split_names(value: str):
    return _split_terms(value)

def search_recipes(db: Session, query: str, scope: str = "all"):
    terms = _split_terms(query)
    base = db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags),
        selectinload(Recipe.comments)
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
    recipes = base.filter(and_(*clauses)).all()
    _attach_recipe_authors(db, recipes)
    _attach_comment_authors(db, recipes)
    return recipes

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


# Comments
def get_recipe_comments(db: Session, recipe_id: int):
    comments = db.query(RecipeComment).filter(RecipeComment.recipe_id == recipe_id).order_by(RecipeComment.created_at.desc()).all()
    comment_ids = [item.id for item in comments]
    if not comment_ids:
        return comments
    rows = db.query(CommentAuthor.comment_id, User.username).join(User, User.id == CommentAuthor.user_id).filter(CommentAuthor.comment_id.in_(comment_ids)).all()
    authors = {comment_id: username for comment_id, username in rows}
    for comment in comments:
        comment.created_by_username = authors.get(comment.id)
    return comments


def create_recipe_comment(db: Session, recipe_id: int, comment: CommentCreate, user_id: int):
    db_comment = RecipeComment(recipe_id=recipe_id, content=comment.content.strip())
    db.add(db_comment)
    db.flush()
    db.add(CommentAuthor(comment_id=db_comment.id, user_id=user_id))
    db.commit()
    db.refresh(db_comment)
    db_comment.created_by_username = db.query(User.username).filter(User.id == user_id).scalar()
    return db_comment


def delete_recipe_comment(db: Session, recipe_id: int, comment_id: int):
    db_comment = db.query(RecipeComment).filter(
        RecipeComment.id == comment_id,
        RecipeComment.recipe_id == recipe_id,
    ).first()
    if db_comment:
        db.query(CommentAuthor).filter(CommentAuthor.comment_id == comment_id).delete(synchronize_session=False)
        db.delete(db_comment)
        db.commit()
    return db_comment


def is_comment_owner(db: Session, comment_id: int, user_id: int):
    return db.query(CommentAuthor).filter(
        CommentAuthor.comment_id == comment_id,
        CommentAuthor.user_id == user_id,
    ).first() is not None


def _attach_recipe_authors(db: Session, recipes: list[Recipe]):
    recipe_ids = [recipe.id for recipe in recipes]
    if not recipe_ids:
        return
    rows = db.query(RecipeAuthor.recipe_id, User.username).join(User, User.id == RecipeAuthor.user_id).filter(RecipeAuthor.recipe_id.in_(recipe_ids)).all()
    authors = {recipe_id: username for recipe_id, username in rows}
    for recipe in recipes:
        recipe.created_by_username = authors.get(recipe.id)


def _attach_comment_authors(db: Session, recipes: list[Recipe]):
    comments = [comment for recipe in recipes for comment in (recipe.comments or [])]
    comment_ids = [comment.id for comment in comments]
    if not comment_ids:
        return
    rows = db.query(CommentAuthor.comment_id, User.username).join(User, User.id == CommentAuthor.user_id).filter(CommentAuthor.comment_id.in_(comment_ids)).all()
    authors = {comment_id: username for comment_id, username in rows}
    for comment in comments:
        comment.created_by_username = authors.get(comment.id)
