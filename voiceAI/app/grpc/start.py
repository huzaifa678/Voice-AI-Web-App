import os
import django
import asyncio
import grpc
from app.grpc import service_pb2_grpc
from app.grpc.service import AudioServicer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")
django.setup()


async def serve():
    server = grpc.aio.server()
    service_pb2_grpc.add_AudioServiceServicer_to_server(AudioServicer(), server)
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    print(f"gRPC server listening on {listen_addr}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
