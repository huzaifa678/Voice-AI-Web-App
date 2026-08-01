import pytest
import asyncio
from collections import deque
from unittest.mock import AsyncMock, patch, MagicMock
from app.audio.consumers import AudioStreamConsumer
from app.audio.session import VoiceSession


@pytest.mark.asyncio
async def test_connect_success(monkeypatch):
    consumer = AudioStreamConsumer()

    consumer.scope = {
        "client": ("127.0.0.1", 12345),
        "user": type("User", (), {"id": 1})(),
    }

    consumer.accept = AsyncMock()
    consumer.close = AsyncMock()

    monkeypatch.setattr("app.audio.consumers.rate_limit", lambda **kwargs: None)

    with patch("grpc.aio.insecure_channel") as mock_channel:
        mock_channel.return_value = MagicMock()
        await consumer.connect()

    consumer.accept.assert_called_once()
    assert consumer.user_id == 1
    assert consumer.session.in_speech is False
    assert isinstance(consumer.vad_frame_buffer, deque)
    assert isinstance(consumer.session.audio_buffer, bytearray)


@pytest.mark.asyncio
async def test_connect_unauthorized():
    consumer = AudioStreamConsumer()

    consumer.scope = {
        "client": ("127.0.0.1", 12345),
        "user": type("User", (), {"id": None})(),
    }

    consumer.accept = AsyncMock()
    consumer.close = AsyncMock()

    await consumer.connect()

    consumer.close.assert_called_once_with(code=4401)


@pytest.mark.asyncio
async def test_process_buffer_short_audio():
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer.session = VoiceSession(user_id="1")
    consumer.session.audio_buffer = bytearray(b"\x00" * 1000)
    consumer.log = AsyncMock()
    consumer.send = AsyncMock()

    await consumer.process_buffer()

    consumer.send.assert_not_called()


@pytest.mark.asyncio
async def test_process_buffer_success():
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer.session = VoiceSession(user_id="1")
    consumer.session.audio_buffer = bytearray(b"\x00" * 20000)
    consumer._grpc_host = "localhost:50051"
    consumer.log = AsyncMock()
    consumer.send = AsyncMock()
    consumer.grpc_stub = MagicMock()

    mock_response = MagicMock()
    mock_response.transcript = "hello world"

    async def async_responses():
        yield mock_response

    consumer.grpc_stub.StreamTranscribe = MagicMock(return_value=async_responses())

    await consumer.process_buffer()

    consumer.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_to_grpc_timeout(monkeypatch):
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer._grpc_host = "localhost:50051"
    consumer.log = AsyncMock()
    consumer.grpc_stub = MagicMock()

    async def mock_wait_for(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr("asyncio.wait_for", mock_wait_for)

    result = await consumer.send_to_grpc(b"\x00" * 20000)

    assert result["error"] == "gRPC call timed out"


@pytest.mark.asyncio
async def test_disconnect_cleanup():
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer.session = VoiceSession(user_id="1")
    consumer.log_task = MagicMock()
    consumer.listen_task = MagicMock()
    consumer.grpc_channel = AsyncMock()
    grpc_channel = consumer.grpc_channel

    consumer.vad_frame_buffer = deque([1, 2, 3])
    consumer.session.audio_buffer = bytearray(b"abc")
    consumer.session.in_speech = True
    consumer.session.prob_history = [0.1, 0.2]

    await consumer.disconnect(code=1000)

    assert consumer.session.audio_buffer == bytearray()
    assert consumer.session.in_speech is False
    assert len(consumer.session.prob_history) == 0
    assert len(consumer.vad_frame_buffer) == 0
    grpc_channel.close.assert_called_once()
