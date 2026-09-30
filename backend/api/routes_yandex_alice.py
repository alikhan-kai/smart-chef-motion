from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.config import get_backend_settings
from backend.schemas.yandex_alice import (
    AliceCommandsResponse,
    AliceExpectedTimerRequest,
    AlicePairingResponse,
    AliceWebhookRequest,
    AliceWebhookResponse,
)
from backend.services.yandex_alice_service import PairingNotFoundError, YandexAliceService

router = APIRouter(prefix="/integrations/yandex-alice", tags=["yandex-alice"])


def get_alice_service(request: Request) -> YandexAliceService:
    service: YandexAliceService = request.app.state.yandex_alice_service
    return service


@router.post("/pairings", response_model=AlicePairingResponse)
async def create_pairing(
    service: YandexAliceService = Depends(get_alice_service),
) -> AlicePairingResponse:
    return await service.create_pairing()


@router.get("/commands", response_model=AliceCommandsResponse)
async def get_commands(
    connection_token: str = Query(min_length=32, max_length=128),
    after: int = Query(default=0, ge=0),
    service: YandexAliceService = Depends(get_alice_service),
) -> AliceCommandsResponse:
    try:
        commands, paired = await service.commands(connection_token, after)
    except PairingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Alice connection not found") from exc
    return AliceCommandsResponse(paired=paired, commands=commands)


@router.post("/expected-timer", status_code=204)
async def set_expected_timer(
    payload: AliceExpectedTimerRequest,
    service: YandexAliceService = Depends(get_alice_service),
) -> None:
    try:
        await service.set_expected_timer(payload.connection_token, payload.seconds)
    except PairingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Alice connection not found") from exc


@router.post("/webhook", response_model=AliceWebhookResponse)
async def alice_webhook(
    payload: AliceWebhookRequest,
    service: YandexAliceService = Depends(get_alice_service),
) -> AliceWebhookResponse:
    expected_skill_id = get_backend_settings().yandex_alice_skill_id
    if expected_skill_id and payload.session.skill_id != expected_skill_id:
        raise HTTPException(status_code=403, detail="Unexpected Alice skill id")
    return await service.handle_webhook(payload)
