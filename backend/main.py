from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import create_client

from backend.api.routes_chats import router as chats_router
from backend.api.routes_compose import router as compose_router
from backend.api.routes_create import router as create_router
from backend.api.routes_generate_raw import router as generate_raw_router
from backend.api.routes_recipe_book import router as recipe_book_router
from backend.api.routes_recipe_magazine import router as recipe_magazine_router
from backend.config import get_backend_settings
from backend.repositories.chat_repo import InMemoryChatRepository
from backend.repositories.recipe_book_repo import (
    InMemoryRecipeBookRepository,
    SupabaseRecipeBookRepository,
)
from backend.repositories.recipe_magazine_repo import (
    InMemoryRecipeMagazineRepository,
    SupabaseRecipeMagazineRepository,
)
from backend.services.chat_service import (
    ChatNotFoundError,
    InvalidStateError,
    RevisionFailedError,
    VersionNotFoundError,
)
from backend.services.recipe_book_service import RecipeNotFoundError
from backend.services.recipe_composer import CompositionError
from backend.services.recipe_magazine_service import MagazineNotFoundError, RecipeEntryNotFoundError
from llm.errors import (
    ModelReportedError,
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    ValidationFailedError,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Smart Chef")

    # The frontend (index.html served statically, e.g. `npx serve -l 8080`)
    # calls this API cross-origin from the browser - without this, every
    # fetch() from js/*.js fails silently with a CORS error, not a 4xx/5xx
    # the frontend can report cleanly.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory, process-only state (see backend/repositories/*.py) - unless
    # SUPABASE_URL/SUPABASE_SERVICE_KEY are set (see backend/config.py), in
    # which case the recipe book and recipe magazine persist to Supabase
    # instead. The test suite sets neither, so each test's create_app() call
    # (see backend/tests/test_chat_endpoints.py) still gets its own isolated
    # in-memory store.
    app.state.chat_repository = InMemoryChatRepository()

    settings = get_backend_settings()
    if settings.supabase_url and settings.supabase_service_key:
        supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)
        app.state.recipe_book_repository = SupabaseRecipeBookRepository(supabase_client)
        app.state.recipe_magazine_repository = SupabaseRecipeMagazineRepository(supabase_client)
    else:
        app.state.recipe_book_repository = InMemoryRecipeBookRepository()
        app.state.recipe_magazine_repository = InMemoryRecipeMagazineRepository()

    app.include_router(create_router)
    app.include_router(generate_raw_router)
    app.include_router(compose_router)
    app.include_router(chats_router)
    app.include_router(recipe_book_router)
    app.include_router(recipe_magazine_router)

    @app.exception_handler(ModelReportedError)
    async def model_reported_error_handler(
        _request: Request, exc: ModelReportedError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.message})

    @app.exception_handler(CompositionError)
    async def composition_error_handler(_request: Request, exc: CompositionError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ValidationFailedError)
    async def validation_failed_handler(
        _request: Request, exc: ValidationFailedError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(UpstreamError)
    async def upstream_error_handler(_request: Request, exc: UpstreamError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(UpstreamTimeoutError)
    async def upstream_timeout_handler(
        _request: Request, exc: UpstreamTimeoutError
    ) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    @app.exception_handler(UpstreamRateLimitError)
    async def upstream_rate_limit_handler(
        _request: Request, exc: UpstreamRateLimitError
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(ChatNotFoundError)
    async def chat_not_found_handler(_request: Request, exc: ChatNotFoundError) -> JSONResponse:
        # Also returned when the chat belongs to another user - existence is
        # never revealed to a non-owner. See docs/chat_contract.md.
        return JSONResponse(status_code=404, content={"detail": "Chat not found"})

    @app.exception_handler(VersionNotFoundError)
    async def version_not_found_handler(
        _request: Request, exc: VersionNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Recipe version not found"})

    @app.exception_handler(RecipeNotFoundError)
    async def recipe_not_found_handler(_request: Request, exc: RecipeNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Recipe not found"})

    @app.exception_handler(MagazineNotFoundError)
    async def magazine_not_found_handler(
        _request: Request, exc: MagazineNotFoundError
    ) -> JSONResponse:
        # Also returned when the magazine is private and belongs to someone
        # else - existence is never revealed to a non-owner, same rule as
        # ChatNotFoundError above.
        return JSONResponse(status_code=404, content={"detail": "Recipe magazine not found"})

    @app.exception_handler(RecipeEntryNotFoundError)
    async def recipe_entry_not_found_handler(
        _request: Request, exc: RecipeEntryNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": f"Recipe book entry not found: {exc}"}
        )

    @app.exception_handler(RevisionFailedError)
    async def revision_failed_handler(_request: Request, exc: RevisionFailedError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(InvalidStateError)
    async def invalid_state_handler(_request: Request, exc: InvalidStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    return app


app = create_app()
