import pytest
import json
import base64
from unittest.mock import Mock, patch, AsyncMock

from app.workers.task_email import send_welcome_email
from app.workers.task_audio import handle_message
from app.workers.task_tts import handle_tts_message


class FakeEmailMessage:
    def __init__(self, body):
        self.body = body


class FakeAudioMessage:
    def __init__(self, body):
        self.body = body
        self.ack = AsyncMock()
        self.nack = AsyncMock()


class FakeTTSMessage:
    def __init__(self, body):
        self.body = body
        self.ack = AsyncMock()
        self.nack = AsyncMock()


@patch("app.workers.task_email.send_mail")
def test_handle_email_message_success(mock_send_mail):
    payload = json.dumps(
        {
            "to_email": "test@example.com",
            "subject": "Welcome!",
            "context": {"username": "testuser"},
        }
    ).encode()

    message = FakeEmailMessage(payload)

    send_welcome_email.apply(args=[json.loads(message.body)])

    mock_send_mail.assert_called_once()
    args, kwargs = mock_send_mail.call_args
    assert "Welcome!" in args
    assert "Hello testuser" in args[1]
    assert ["test@example.com"] == args[3]


@pytest.mark.asyncio
@patch("app.workers.task_audio.publish_audio_response", new_callable=AsyncMock)
@patch(
    "app.workers.task_audio.LLMService.query_from_text_async", new_callable=AsyncMock
)
@patch("app.workers.task_audio.get_connection")
@patch("app.workers.task_audio.AudioService.process_audio")
async def test_handle_message_success(
    mock_process_audio, mock_get_connection, mock_query_llm, mock_publish
):
    mock_process_audio.return_value = "Hello world"

    mock_query_llm.return_value = "LLM response text"

    mock_channel = AsyncMock()
    mock_connection = AsyncMock()
    mock_connection.channel = AsyncMock(return_value=mock_channel)
    mock_get_connection.return_value = mock_connection

    payload = {"audio_bytes": base64.b64encode(b"fake audio").decode(), "user_id": 123}
    message = FakeAudioMessage(json.dumps(payload).encode())

    await handle_message(message)

    mock_process_audio.assert_called_once()
    mock_query_llm.assert_called_once_with(text="Hello world")
    mock_publish.assert_called_once_with(user_id=123, response="LLM response text")
    message.ack.assert_called_once()
    mock_connection.channel.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.workers.task_audio.AudioService.process_audio")
@patch("app.workers.task_audio.get_connection", new_callable=AsyncMock)
async def test_handle_message_empty_audio(mock_get_connection, mock_process_audio):
    mock_process_audio.return_value = ""  # empty string

    mock_channel = AsyncMock()

    mock_connection = AsyncMock()
    mock_connection.channel.return_value = mock_channel

    mock_get_connection.return_value = mock_connection

    payload = {"audio_bytes": base64.b64encode(b"fake audio").decode()}
    message = FakeAudioMessage(json.dumps(payload).encode())

    from app.workers.task_audio import handle_message

    await handle_message(message)

    message.ack.assert_called_once()


@pytest.mark.asyncio
@patch("app.workers.task_audio.AudioService.process_audio")
@patch(
    "app.workers.task_audio.LLMService.query_from_text_async", new_callable=AsyncMock
)
@patch("app.workers.task_audio.get_connection", new_callable=AsyncMock)
async def test_handle_message_exception(
    mock_get_connection, mock_query_llm, mock_process_audio
):
    mock_process_audio.side_effect = Exception("Audio processing failed")

    payload = {"audio_bytes": base64.b64encode(b"fake audio").decode()}
    message = FakeAudioMessage(json.dumps(payload).encode())

    from app.workers.task_audio import handle_message

    with pytest.raises(Exception):
        await handle_message(message)

    assert message.nack.call_args.kwargs["requeue"] is False
    message.ack.assert_not_called()


@pytest.mark.asyncio
@patch("app.workers.task_tts.TTSService.synthesize", new_callable=Mock)
@patch("app.workers.task_tts.publish_audio_response", new_callable=AsyncMock)
async def test_handle_tts_message_success(mock_publish, mock_synthesize):
    fake_audio_bytes = b"fake audio data"
    mock_synthesize.return_value = fake_audio_bytes
    payload = {"text": "Hello world", "user_id": "123"}
    message = FakeTTSMessage(json.dumps(payload).encode())

    await handle_tts_message(message)

    mock_synthesize.assert_called_once_with("Hello world")
    audio_b64 = base64.b64encode(fake_audio_bytes).decode("utf-8")
    mock_publish.assert_awaited_once_with(user_id="123", audio_bytes=audio_b64)
    message.ack.assert_awaited_once()
    message.nack.assert_not_called()


@pytest.mark.asyncio
@patch("app.workers.task_tts.TTSService.synthesize", new_callable=Mock)
@patch("app.workers.task_tts.publish_audio_response", new_callable=AsyncMock)
async def test_handle_tts_message_synthesize_exception(mock_publish, mock_synthesize):
    mock_synthesize.side_effect = Exception("Synthesis failed")
    payload = {"text": "Hello world", "user_id": "123"}
    message = FakeTTSMessage(json.dumps(payload).encode())

    with pytest.raises(Exception):
        await handle_tts_message(message)

    mock_synthesize.assert_called_once_with("Hello world")
    mock_publish.assert_not_called()
    message.nack.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_called()
