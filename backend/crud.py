from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, and_, func
from datetime import datetime, timedelta
import re
import secrets
import hashlib
from .models import (
    Recipe,
    Ingredient,
    Tag,
    RecipeComment,
    User,
    AuthToken,
    RecipeAuthor,
    CommentAuthor,
    RecipeIngredient,
    RecipeFavorite,
    OnlineDevicePresence,
    CommentLike,
)
from .schemas import RecipeCreate, IngredientCreate, TagCreate, CommentCreate


VALID_QUANTITY_UNITS = {"ml", "cl", "dl", "l", "mg", "g", "kg", "st"}
QUANTITY_PATTERN = re.compile(r"^\d+(?:[\.,]\d+)?\s*(ml|cl|dl|l|mg|g|kg|st)$", re.IGNORECASE)


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


def get_user_by_token(db: Session, token: str, touch: bool = False):
    token_row = db.query(AuthToken).filter(AuthToken.token == token).first()
    if not token_row:
        return None
    if touch:
        token_row.last_seen_at = datetime.utcnow()
        db.commit()
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


def get_online_device_count(db: Session, window_seconds: int = 300):
    safe_window = max(30, int(window_seconds or 300))
    threshold = datetime.utcnow() - timedelta(seconds=safe_window)
    rows = db.query(
        OnlineDevicePresence.device_id,
        OnlineDevicePresence.user_id,
        OnlineDevicePresence.user_agent,
    ).filter(
        OnlineDevicePresence.last_seen_at >= threshold
    ).all()

    unique_keys = set()
    for device_id, user_id, user_agent in rows:
        normalized_agent = (user_agent or "").strip().lower()
        if user_id is not None and normalized_agent:
            unique_keys.add(f"user:{int(user_id)}:agent:{normalized_agent}")
            continue
        if user_id is not None:
            unique_keys.add(f"user:{int(user_id)}:device:{device_id}")
            continue
        unique_keys.add(f"anon:{device_id}")

    return len(unique_keys)


def touch_online_device(db: Session, device_id: str, user_id: int | None = None, user_agent: str | None = None):
    normalized_device_id = (device_id or "").strip()
    if not normalized_device_id:
        return

    row = db.query(OnlineDevicePresence).filter(OnlineDevicePresence.device_id == normalized_device_id).first()
    now = datetime.utcnow()
    normalized_user_agent = (user_agent or "").strip() or None
    if row is None:
        db.add(
            OnlineDevicePresence(
                device_id=normalized_device_id,
                user_id=user_id,
                user_agent=normalized_user_agent,
                last_seen_at=now,
            )
        )
    else:
        row.last_seen_at = now
        if user_id is not None:
            row.user_id = user_id
        if normalized_user_agent is not None:
            row.user_agent = normalized_user_agent
    db.commit()


def remove_online_device(db: Session, device_id: str):
    normalized_device_id = (device_id or "").strip()
    if not normalized_device_id:
        return

    row = db.query(OnlineDevicePresence).filter(OnlineDevicePresence.device_id == normalized_device_id).first()
    if row is None:
        return
    db.delete(row)
    db.commit()

def get_recipes(db: Session):
    recipes = db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags),
        selectinload(Recipe.comments)
    ).all()
    _attach_recipe_authors(db, recipes)
    _attach_favorite_counts(db, recipes)
    _attach_ingredient_measurements(db, recipes)
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
        _attach_favorite_counts(db, [recipe])
        _attach_ingredient_measurements(db, [recipe])
        _attach_comment_authors(db, [recipe])
    return recipe

