import pytest
import json
import base64
from unittest.mock import patch, AsyncMock
from app.workers.task_email import handle_email_message
from app.workers.task_audio import handle_message
import pytest
import json
from unittest.mock import patch, AsyncMock
from app.workers.task_email import handle_email_message

class FakeEmailMessage:
    def __init__(self, body):
        self.body = body

    def process(self):
        class DummyCM:
            async def __aenter__(self_inner):
                return self_inner
            async def __aexit__(self_inner, exc_type, exc_val, exc_tb):
                pass
        return DummyCM()


class FakeAudioMessage:
    def __init__(self, body):
        self.body = body
        self.ack = AsyncMock()
        self.nack = AsyncMock()


@pytest.mark.asyncio
@patch("app.workers.task_email.send_mail")
async def test_handle_email_message_success(mock_send_mail):
    payload = json.dumps({
        "to_email": "test@example.com",
        "subject": "Welcome!",
        "context": {"username": "testuser"}
    }).encode()

    message = FakeEmailMessage(payload)
    await handle_email_message(message)

    mock_send_mail.assert_called_once()
    args, _ = mock_send_mail.call_args
    assert "Welcome!" in args
    assert "Hello testuser" in args[1]
    assert ["test@example.com"] == args[3]

@pytest.mark.asyncio
@patch("app.workers.task_audio.AudioService.process_audio")  # sync function
@patch("app.workers.task_audio.LLMService.query_from_text_async", new_callable=AsyncMock)
@patch("app.workers.task_audio.publish_audio_response", new_callable=AsyncMock)
async def test_handle_message_success(mock_publish, mock_llm, mock_audio):
    mock_audio.return_value = "Hello world"  # sync string
    mock_llm.return_value = "LLM response text"

    payload = {"audio_bytes": base64.b64encode(b"fake audio").decode(), "user_id": 123}
    message = FakeAudioMessage(json.dumps(payload).encode())

    await handle_message(message)

    mock_audio.assert_called_once()
    mock_llm.assert_called_once_with(text="Hello world")
    mock_publish.assert_called_once_with(user_id=123, response="LLM response text")
    message.ack.assert_called_once()


@pytest.mark.asyncio
@patch("app.workers.task_audio.AudioService.process_audio")
async def test_handle_message_empty_audio(mock_audio):
    mock_audio.return_value = ""  # empty string

    payload = {"audio_bytes": base64.b64encode(b"fake audio").decode()}
    message = FakeAudioMessage(json.dumps(payload).encode())

    from app.workers.task_audio import handle_message
    await handle_message(message)

    message.ack.assert_called_once()


@pytest.mark.asyncio
@patch("app.workers.task_audio.AudioService.process_audio")
@patch("app.workers.task_audio.LLMService.query_from_text_async", new_callable=AsyncMock)
async def test_handle_message_exception(mock_llm, mock_audio):
    mock_audio.side_effect = Exception("Audio processing failed")

    payload = {"audio_bytes": base64.b64encode(b"fake audio").decode()}
    message = FakeAudioMessage(json.dumps(payload).encode())

    from app.workers.task_audio import handle_message
    import pytest

    with pytest.raises(Exception):
        await handle_message(message)

    message.nack.assert_called_once_with(requeue=False)
    message.ack.assert_not_called()
