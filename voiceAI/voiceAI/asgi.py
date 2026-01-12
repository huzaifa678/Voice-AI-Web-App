"""
ASGI config for voiceAI project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from app.audio.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voiceAI.settings')

import django
django.setup()

from app.middleware.jwt_middleware import JWTAuthMiddleware

django_asgi_app = get_asgi_application()

class LifespanApp:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()

                if message["type"] == "lifespan.startup":
                    print("ASGI startup")
                    await send({"type": "lifespan.startup.complete"})

                elif message["type"] == "lifespan.shutdown":
                    print("ASGI shutdown: cleaning up...")
                    await self.shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        else:
            await self.app(scope, receive, send)

    async def shutdown(self):
        from app.common.rabbit_mq import close_connection
        close_connection()

application = LifespanApp(
    ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        ),
    })
)
