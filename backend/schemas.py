from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

# Ingredient schemas
class IngredientBase(BaseModel):
    name: str

class IngredientCreate(IngredientBase):
    pass

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

class Recipe(RecipeBase):
    id: int
    ingredients: List[Ingredient] = Field(default_factory=list)
    tags: List[Tag] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