def create_recipe(db: Session, recipe: RecipeCreate, user_id: int):
    recipe_data = recipe.dict(exclude={"ingredients", "tags"})
    db_recipe = Recipe(**recipe_data)
    db.add(db_recipe)
    db.flush()

    ingredient_entries = _extract_ingredient_entries(recipe.ingredients or [])
    ingredients = []
    ingredient_by_name = {}
    missing_ingredients = []
    for name, _ in ingredient_entries:
        existing = db.query(Ingredient).filter(func.lower(Ingredient.name) == name).first()
        if not existing:
            missing_ingredients.append(name)
            continue
        ingredients.append(existing)
        ingredient_by_name[name] = existing

    if missing_ingredients:
        unique_missing = sorted(set(missing_ingredients))
        raise ValueError(f"Unknown ingredients: {', '.join(unique_missing)}. Add them to the ingredient list first.")

    tag_names = _extract_unique_names(recipe.tags or [], "tags")
    tags = []
    for name in tag_names:
        existing = db.query(Tag).filter(func.lower(Tag.name) == name).first()
        if not existing:
            existing = Tag(name=name)
            db.add(existing)
            db.flush()
        tags.append(existing)

    db_recipe.ingredients = ingredients
    db_recipe.tags = tags
    db.flush()
    _apply_recipe_ingredient_quantities(db, db_recipe.id, ingredient_entries, ingredient_by_name)
    db.add(RecipeAuthor(recipe_id=db_recipe.id, user_id=user_id))
    db.commit()
    db.refresh(db_recipe)
    _attach_recipe_authors(db, [db_recipe])
    _attach_favorite_counts(db, [db_recipe])
    _attach_ingredient_measurements(db, [db_recipe])
    _attach_comment_authors(db, [db_recipe])
    return db_recipe


def update_recipe(db: Session, recipe_id: int, recipe: RecipeCreate):
    db_recipe = db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags),
        selectinload(Recipe.comments),
    ).filter(Recipe.id == recipe_id).first()
    if db_recipe is None:
        return None

    recipe_data = recipe.dict(exclude={"ingredients", "tags"})
    for key, value in recipe_data.items():
        setattr(db_recipe, key, value)

    ingredient_entries = _extract_ingredient_entries(recipe.ingredients or [])
    ingredients = []
    ingredient_by_name = {}
    missing_ingredients = []
    for name, _ in ingredient_entries:
        existing = db.query(Ingredient).filter(func.lower(Ingredient.name) == name).first()
        if not existing:
            missing_ingredients.append(name)
            continue
        ingredients.append(existing)
        ingredient_by_name[name] = existing

    if missing_ingredients:
        unique_missing = sorted(set(missing_ingredients))
        raise ValueError(f"Unknown ingredients: {', '.join(unique_missing)}. Add them to the ingredient list first.")

    tag_names = _extract_unique_names(recipe.tags or [], "tags")
    tags = []
    for name in tag_names:
        existing = db.query(Tag).filter(func.lower(Tag.name) == name).first()
        if not existing:
            existing = Tag(name=name)
            db.add(existing)
            db.flush()
        tags.append(existing)

    db_recipe.ingredients = ingredients
    db_recipe.tags = tags
    db.flush()
    _apply_recipe_ingredient_quantities(db, db_recipe.id, ingredient_entries, ingredient_by_name)

    db.commit()
    db.refresh(db_recipe)
    _attach_recipe_authors(db, [db_recipe])
    _attach_favorite_counts(db, [db_recipe])
    _attach_ingredient_measurements(db, [db_recipe])
    _attach_comment_authors(db, [db_recipe])
    return db_recipe

def delete_recipe(db: Session, recipe_id: int):
    db_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if db_recipe:
        comment_ids = [comment.id for comment in db_recipe.comments]
        if comment_ids:
            db.query(CommentLike).filter(CommentLike.comment_id.in_(comment_ids)).delete(synchronize_session=False)
            db.query(CommentAuthor).filter(CommentAuthor.comment_id.in_(comment_ids)).delete(synchronize_session=False)
        db.query(RecipeFavorite).filter(RecipeFavorite.recipe_id == recipe_id).delete(synchronize_session=False)
        db.query(RecipeAuthor).filter(RecipeAuthor.recipe_id == recipe_id).delete(synchronize_session=False)
        db.delete(db_recipe)
        db.commit()
    return db_recipe


def get_favorite_recipe_ids(db: Session, user_id: int):
    rows = db.query(RecipeFavorite.recipe_id).filter(RecipeFavorite.user_id == user_id).all()
    return [recipe_id for (recipe_id,) in rows]


