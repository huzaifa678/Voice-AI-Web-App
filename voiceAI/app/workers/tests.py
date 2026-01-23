import base64
from unittest.mock import patch, AsyncMock

from app.workers.task_email import handle_email_message
from app.workers.task_audio import handle_audio_task


@patch("app.workers.task_email.asyncio.to_thread")
def test_handle_email_message_success(mock_to_thread):
    payload = {
        "to_email": "test@example.com",
        "subject": "Welcome!",
        "context": {"username": "testuser"},
    }

    handle_email_message(payload)

    mock_to_thread.assert_called_once()

    args, _ = mock_to_thread.call_args
    assert args[0].__name__ == "send_mail"
    assert "Welcome!" == args[1]
    assert "testuser" in args[2]
    assert ["test@example.com"] == args[4]


def test_handle_email_message_no_recipient():
    handle_email_message({})  


@patch("app.workers.task_audio.publish_audio_response", new_callable=AsyncMock)
@patch("app.workers.task_audio.LLMService.query_from_text_async", new_callable=AsyncMock)
@patch("app.workers.task_audio.AudioService.process_audio")
def test_handle_audio_task_success(
    mock_audio,
    mock_llm,
    mock_publish,
):
    mock_audio.return_value = "Hello world"
    mock_llm.return_value = "LLM response text"

    payload = {
        "user_id": 123,
        "audio_bytes": base64.b64encode(b"fake audio").decode(),
    }

    handle_audio_task(payload)

    mock_audio.assert_called_once()
    mock_llm.assert_called_once_with(text="Hello world")
    mock_publish.assert_called_once_with(
        user_id=123,
        response="LLM response text",
    )


@patch("app.workers.task_audio.AudioService.process_audio")
def test_handle_audio_task_empty_audio(mock_audio):
    mock_audio.return_value = ""

    payload = {
        "audio_bytes": base64.b64encode(b"fake audio").decode()
    }

    handle_audio_task(payload)

    mock_audio.assert_called_once()
