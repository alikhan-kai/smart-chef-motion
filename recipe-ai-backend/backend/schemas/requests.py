from pydantic import BaseModel


class RecipeRequest(BaseModel):
    """Request body shared by POST /recipes/create and POST /recipes/generate-raw."""

    prompt: str
    allergies: str | None = None
    preferred_units: str | None = None
