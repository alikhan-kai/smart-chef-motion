from fastapi import APIRouter

from backend.schemas.recipe import Recipe
from backend.schemas.requests import RecipeRequest
from backend.services.pipeline import create_recipe

router = APIRouter()


@router.post("/recipes/create", response_model=Recipe)
async def create_recipe_endpoint(request: RecipeRequest) -> Recipe:
    return await create_recipe(
        request.prompt, request.allergies, request.preferred_units, language=request.language
    )
