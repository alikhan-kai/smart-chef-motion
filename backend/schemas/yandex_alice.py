from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AliceApplication(BaseModel):
    application_id: str = Field(min_length=1, max_length=256)


class AliceSession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    application: AliceApplication
    message_id: int = 0
    new: bool = False
    skill_id: str | None = None


class AliceNlu(BaseModel):
    model_config = ConfigDict(extra="allow")

    tokens: list[str] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)


class AliceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    command: str = ""
    original_utterance: str = ""
    nlu: AliceNlu = Field(default_factory=AliceNlu)
    type: str = "SimpleUtterance"


class AliceWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request: AliceRequest
    session: AliceSession
    version: str = "1.0"


class AliceResponseBody(BaseModel):
    text: str
    tts: str | None = None
    end_session: bool = False


class AliceWebhookResponse(BaseModel):
    response: AliceResponseBody
    version: str = "1.0"


class AlicePairingResponse(BaseModel):
    code: str
    connection_token: str
    expires_in_seconds: int


class AliceExpectedTimerRequest(BaseModel):
    connection_token: str = Field(min_length=32, max_length=128)
    seconds: int | None = Field(default=None, ge=1, le=24 * 60 * 60)


class AliceVoiceCommand(BaseModel):
    id: int
    action: Literal["start", "stop"]
    seconds: int | None = None


class AliceCommandsResponse(BaseModel):
    paired: bool
    commands: list[AliceVoiceCommand]
