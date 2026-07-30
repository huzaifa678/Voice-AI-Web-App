import os
import django
import asyncio
import grpc
from app.grpc import service_pb2_grpc
from app.common.logger import get_logger
from app.common.telemetry import setup_telemetry

logger = get_logger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")
setup_telemetry("voice-ai-grpc")
django.setup()

from app.grpc.service import AudioServicer


async def serve():
    server = grpc.aio.server()
    service_pb2_grpc.add_AudioServiceServicer_to_server(AudioServicer(), server)
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    logger.info("gRPC server listening on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
