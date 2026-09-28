from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes_chats import router as chats_router
from backend.api.routes_compose import router as compose_router
from backend.api.routes_create import router as create_router
from backend.api.routes_generate_raw import router as generate_raw_router
from backend.api.routes_recipe_book import router as recipe_book_router
from backend.repositories.chat_repo import InMemoryChatRepository
from backend.repositories.recipe_book_repo import InMemoryRecipeBookRepository
from backend.services.chat_service import (
    ChatNotFoundError,
    InvalidStateError,
    RevisionFailedError,
    VersionNotFoundError,
)
from backend.services.recipe_book_service import RecipeNotFoundError
from backend.services.recipe_composer import CompositionError
from llm.errors import (
    ModelReportedError,
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    ValidationFailedError,
)

def create_app() -> FastAPI:
    app = FastAPI(title="Smart Chef")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory, process-only state (see backend/repositories/*.py): no
    # Supabase/persistence yet, per AGENTS.md. One instance per app - each
    # test's create_app() call (see backend/tests/test_chat_endpoints.py)
    # therefore gets its own isolated store.
    app.state.chat_repository = InMemoryChatRepository()
    app.state.recipe_book_repository = InMemoryRecipeBookRepository()

    app.include_router(create_router)
    app.include_router(generate_raw_router)
    app.include_router(compose_router)
    app.include_router(chats_router)
    app.include_router(recipe_book_router)

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

    @app.exception_handler(RevisionFailedError)
    async def revision_failed_handler(_request: Request, exc: RevisionFailedError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(InvalidStateError)
    async def invalid_state_handler(_request: Request, exc: InvalidStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    return app


app = create_app()
