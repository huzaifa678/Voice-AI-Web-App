from django.urls import path
from .views import AudioTranscribeView

urlpatterns = [
    path("transcribe/", AudioTranscribeView.as_view(), name="audio-transcribe"),
]