def add_recipe_favorite(db: Session, recipe_id: int, user_id: int):
    recipe_exists = db.query(Recipe.id).filter(Recipe.id == recipe_id).first()
    if recipe_exists is None:
        return None

    existing = db.query(RecipeFavorite).filter(
        RecipeFavorite.recipe_id == recipe_id,
        RecipeFavorite.user_id == user_id,
    ).first()
    if existing is None:
        db.add(RecipeFavorite(recipe_id=recipe_id, user_id=user_id))
        db.commit()

    return {"recipe_id": recipe_id}


def remove_recipe_favorite(db: Session, recipe_id: int, user_id: int):
    favorite = db.query(RecipeFavorite).filter(
        RecipeFavorite.recipe_id == recipe_id,
        RecipeFavorite.user_id == user_id,
    ).first()
    if favorite is None:
        return {"recipe_id": recipe_id}

    db.delete(favorite)
    db.commit()
    return {"recipe_id": recipe_id}


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


def _extract_unique_names(items: list[IngredientCreate | TagCreate], field_label: str):
    names = []
    for item in items:
        for raw in _split_names(item.name):
            normalized = raw.strip().lower()
            if normalized:
                names.append(normalized)

    seen = set()
    duplicates = []
    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)

    if duplicates:
        raise ValueError(f"Duplicate {field_label}: {', '.join(duplicates)}")

    return names


def _extract_ingredient_entries(items: list[IngredientCreate]):
    entries = []
    for item in items:
        quantity = _normalize_quantity(item.quantity)
        for raw in _split_names(item.name):
            normalized = raw.strip().lower()
            if normalized:
                entries.append((normalized, quantity))

    names = [name for name, _ in entries]
    seen = set()
    duplicates = []
    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)

    if duplicates:
        raise ValueError(f"Duplicate ingredients: {', '.join(duplicates)}")

    return entries


def _normalize_quantity(raw_quantity: str | None):
    value = (raw_quantity or "").strip().lower()
    if not value:
        return None

    compact = re.sub(r"\s+", "", value)
    match = QUANTITY_PATTERN.match(compact)
    if not match:
        raise ValueError("Quantity must use EU units like ml, dl, l, g, or kg (example: 2 dl)")

    unit = match.group(1).lower()
    if unit not in VALID_QUANTITY_UNITS:
        raise ValueError("Unsupported quantity unit")

    number = compact[: -len(unit)]
    return f"{number} {unit}".replace(",", ".")


def _apply_recipe_ingredient_quantities(
    db: Session,
    recipe_id: int,
    ingredient_entries: list[tuple[str, str | None]],
    ingredient_by_name: dict[str, Ingredient],
):
    for name, quantity in ingredient_entries:
        ingredient = ingredient_by_name.get(name)
        if ingredient is None:
            continue
        row = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id,
            RecipeIngredient.ingredient_id == ingredient.id,
        ).first()
        if row:
            row.quantity = quantity

def search_recipes(db: Session, query: str, scope: str = "all"):
    terms = _split_terms(query)
    base = db.query(Recipe).options(
        selectinload(Recipe.ingredients),
        selectinload(Recipe.tags),
        selectinload(Recipe.comments)
    )

    def _with_authors(results: list[Recipe]):
        _attach_recipe_authors(db, results)
        _attach_favorite_counts(db, results)
        _attach_ingredient_measurements(db, results)
        _attach_comment_authors(db, results)
        return results

    if not terms:
        return _with_authors(base.all())

    if scope == "name":
        clauses = [or_(
            Recipe.title.ilike(f"%{t}%"),
            Recipe.description.ilike(f"%{t}%")
        ) for t in terms]
        return _with_authors(base.filter(and_(*clauses)).all())
    if scope == "ingredients":
        clauses = [
            Recipe.ingredients.any(Ingredient.name.ilike(f"%{t}%"))
            for t in terms
        ]
        return _with_authors(base.filter(and_(*clauses)).all())
    if scope == "tags":
        clauses = [
            Recipe.tags.any(Tag.name.ilike(f"%{t}%"))
            for t in terms
        ]
        return _with_authors(base.filter(and_(*clauses)).all())

    clauses = [or_(
        Recipe.title.ilike(f"%{t}%"),
        Recipe.description.ilike(f"%{t}%"),
        Recipe.ingredients.any(Ingredient.name.ilike(f"%{t}%")),
        Recipe.tags.any(Tag.name.ilike(f"%{t}%"))
    ) for t in terms]
    return _with_authors(base.filter(and_(*clauses)).all())

