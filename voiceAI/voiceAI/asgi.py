"""
ASGI config for voiceAI project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import grpc
from app.audio.routing import websocket_urlpatterns
from app.grpc.service import AudioServicer
from app.grpc import service_pb2_grpc

from app.middleware.jwt_middleware import JWTAuthMiddleware
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")

django.setup()

django_asgi_app = get_asgi_application()


class LifespanApp:
    def __init__(self, app):
        self.app = app
        self.grpc_server = None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()

                if message["type"] == "lifespan.startup":
                    print("ASGI startup")

                    await self.start_grpc_server()

                    await send({"type": "lifespan.startup.complete"})

                elif message["type"] == "lifespan.shutdown":
                    print("ASGI shutdown: cleaning up...")
                    await self.shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        else:
            await self.app(scope, receive, send)

    async def start_grpc_server(self):
        self.grpc_server = grpc.aio.server()

        service_pb2_grpc.add_AudioServiceServicer_to_server(
            AudioServicer(), self.grpc_server
        )

        self.grpc_server.add_insecure_port("[::]:50051")

        await self.grpc_server.start()
        print("gRPC server started on port 50051")

    async def shutdown(self):
        from app.common.rabbit_mq import close_connection

        if self.grpc_server:
            print("Stopping gRPC server...")
            await self.grpc_server.stop(grace=None)

        close_connection()


application = LifespanApp(
    ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
        }
    )
)
