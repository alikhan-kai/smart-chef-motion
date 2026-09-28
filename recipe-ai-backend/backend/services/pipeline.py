from backend.schemas.recipe import Recipe
from backend.services.recipe_composer import compose_recipe
from llm.recipe_generator import generate_raw_recipe


async def create_recipe(
    prompt: str,
    allergies: str | None = None,
    preferred_units: str | None = None,
) -> Recipe:
    """Full pipeline: generate_raw_recipe() -> compose_recipe(), as plain function calls."""
    raw_recipe = await generate_raw_recipe(prompt, allergies, preferred_units)
    return await compose_recipe(raw_recipe)
