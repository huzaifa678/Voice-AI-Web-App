from django.urls import re_path
from .consumers import AudioStreamConsumer  

websocket_urlpatterns = [
    re_path(r"ws/audio/$", AudioStreamConsumer.as_asgi()),
]
