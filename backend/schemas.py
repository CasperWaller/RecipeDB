from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

# Recipe schemas
class RecipeBase(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None

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
    model_config = ConfigDict(from_attributes=True)


class RecipeFavorite(BaseModel):
    recipe_id: int


class RecipeFavoriteList(BaseModel):
    recipe_ids: List[int] = Field(default_factory=list)
