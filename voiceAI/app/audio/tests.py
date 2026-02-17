import pytest
import asyncio
import numpy as np
from unittest.mock import AsyncMock, patch, MagicMock
from app.audio.consumers import AudioStreamConsumer

@pytest.mark.asyncio
async def test_connect_success(monkeypatch):
    consumer = AudioStreamConsumer()

    consumer.scope = {
        "client": ("127.0.0.1", 12345),
        "user": type("User", (), {"id": 1})()
    }

    consumer.accept = AsyncMock()
    consumer.close = AsyncMock()

    monkeypatch.setattr("app.audio.consumers.rate_limit", lambda **kwargs: None)

    await consumer.connect()

    consumer.accept.assert_called_once()
    assert consumer.user_id == 1
    assert consumer.in_speech is False
    
    
@pytest.mark.asyncio
async def test_connect_unauthorized():
    consumer = AudioStreamConsumer()

    consumer.scope = {
        "client": ("127.0.0.1", 12345),
        "user": type("User", (), {"id": None})()
    }

    consumer.accept = AsyncMock()
    consumer.close = AsyncMock()

    await consumer.connect()

    consumer.close.assert_called_once_with(code=4401)

@pytest.mark.asyncio
async def test_process_buffer_short_audio():
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer.audio_buffer = b"\x00" * 1000  
    consumer.log = AsyncMock()
    consumer.send = AsyncMock()

    await consumer.process_buffer()

    consumer.send.assert_not_called()

@pytest.mark.asyncio
async def test_process_buffer_success():
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer.audio_buffer = b"\x00" * 20000  
    consumer.log = AsyncMock()
    consumer.send = AsyncMock()

    consumer.send_to_grpc = AsyncMock(return_value={"transcript": "hello world"})

    await consumer.process_buffer()

    consumer.send.assert_called_once()

@pytest.mark.asyncio
async def test_send_to_grpc_timeout(monkeypatch):
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer.log = AsyncMock()

    async def mock_wait_for(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr("asyncio.wait_for", mock_wait_for)

    with patch("grpc.aio.insecure_channel") as mock_channel:
        mock_channel.return_value.__aenter__.return_value = MagicMock()

        result = await consumer.send_to_grpc(b"\x00" * 20000)

    assert result["error"] == "gRPC call timed out"
    
    
@pytest.mark.asyncio
async def test_disconnect_cleanup():
    consumer = AudioStreamConsumer()
    consumer.user_id = 1
    consumer.log_task = AsyncMock()
    consumer.listen_task = AsyncMock()

    consumer.vad_frame_buffer = np.array([1, 2, 3], dtype=np.float32)
    consumer.audio_buffer = b"abc"
    consumer.in_speech = True
    consumer.prob_history = [0.1, 0.2]

    await consumer.disconnect(code=1000)

    assert consumer.audio_buffer == b""
    assert consumer.in_speech is False
    assert len(consumer.prob_history) == 0
