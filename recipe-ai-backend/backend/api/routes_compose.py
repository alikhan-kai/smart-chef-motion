from fastapi import APIRouter

from backend.schemas.recipe import Recipe
from backend.services.recipe_composer import compose_recipe
from llm.schemas import RawRecipe

router = APIRouter()


@router.post("/recipes/compose", response_model=Recipe)
async def compose_recipe_endpoint(raw_recipe: RawRecipe) -> Recipe:
    return await compose_recipe(raw_recipe)
