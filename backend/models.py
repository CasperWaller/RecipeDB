from sqlalchemy import Column, Integer, Text, ForeignKey, TIMESTAMP, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    prep_time = Column(Integer)
    cook_time = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
    ingredients = relationship("Ingredient", secondary="recipe_ingredients", back_populates="recipes")
    tags = relationship("Tag", secondary="recipetags", back_populates="recipes")

class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    recipes = relationship("Recipe", secondary="recipe_ingredients", back_populates="ingredients")

    __table_args__ = (
        Index("ix_ingredients_name_lower", func.lower(name), unique=True),
    )

class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    recipe_id = Column(Integer, ForeignKey("recipes.id"), primary_key=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), primary_key=True)
    quantity = Column(Text)

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    recipes = relationship("Recipe", secondary="recipetags", back_populates="tags")

    __table_args__ = (
        Index("ix_tags_name_lower", func.lower(name), unique=True),
    )

class RecipeTag(Base):
    __tablename__ = "recipetags"
    recipe_id = Column(Integer, ForeignKey("recipes.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)