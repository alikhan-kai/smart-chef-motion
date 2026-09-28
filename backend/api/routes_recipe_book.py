from fastapi import APIRouter, Depends

from backend.api.deps import get_recipe_book_repository, get_user_id
from backend.repositories.recipe_book_repo import RecipeBookRepository
from backend.schemas.chat import RecipeBookEntry
from backend.services import recipe_book_service

router = APIRouter()


@router.get("/recipe-book", response_model=list[RecipeBookEntry])
async def list_recipe_book_endpoint(
    user_id: str = Depends(get_user_id),
    book_repo: RecipeBookRepository = Depends(get_recipe_book_repository),
) -> list[RecipeBookEntry]:
    return await recipe_book_service.list_entries(book_repo, user_id)


@router.get("/recipe-book/{recipe_id}", response_model=RecipeBookEntry)
async def get_recipe_book_entry_endpoint(
    recipe_id: str,
    user_id: str = Depends(get_user_id),
    book_repo: RecipeBookRepository = Depends(get_recipe_book_repository),
) -> RecipeBookEntry:
    return await recipe_book_service.get_entry(book_repo, user_id, recipe_id)
