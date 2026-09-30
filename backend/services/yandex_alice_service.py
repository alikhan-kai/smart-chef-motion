import asyncio
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from backend.schemas.yandex_alice import (
    AlicePairingResponse,
    AliceResponseBody,
    AliceVoiceCommand,
    AliceWebhookRequest,
    AliceWebhookResponse,
)

PAIRING_TTL = timedelta(minutes=10)
MAX_TIMER_SECONDS = 24 * 60 * 60


class PairingNotFoundError(Exception):
    pass


@dataclass
class _Connection:
    code: str
    token: str
    expires_at: datetime
    application_id: str | None = None
    expected_timer_seconds: int | None = None
    commands: list[AliceVoiceCommand] = field(default_factory=list)


class YandexAliceService:
    """Small in-memory bridge between an Alice skill and one browser tab.

    The opaque token is known only to the browser. Alice pairs by speaking the
    short-lived six-digit code, after which her application id points at the
    same connection. This MVP intentionally needs one backend worker; a shared
    store should replace these dictionaries before horizontal scaling.
    """

    def __init__(self) -> None:
        self._by_code: dict[str, _Connection] = {}
        self._by_token: dict[str, _Connection] = {}
        self._token_by_application: dict[str, str] = {}
        self._next_command_id = 1
        self._lock = asyncio.Lock()

    async def create_pairing(self) -> AlicePairingResponse:
        async with self._lock:
            self._remove_expired()
            code = self._new_code()
            token = secrets.token_urlsafe(32)
            connection = _Connection(
                code=code,
                token=token,
                expires_at=datetime.now(UTC) + PAIRING_TTL,
            )
            self._by_code[code] = connection
            self._by_token[token] = connection
            return AlicePairingResponse(
                code=code,
                connection_token=token,
                expires_in_seconds=int(PAIRING_TTL.total_seconds()),
            )

    async def commands(
        self, token: str, after: int
    ) -> tuple[list[AliceVoiceCommand], bool]:
        async with self._lock:
            self._remove_expired()
            connection = self._by_token.get(token)
            if connection is None:
                raise PairingNotFoundError
            commands = [
                command for command in connection.commands if command.id > after
            ]
            return commands, connection.application_id is not None

    async def set_expected_timer(self, token: str, seconds: int | None) -> None:
        async with self._lock:
            self._remove_expired()
            connection = self._by_token.get(token)
            if connection is None:
                raise PairingNotFoundError
            connection.expected_timer_seconds = seconds

    async def handle_webhook(self, payload: AliceWebhookRequest) -> AliceWebhookResponse:
        application_id = payload.session.application.application_id
        command = payload.request.command.strip().lower()

        async with self._lock:
            self._remove_expired()
            connection = self._connection_for_application(application_id)

            # Accept a fresh code even when this Station was paired before.
            # This lets the user move Alice to another browser session without
            # waiting for, or administratively deleting, the old connection.
            code = self._extract_pairing_code(command, payload)
            if code is not None:
                new_connection = self._by_code.get(code)
                if new_connection is None:
                    return self._reply(
                        "Код не найден или устарел. "
                        "Создайте новый код "
                        "на экране готовки."
                    )
                if connection is not None:
                    connection.application_id = None
                new_connection.application_id = application_id
                # A paired connection stays valid for the current browser
                # session instead of expiring with the spoken code.
                new_connection.expires_at = datetime.max.replace(tzinfo=UTC)
                self._token_by_application[application_id] = new_connection.token
                return self._reply(
                    "Готово, Smart Chef подключен. Скажите: "
                    "запусти таймер, таймер на пять минут, "
                    "или останови таймер."
                )

            if connection is None:
                if payload.session.new or not command:
                    return self._reply(
                        "Откройте рецепт в Smart Chef, "
                        "нажмите Подключить Алису и назовите "
                        "шестизначный код. Например: код 123456."
                    )
                return self._reply(
                    "Сначала назовите код подключения из Smart Chef."
                )

            action = self._parse_action(command)
            if action is None:
                return self._reply(
                    "Не поняла команду. Скажите: "
                    "запусти таймер, "
                    "таймер на пять минут, или останови таймер."
                )

            action_name, seconds = action
            if (
                action_name == "start"
                and seconds is not None
                and connection.expected_timer_seconds is not None
                and seconds != connection.expected_timer_seconds
            ):
                expected = self._duration_text(connection.expected_timer_seconds)
                return self._reply(
                    f"Для текущего шага нужен таймер на {expected}. "
                    "Назовите правильное время еще раз."
                )

            voice_command = AliceVoiceCommand(
                id=self._next_command_id,
                action=action_name,
                seconds=seconds,
            )
            self._next_command_id += 1
            connection.commands.append(voice_command)
            connection.commands = connection.commands[-50:]

            if action_name == "stop":
                return self._reply("Останавливаю таймер в Smart Chef.")
            if seconds is None:
                return self._reply("Запускаю таймер текущего шага.")
            duration = self._duration_text(seconds)
            return self._reply(f"Запускаю таймер на {duration}.")

    def _new_code(self) -> str:
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            if code not in self._by_code:
                return code
        raise RuntimeError("Could not allocate a pairing code")

    def _remove_expired(self) -> None:
        now = datetime.now(UTC)
        expired = [token for token, item in self._by_token.items() if item.expires_at <= now]
        for token in expired:
            item = self._by_token.pop(token)
            self._by_code.pop(item.code, None)
            if item.application_id is not None:
                self._token_by_application.pop(item.application_id, None)

    def _connection_for_application(self, application_id: str) -> _Connection | None:
        token = self._token_by_application.get(application_id)
        return self._by_token.get(token) if token else None

    @staticmethod
    def _extract_pairing_code(command: str, payload: AliceWebhookRequest) -> str | None:
        match = re.search(r"(?<!\d)(\d{6})(?!\d)", command.replace(" ", ""))
        if match:
            return match.group(1)
        if "код" not in command and "подключ" not in command:
            return None
        for entity in payload.request.nlu.entities:
            if entity.get("type") == "YANDEX.NUMBER":
                value = entity.get("value")
                if isinstance(value, int) and 0 <= value <= 999_999:
                    return f"{value:06d}"
        return None

    @staticmethod
    def _parse_action(command: str) -> tuple[str, int | None] | None:
        stop_words = ("стоп", "останов", "отмен", "выключ")
        if any(word in command for word in stop_words):
            return ("stop", None)
        start_words = (
            "таймер",
            "запуст",
            "постав",
            "включ",
            "продолж",
        )
        if not any(word in command for word in start_words):
            return None

        total = 0.0
        units = (
            (r"(\d+(?:[.,]\d+)?)\s*(?:час|часа|часов|ч)", 3600),
            (r"(\d+(?:[.,]\d+)?)\s*(?:минут|минуты|минуту|мин|м)", 60),
            (r"(\d+(?:[.,]\d+)?)\s*(?:секунд|секунды|секунду|сек)", 1),
        )
        for pattern, multiplier in units:
            match = re.search(pattern, command)
            if match:
                total += float(match.group(1).replace(",", ".")) * multiplier

        if total:
            seconds = round(total)
            if 1 <= seconds <= MAX_TIMER_SECONDS:
                return ("start", seconds)
            return None
        return ("start", None)

    @staticmethod
    def _duration_text(seconds: int) -> str:
        if seconds % 3600 == 0:
            return f"{seconds // 3600} ч."
        if seconds % 60 == 0:
            return f"{seconds // 60} мин."
        return f"{seconds} сек."

    @staticmethod
    def _reply(text: str) -> AliceWebhookResponse:
        return AliceWebhookResponse(response=AliceResponseBody(text=text))
