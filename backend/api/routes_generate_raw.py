from fastapi import APIRouter

from backend.schemas.requests import RecipeRequest
from llm.recipe_generator import generate_raw_recipe
from llm.schemas import RawRecipe

router = APIRouter()


@router.post("/recipes/generate-raw", response_model=RawRecipe)
async def generate_raw_endpoint(request: RecipeRequest) -> RawRecipe:
    # Model-reported errors -> 422, post-retry validation failures -> 502;
    # see the exception handlers registered in backend/main.py.
    return await generate_raw_recipe(request.prompt, request.allergies, request.preferred_units)
