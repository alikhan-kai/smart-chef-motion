from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _webhook_payload(
    command: str,
    application_id: str = "alice-device-1",
    *,
    new: bool = False,
    entities: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "version": "1.0",
        "session": {
            "application": {"application_id": application_id},
            "message_id": 0,
            "new": new,
            "skill_id": "test-skill",
        },
        "request": {
            "type": "SimpleUtterance",
            "command": command,
            "original_utterance": command,
            "nlu": {"tokens": command.split(), "entities": entities or []},
        },
    }


@pytest.mark.asyncio
async def test_pair_then_start_custom_timer(client: AsyncClient) -> None:
    pairing_response = await client.post("/integrations/yandex-alice/pairings")
    assert pairing_response.status_code == 200
    pairing = pairing_response.json()

    link_response = await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload(f"код {pairing['code']}"),
    )
    assert link_response.status_code == 200
    assert "подключен" in link_response.json()["response"]["text"]

    timer_response = await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload("поставь таймер на 2 минуты 30 секунд"),
    )
    assert timer_response.status_code == 200

    commands_response = await client.get(
        "/integrations/yandex-alice/commands",
        params={"connection_token": pairing["connection_token"]},
    )
    assert commands_response.status_code == 200
    assert commands_response.json() == {
        "paired": True,
        "commands": [{"id": 1, "action": "start", "seconds": 150}]
    }


@pytest.mark.asyncio
async def test_start_current_timer_and_stop_are_returned_once_with_cursor(
    client: AsyncClient,
) -> None:
    pairing = (await client.post("/integrations/yandex-alice/pairings")).json()
    await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload(
            "подключить код",
            entities=[{"type": "YANDEX.NUMBER", "value": int(pairing["code"])}],
        ),
    )
    await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload("запусти таймер"),
    )
    await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload("останови таймер"),
    )

    params = {"connection_token": pairing["connection_token"]}
    commands = (await client.get("/integrations/yandex-alice/commands", params=params)).json()
    assert commands["paired"] is True
    assert commands["commands"] == [
        {"id": 1, "action": "start", "seconds": None},
        {"id": 2, "action": "stop", "seconds": None},
    ]

    params["after"] = 2
    no_commands = (await client.get("/integrations/yandex-alice/commands", params=params)).json()
    assert no_commands == {"paired": True, "commands": []}


@pytest.mark.asyncio
async def test_unpaired_device_gets_pairing_instructions(client: AsyncClient) -> None:
    response = await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload("", new=True),
    )
    assert response.status_code == 200
    assert "шестизначный код" in response.json()["response"]["text"]


@pytest.mark.asyncio
async def test_unknown_connection_token_is_not_accepted(client: AsyncClient) -> None:
    response = await client.get(
        "/integrations/yandex-alice/commands",
        params={"connection_token": "x" * 32},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_wrong_duration_is_rejected_for_recipe_step(client: AsyncClient) -> None:
    pairing = (await client.post("/integrations/yandex-alice/pairings")).json()
    expected_response = await client.post(
        "/integrations/yandex-alice/expected-timer",
        json={
            "connection_token": pairing["connection_token"],
            "seconds": 20 * 60,
        },
    )
    assert expected_response.status_code == 204
    await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload(f"код {pairing['code']}"),
    )

    wrong_response = await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload("поставь таймер на 10 минут"),
    )
    assert wrong_response.status_code == 200
    assert "20 мин" in wrong_response.json()["response"]["text"]

    commands = await client.get(
        "/integrations/yandex-alice/commands",
        params={"connection_token": pairing["connection_token"]},
    )
    assert commands.json() == {"paired": True, "commands": []}


@pytest.mark.asyncio
async def test_custom_duration_is_allowed_when_step_has_no_timer(
    client: AsyncClient,
) -> None:
    pairing = (await client.post("/integrations/yandex-alice/pairings")).json()
    await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload(f"код {pairing['code']}"),
    )
    await client.post(
        "/integrations/yandex-alice/webhook",
        json=_webhook_payload("таймер на 45 секунд"),
    )

    commands = await client.get(
        "/integrations/yandex-alice/commands",
        params={"connection_token": pairing["connection_token"]},
    )
    assert commands.json()["commands"][0]["seconds"] == 45
