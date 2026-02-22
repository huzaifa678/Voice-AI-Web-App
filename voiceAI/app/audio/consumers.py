import asyncio
import os
import time
import json
import aio_pika
import grpc
import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer

from app.audio.services import VADService
from app.common.rate_limit import rate_limit
from app.common.rabbit_mq import get_connection
from app.grpc import audio_pb2, service_pb2_grpc

TARGET_SR = 16000

FRAME_SAMPLES = 512
HOP_SAMPLES   = 512   

SPEECH_START_PROB = 0.20
SPEECH_END_PROB   = 0.10

SILENCE_TIMEOUT = 0.4
SMOOTH_WINDOW_MS = 100

RMS_GATE = 0.005    
INT16_MAX = 32767


class AudioStreamConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        ip = self.scope["client"][0]
        self.user_id = getattr(self.scope.get("user"), "id", None)

        if self.user_id is None:
            await self.close(code=4401)
            return

        rate_limit(key=f"ws:{ip}", limit=30, window_seconds=60)

        self.vad_frame_buffer = np.array([], dtype=np.float32)
        self.audio_buffer = b""
        self.prob_history = []

        self.in_speech = False
        self.speech_ms = 0.0
        self.last_speech_ts = None
        
        self.warmup_frames = 5

        await self.accept()
        
        self.log_queue = asyncio.Queue()
        self.log_task = asyncio.create_task(self._log_worker())

        self.listen_task = asyncio.create_task(self.listen_llm_responses())

        print(f"Connected user {self.user_id}")


    async def receive(self, text_data=None, bytes_data=None):
        if not bytes_data:
            return

        audio = np.frombuffer(bytes_data, dtype=np.int16).astype(np.float32)
        audio /= INT16_MAX

        self.vad_frame_buffer = np.concatenate([self.vad_frame_buffer, audio])

        smooth_frame_count = max(
            1,
            int(SMOOTH_WINDOW_MS / (FRAME_SAMPLES / TARGET_SR * 1000))
        )

        while len(self.vad_frame_buffer) >= FRAME_SAMPLES:
            frame = self.vad_frame_buffer[:FRAME_SAMPLES]
            self.vad_frame_buffer = self.vad_frame_buffer[FRAME_SAMPLES:]

            if self.warmup_frames > 0:
                self.warmup_frames -= 1
                continue

            now = time.monotonic()
            rms = np.sqrt(np.mean(frame ** 2))

            if rms < RMS_GATE:
                prob = 0.0
            else:
                prob = float(
                    VADService.speech_prob(frame, sample_rate=TARGET_SR)
                )

            self.prob_history.append(prob)
            if len(self.prob_history) > smooth_frame_count:
                self.prob_history.pop(0)

            smooth_prob = prob if not self.in_speech else float(np.mean(self.prob_history))

            await self.log(
                f"[VAD] rms={rms:.4f} "
                f"prob={prob:.3f} "
                f"smooth={smooth_prob:.3f} "
                f"in_speech={self.in_speech}"
            )

            if not self.in_speech and smooth_prob > SPEECH_START_PROB:
                await self.log("[VAD] SPEECH START")
                self.in_speech = True
                self.last_speech_ts = now
                self.audio_buffer = b""
                self.prob_history.clear()

            if self.in_speech:
                self.audio_buffer += (frame * INT16_MAX).astype(np.int16).tobytes()

                if smooth_prob > SPEECH_END_PROB:
                    self.last_speech_ts = now

                elif (now - self.last_speech_ts) > SILENCE_TIMEOUT:
                    await self.log("[VAD] SPEECH END")
                    await self.process_buffer()

                    self.in_speech = False
                    self.audio_buffer = b""
                    self.last_speech_ts = None
                    self.prob_history.clear()
                    self.warmup_frames = 3   


    async def process_buffer(self):
        await self.log("enter the process buffer method")
        min_bytes = int(TARGET_SR * 2 * 0.5)  # 0.5 sec PCM16
        if len(self.audio_buffer) < min_bytes:
            await self.log("[VAD] Dropped short utterance")
            return
        
        try:
            grpc_type = os.getenv("GRPC_DEPLOYMENT_TYPE", "local").lower()
            if grpc_type == "remote":
                await self.log("[gRPC] Using separate deployment method")
                response = await self.send_to_grpc_separate(self.audio_buffer)
            else:
                await self.log("[gRPC] Using local deployment method")
                response = await self.send_to_grpc(self.audio_buffer)

            await self.send(text_data=json.dumps(response))
            await self.log("called the grpc method successfully")

        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e)}))

        # try:
        #     await self.log("entered the service body")
        #     result = await transcribe_audio_bytes(
        #         self.audio_buffer,
        #         user_id=str(self.user_id),
        #     )
        #     await self.send(text_data=json.dumps(result))
        # except Exception as e:
        #     await self.send(text_data=json.dumps({"error": str(e)}))
        
    async def send_to_grpc_separate(self, audio_bytes: bytes):
        """
        Connect to gRPC when it's running as a separate Deployment/service in K8s.
        Uses the service DNS name instead of localhost.
        """
        user_id = str(self.user_id) if self.user_id else "anonymous"
        grpc_target = "voice-ai-grpc:50051"  # Kubernetes service name of the gRPC deployment
        await self.log(f"[gRPC] Connecting to separate gRPC service at {grpc_target}")

        async with grpc.aio.insecure_channel(grpc_target) as channel:
            stub = service_pb2_grpc.AudioServiceStub(channel)
            await self.log("[gRPC] Created stub for separate deployment")

            async def gen_chunks():
                chunk_size = 16000
                for i in range(0, len(audio_bytes), chunk_size * 2):
                    chunk = audio_bytes[i:i + chunk_size * 2]
                    if not chunk:
                        break
                    yield audio_pb2.AudioChunk(pcm=chunk)
                    await asyncio.sleep(0)  # yield control to event loop

            try:
                response = await asyncio.wait_for(
                    stub.StreamTranscribe(gen_chunks(), metadata=(("user_id", user_id),)),
                    timeout=30.0,
                )
                await self.log("[gRPC] Method invoked successfully on separate deployment")
                return {"transcript": response.transcript}

            except asyncio.CancelledError:
                await self.log("[gRPC] Call cancelled due to disconnect")
                return {"error": "gRPC call cancelled"}

            except asyncio.TimeoutError:
                await self.log("[gRPC] Call timed out")
                return {"error": "gRPC call timed out"}

            except grpc.aio.AioRpcError as e:
                await self.log(f"[gRPC ERROR] {e.code()}: {e.details()}")
                return {"error": f"gRPC call failed: {e.details()}"}
        
    async def send_to_grpc(self, audio_bytes: bytes):
        """
        Stream audio in small chunks to the gRPC AudioService and get transcription.
        """
        user_id = str(self.user_id) if self.user_id else "anonymous"
        await self.log("entered the grpc method")

        async with grpc.aio.insecure_channel("localhost:50051") as channel:
            stub = service_pb2_grpc.AudioServiceStub(channel)
            await self.log("created stub")

            async def gen_chunks():
                """
                Split audio_bytes into small PCM16 chunks and yield them.
                """
                chunk_size = 16000  
                for i in range(0, len(audio_bytes), chunk_size * 2):
                    chunk = audio_bytes[i:i + chunk_size * 2]
                    if not chunk:
                        break
                    yield audio_pb2.AudioChunk(pcm=chunk)
                    await asyncio.sleep(0)  

            try:
                response = await asyncio.wait_for(
                    stub.StreamTranscribe(gen_chunks(), metadata=(("user_id", user_id),)),
                    timeout=30.0,  
                )
                await self.log("method invoked successfully")
                return {"transcript": response.transcript}

            except asyncio.CancelledError:
                await self.log("[gRPC] Call cancelled due to disconnect")
                return {"error": "gRPC call cancelled"}

            except asyncio.TimeoutError:
                await self.log("[gRPC] Call timed out")
                return {"error": "gRPC call timed out"}

            except grpc.aio.AioRpcError as e:
                await self.log(f"[gRPC ERROR] {e.code()}: {e.details()}")
                return {"error": f"gRPC call failed: {e.details()}"}
            


    async def listen_llm_responses(self):
        connection = await get_connection()
        await self.log(f"[LLM] Connection established: {connection}")

        channel = await connection.channel()
        await self.log(f"[LLM] Channel opened: {channel}")

        exchange = await channel.declare_exchange(
            "audio_responses_exchange",
            aio_pika.ExchangeType.DIRECT,
            durable=True
        )
        
        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(exchange, routing_key="audio_responses")
        await self.log(f"[LLM] Queue declared and bound: {queue.name}")

        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    data = json.loads(message.body)
                    await self.log(f"sending the message {data}")
                    if str(data.get("user_id")) == str(self.user_id):
                        await self.log(f"sending the message {data}")
                        await self.send(text_data=json.dumps({
                            "llmResponse": data.get("response")
                        }))
                        
    async def _log_worker(self):
        try:
            while True:
                msg = await self.log_queue.get()
                print(msg)
                await asyncio.sleep(0.05)  
                self.log_queue.task_done()
        except asyncio.CancelledError:
            pass
        
    async def log(self, msg):
        if hasattr(self, "log_queue"):
            await self.log_queue.put(msg)



    async def disconnect(self, code):
        print(f"Disconnected {self.user_id}, code={code}")
        
        if hasattr(self, "log_task"):
            self.log_task.cancel()

        if hasattr(self, "listen_task"):
            self.listen_task.cancel()

        self.vad_frame_buffer = np.array([], dtype=np.float32)
        self.audio_buffer = b""
        self.in_speech = False
        self.prob_history.clear()

            
    async def cleanup(self):
        self.audio_buffer = b""
        self.vad_frame_buffer = np.array([], dtype=np.float32)
        self.in_speech = False
        self.last_speech_ts = None
