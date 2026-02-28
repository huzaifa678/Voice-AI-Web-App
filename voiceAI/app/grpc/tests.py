import grpc
import pytest
from unittest.mock import AsyncMock, patch
from app.grpc.service import AudioServicer
from app.grpc import audio_pb2
from asgiref.sync import sync_to_async

SAMPLE_AUDIO_BYTES = b"\x01\x02" * 100  # small dummy audio
SAMPLE_USER_ID = 1


class DummyContext:
    def __init__(self):
        self._metadata = [("user_id", SAMPLE_USER_ID)]
        self.code = None
        self.details = None

    def invocation_metadata(self):
        return self._metadata

    def set_code(self, code):
        self.code = code

    def set_details(self, details):
        self.details = details


class DummyRequest:
    def __init__(self, pcm):
        self.pcm = pcm


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_stream_transcribe_success():
    from app.models import User

    test_user, _ = await sync_to_async(User.objects.get_or_create)(
        id=1, defaults={"username": "test-user", "email": "test@example.com"}
    )

    servicer = AudioServicer()

    with patch(
        "app.grpc.service.VADService.is_speech", return_value=True
    ) as mock_vad, patch(
        "app.grpc.service.AudioService.transcribe_pcm",
        new_callable=AsyncMock,
        return_value="hello world",
    ) as mock_transcribe, patch(
        "app.grpc.service.publish_audio_task", new_callable=AsyncMock
    ) as mock_publish, patch(
        "app.grpc.service.rate_limit", return_value=None
    ):

        async def request_gen():
            yield DummyRequest(SAMPLE_AUDIO_BYTES)

        context = DummyContext()
        response = await servicer.StreamTranscribe(request_gen(), context)

        assert isinstance(response, audio_pb2.TranscriptionResponse)
        assert response.transcript == "hello world"
        assert mock_vad.call_count >= 1
        mock_transcribe.assert_called_once_with(SAMPLE_AUDIO_BYTES, 16000)
        mock_publish.assert_awaited_once()
        assert context.code is None
        assert context.details is None


@pytest.mark.asyncio
async def test_stream_transcribe_no_audio():
    servicer = AudioServicer()

    async def empty_request_gen():
        if False:
            yield

    context = DummyContext()
    response = await servicer.StreamTranscribe(empty_request_gen(), context)

    assert isinstance(response, audio_pb2.TranscriptionResponse)
    assert response.transcript == ""
    assert context.code == grpc.StatusCode.INVALID_ARGUMENT
    assert context.details == "No audio received"
