from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Literal
from datetime import datetime
import json


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_super_admin: bool
    model_config = ConfigDict(from_attributes=True)


class UserRoleUpdate(BaseModel):
    role: Literal["user", "admin", "super_admin"]


class AuthTokenResponse(BaseModel):
    token: str
    user: UserPublic

# Ingredient schemas
class IngredientBase(BaseModel):
    name: str

class IngredientCreate(IngredientBase):
    quantity: Optional[str] = None

class Ingredient(IngredientBase):
    id: int
    recipe_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class IngredientUpdate(IngredientBase):
    pass

# Tag schemas
class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# Comment schemas
class CommentBase(BaseModel):
    content: str


class CommentCreate(CommentBase):
    pass


class Comment(CommentBase):
    id: int
    recipe_id: int
    created_at: Optional[datetime] = None
    created_by_username: Optional[str] = None
    like_count: int = 0
    recipe_title: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Recipe schemas
class RecipeBase(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    servings: Optional[int] = None
    is_public: Optional[bool] = True
    allowed_usernames: Optional[List[str]] = None
    allergens: List[str] = Field(default_factory=list)

    @field_validator("allergens", mode="before")
    @classmethod
    def normalize_allergens(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item).strip().lower() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
            return [item.strip().lower() for item in raw.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip().lower() for item in value if str(item).strip()]
        return []

class RecipeCreate(RecipeBase):
    ingredients: List[IngredientCreate] = Field(default_factory=list)
    tags: List[TagCreate] = Field(default_factory=list)


class IngredientMeasurement(BaseModel):
    ingredient_id: int
    name: str
    quantity: Optional[str] = None

class Recipe(RecipeBase):
    id: int
    ingredients: List[Ingredient] = Field(default_factory=list)
    ingredient_measurements: List[IngredientMeasurement] = Field(default_factory=list)
    tags: List[Tag] = Field(default_factory=list)
    comments: List[Comment] = Field(default_factory=list)
    created_by_username: Optional[str] = None
    favorite_count: int = 0
    servings: Optional[int] = None
    allowed_usernames: Optional[List[str]] = None
    model_config = ConfigDict(from_attributes=True)


class RecipeFavorite(BaseModel):
    recipe_id: int


class RecipeFavoriteList(BaseModel):
    recipe_ids: List[int] = Field(default_factory=list)


class CommentLike(BaseModel):
    comment_id: int


class CommentLikeList(BaseModel):
    comment_ids: List[int] = Field(default_factory=list)


class OnlineDevicesResponse(BaseModel):
    online_devices: int = 0


class PresenceHeartbeatRequest(BaseModel):
    device_id: str