# Ingredients

def get_ingredients(db: Session):
    ingredients = db.query(Ingredient).order_by(func.lower(Ingredient.name)).all()
    ingredient_ids = [item.id for item in ingredients]
    if not ingredient_ids:
        return ingredients

    rows = db.query(
        RecipeIngredient.ingredient_id,
        func.count(RecipeIngredient.recipe_id),
    ).filter(
        RecipeIngredient.ingredient_id.in_(ingredient_ids)
    ).group_by(
        RecipeIngredient.ingredient_id
    ).all()

    recipe_counts = {ingredient_id: int(count) for ingredient_id, count in rows}
    for ingredient in ingredients:
        ingredient.recipe_count = recipe_counts.get(ingredient.id, 0)
    return ingredients

def create_ingredient(db: Session, ingredient: IngredientCreate):
    normalized_name = (ingredient.name or "").strip().lower()
    if not normalized_name:
        raise ValueError("Ingredient name is required")

    existing = db.query(Ingredient).filter(func.lower(Ingredient.name) == normalized_name).first()
    if existing is not None:
        raise ValueError("Ingredient already exists")

    db_ingredient = Ingredient(name=normalized_name)
    db.add(db_ingredient)
    db.commit()
    db.refresh(db_ingredient)
    db_ingredient.recipe_count = 0
    return db_ingredient


def update_ingredient(db: Session, ingredient_id: int, name: str):
    db_ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if db_ingredient is None:
        return None

    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        raise ValueError("Ingredient name is required")

    duplicate = db.query(Ingredient).filter(
        func.lower(Ingredient.name) == normalized_name,
        Ingredient.id != ingredient_id,
    ).first()
    if duplicate is not None:
        raise ValueError("Ingredient already exists")

    db_ingredient.name = normalized_name
    db.commit()
    db.refresh(db_ingredient)

    recipe_count = db.query(func.count(RecipeIngredient.recipe_id)).filter(
        RecipeIngredient.ingredient_id == ingredient_id
    ).scalar() or 0
    db_ingredient.recipe_count = int(recipe_count)
    return db_ingredient


def delete_ingredient(db: Session, ingredient_id: int):
    db_ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if db_ingredient is None:
        return None

    in_use = db.query(RecipeIngredient.recipe_id).filter(RecipeIngredient.ingredient_id == ingredient_id).first()
    if in_use is not None:
        raise ValueError("Cannot delete ingredient that is used by recipes")

    db.delete(db_ingredient)
    db.commit()
    db_ingredient.recipe_count = 0
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
    like_rows = db.query(
        CommentLike.comment_id,
        func.count(CommentLike.user_id),
    ).filter(
        CommentLike.comment_id.in_(comment_ids)
    ).group_by(
        CommentLike.comment_id
    ).all()
    like_counts = {comment_id: int(count) for comment_id, count in like_rows}
    for comment in comments:
        comment.created_by_username = authors.get(comment.id)
        comment.like_count = like_counts.get(comment.id, 0)
    return comments


def create_recipe_comment(db: Session, recipe_id: int, comment: CommentCreate, user_id: int):
    db_comment = RecipeComment(recipe_id=recipe_id, content=comment.content.strip())
    db.add(db_comment)
    db.flush()
    db.add(CommentAuthor(comment_id=db_comment.id, user_id=user_id))
    db.commit()
    db.refresh(db_comment)
    db_comment.created_by_username = db.query(User.username).filter(User.id == user_id).scalar()
    db_comment.like_count = 0
    return db_comment


def delete_recipe_comment(db: Session, recipe_id: int, comment_id: int):
    db_comment = db.query(RecipeComment).filter(
        RecipeComment.id == comment_id,
        RecipeComment.recipe_id == recipe_id,
    ).first()
    if db_comment:
        db.query(CommentLike).filter(CommentLike.comment_id == comment_id).delete(synchronize_session=False)
        db.query(CommentAuthor).filter(CommentAuthor.comment_id == comment_id).delete(synchronize_session=False)
        db.delete(db_comment)
        db.commit()
    return db_comment


