from sqlalchemy import Column, Integer, Text, ForeignKey, TIMESTAMP, Index, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(TIMESTAMP, server_default=func.now())


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(Text, nullable=False, unique=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_seen_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    user = relationship("User")


class RecipeAuthor(Base):
    __tablename__ = "recipe_authors"
    recipe_id = Column(Integer, ForeignKey("recipes.id"), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)


class CommentAuthor(Base):
    __tablename__ = "comment_authors"
    comment_id = Column(Integer, ForeignKey("recipe_comments.id"), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)


class RecipeFavorite(Base):
    __tablename__ = "recipe_favorites"
    recipe_id = Column(Integer, ForeignKey("recipes.id"), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class OnlineDevicePresence(Base):
    __tablename__ = "online_device_presence"
    device_id = Column(Text, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    last_seen_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

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
    comments = relationship("RecipeComment", back_populates="recipe", cascade="all, delete-orphan")

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


class RecipeComment(Base):
    __tablename__ = "recipe_comments"
    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    recipe = relationship("Recipe", back_populates="comments")
