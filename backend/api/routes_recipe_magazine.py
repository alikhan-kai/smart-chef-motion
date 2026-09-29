from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from backend.api.deps import get_recipe_magazine_repository, get_user_id
from backend.repositories.recipe_magazine_repo import MagazineSort, RecipeMagazineRepository
from backend.schemas.recipe_magazine import (
    RecipeMagazineCreateRequest,
    RecipeMagazineDetail,
    RecipeMagazineSummary,
    RecipeMagazineUpdateRequest,
    SaveMarketItemRequest,
    SetMagazineItemsRequest,
)
from backend.services import recipe_magazine_service

router = APIRouter()


@router.post("/recipe-magazines", response_model=RecipeMagazineSummary, status_code=201)
async def create_magazine_endpoint(
    body: RecipeMagazineCreateRequest,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> RecipeMagazineSummary:
    return await recipe_magazine_service.create_magazine(
        magazine_repo, user_id, body.title, body.description
    )


@router.get("/recipe-magazines", response_model=list[RecipeMagazineSummary])
async def list_my_magazines_endpoint(
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> list[RecipeMagazineSummary]:
    return await recipe_magazine_service.list_my_magazines(magazine_repo, user_id)


@router.get("/recipe-magazines/market", response_model=list[RecipeMagazineSummary])
async def market_magazines_endpoint(
    q: str | None = Query(default=None),
    sort: MagazineSort = Query(default="popular"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> list[RecipeMagazineSummary]:
    return await recipe_magazine_service.list_market(magazine_repo, q, sort, limit, offset)


@router.patch("/recipe-magazines/{magazine_id}", response_model=RecipeMagazineSummary)
async def update_magazine_endpoint(
    magazine_id: str,
    body: RecipeMagazineUpdateRequest,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> RecipeMagazineSummary:
    return await recipe_magazine_service.update_magazine(
        magazine_repo, user_id, magazine_id, body.title, body.description
    )


@router.put("/recipe-magazines/{magazine_id}/items", response_model=RecipeMagazineSummary)
async def set_magazine_items_endpoint(
    magazine_id: str,
    body: SetMagazineItemsRequest,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> RecipeMagazineSummary:
    return await recipe_magazine_service.set_magazine_items(
        magazine_repo, user_id, magazine_id, body.recipes
    )


@router.put("/recipe-magazines/{magazine_id}/cover", status_code=204)
async def set_magazine_cover_endpoint(
    magazine_id: str,
    cover: UploadFile = File(...),
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> None:
    content = await cover.read()
    content_type = cover.content_type or "application/octet-stream"
    await recipe_magazine_service.set_magazine_cover(
        magazine_repo, user_id, magazine_id, content, content_type
    )


@router.get("/recipe-magazines/{magazine_id}/cover")
async def get_magazine_cover_endpoint(
    magazine_id: str,
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> Response:
    content, content_type = await recipe_magazine_service.get_magazine_cover(
        magazine_repo, magazine_id
    )
    return Response(content=content, media_type=content_type)


@router.post("/recipe-magazines/{magazine_id}/share", response_model=RecipeMagazineSummary)
async def share_magazine_endpoint(
    magazine_id: str,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> RecipeMagazineSummary:
    return await recipe_magazine_service.share_magazine(magazine_repo, user_id, magazine_id)


@router.post("/recipe-magazines/{magazine_id}/unpublish", response_model=RecipeMagazineSummary)
async def unpublish_magazine_endpoint(
    magazine_id: str,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> RecipeMagazineSummary:
    return await recipe_magazine_service.unpublish_magazine(magazine_repo, user_id, magazine_id)


@router.delete("/recipe-magazines/{magazine_id}", status_code=204)
async def delete_magazine_endpoint(
    magazine_id: str,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> None:
    await recipe_magazine_service.delete_magazine(magazine_repo, user_id, magazine_id)


@router.post(
    "/recipe-magazines/{magazine_id}/items/{item_id}/save",
    response_model=RecipeMagazineSummary,
)
async def save_market_item_endpoint(
    magazine_id: str,
    item_id: str,
    body: SaveMarketItemRequest,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> RecipeMagazineSummary:
    return await recipe_magazine_service.save_market_item_to_my_magazine(
        magazine_repo, user_id, magazine_id, item_id, body.target_magazine_id
    )


@router.get("/recipe-magazines/{magazine_id}", response_model=RecipeMagazineDetail)
async def get_magazine_detail_endpoint(
    magazine_id: str,
    user_id: str = Depends(get_user_id),
    magazine_repo: RecipeMagazineRepository = Depends(get_recipe_magazine_repository),
) -> RecipeMagazineDetail:
    return await recipe_magazine_service.get_magazine_detail(magazine_repo, user_id, magazine_id)