def get_liked_comment_ids(db: Session, recipe_id: int, user_id: int):
    rows = db.query(CommentLike.comment_id).join(
        RecipeComment,
        RecipeComment.id == CommentLike.comment_id,
    ).filter(
        CommentLike.user_id == user_id,
        RecipeComment.recipe_id == recipe_id,
    ).all()
    return [comment_id for (comment_id,) in rows]


def add_comment_like(db: Session, recipe_id: int, comment_id: int, user_id: int):
    comment_exists = db.query(RecipeComment.id).filter(
        RecipeComment.id == comment_id,
        RecipeComment.recipe_id == recipe_id,
    ).first()
    if comment_exists is None:
        return None

    existing = db.query(CommentLike).filter(
        CommentLike.comment_id == comment_id,
        CommentLike.user_id == user_id,
    ).first()
    if existing is None:
        db.add(CommentLike(comment_id=comment_id, user_id=user_id))
        db.commit()
    return {"comment_id": comment_id}


def remove_comment_like(db: Session, recipe_id: int, comment_id: int, user_id: int):
    comment_exists = db.query(RecipeComment.id).filter(
        RecipeComment.id == comment_id,
        RecipeComment.recipe_id == recipe_id,
    ).first()
    if comment_exists is None:
        return None

    like = db.query(CommentLike).filter(
        CommentLike.comment_id == comment_id,
        CommentLike.user_id == user_id,
    ).first()
    if like is not None:
        db.delete(like)
        db.commit()
    return {"comment_id": comment_id}


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


def _attach_favorite_counts(db: Session, recipes: list[Recipe]):
    recipe_ids = [recipe.id for recipe in recipes]
    if not recipe_ids:
        return

    rows = db.query(
        RecipeFavorite.recipe_id,
        func.count(RecipeFavorite.user_id),
    ).filter(
        RecipeFavorite.recipe_id.in_(recipe_ids)
    ).group_by(
        RecipeFavorite.recipe_id
    ).all()

    counts = {recipe_id: int(count) for recipe_id, count in rows}
    for recipe in recipes:
        recipe.favorite_count = counts.get(recipe.id, 0)


def _attach_ingredient_measurements(db: Session, recipes: list[Recipe]):
    recipe_ids = [recipe.id for recipe in recipes]
    if not recipe_ids:
        return

    rows = db.query(
        RecipeIngredient.recipe_id,
        RecipeIngredient.ingredient_id,
        Ingredient.name,
        RecipeIngredient.quantity,
    ).join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id).filter(
        RecipeIngredient.recipe_id.in_(recipe_ids)
    ).all()

    by_recipe_id: dict[int, list[dict]] = {recipe_id: [] for recipe_id in recipe_ids}
    for recipe_id, ingredient_id, name, quantity in rows:
        by_recipe_id.setdefault(recipe_id, []).append(
            {
                "ingredient_id": ingredient_id,
                "name": name,
                "quantity": quantity,
            }
        )

    for recipe in recipes:
        recipe.ingredient_measurements = by_recipe_id.get(recipe.id, [])


def _attach_comment_authors(db: Session, recipes: list[Recipe]):
    comments = [comment for recipe in recipes for comment in (recipe.comments or [])]
    comment_ids = [comment.id for comment in comments]
    if not comment_ids:
        return
    rows = db.query(CommentAuthor.comment_id, User.username).join(User, User.id == CommentAuthor.user_id).filter(CommentAuthor.comment_id.in_(comment_ids)).all()
    authors = {comment_id: username for comment_id, username in rows}
    like_rows = db.query(
        CommentLike.comment_id,
        func.count(CommentLike.user_id),
    ).filter(
        CommentLike.comment_id.in_(comment_ids)
    ).group_by(
        CommentLike.comment_id
    ).all()
    like_counts = {comment_id: int(count) for comment_id, count in like_rows}
    for comment in comments:
        comment.created_by_username = authors.get(comment.id)
        comment.like_count = like_counts.get(comment.id, 0)
