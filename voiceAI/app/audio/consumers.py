import asyncio
import functools
import time
import json
import grpc
import numpy as np
import aio_pika
from collections import deque
from channels.generic.websocket import AsyncWebsocketConsumer

from app.common.config import config
from app.audio.services import VADService
from app.common.logger import get_logger
from app.common.rate_limit import rate_limit
from app.common.rabbit_mq import get_connection
from app.grpc import audio_pb2, service_pb2_grpc
from app.audio.metrics import VoiceMetrics
from app.audio.session import VoiceSession
from app.audio.state import VoiceState
from app.common.telemetry import (
    SpanKind,
    context_from_metadata,
    current_trace_headers,
    record_exception,
    tracer,
)

logger = get_logger(__name__)
tracer = tracer(__name__)

TARGET_SR = 16000

FRAME_SAMPLES = 512
HOP_SAMPLES = 512

SPEECH_START_PROB = 0.20
VAD_DEBUG = config.VAD_DEBUG
SPEECH_END_PROB = 0.10

SILENCE_TIMEOUT = 0.4
SMOOTH_WINDOW_MS = 100

RMS_GATE = 0.005
INT16_MAX = 32767


class AudioStreamConsumer(AsyncWebsocketConsumer):

    async def emit_event(
        self,
        event: VoiceState,
        metadata=None
    ):

        payload = {
            "event": event.value,
            "user_id": self.user_id,
            "timestamp": VoiceMetrics.now()
        }

        if metadata:
            payload.update(metadata)

        VoiceMetrics.count_event(event.value)

        await self.log(
            f"[VOICE_EVENT] {payload}"
        )

    async def connect(self):
        ip = self.scope["client"][0]
        self.user_id = getattr(self.scope.get("user"), "id", None)

        if self.user_id is None:
            await self.close(code=4401)
            return

        # rate_limit hits Redis with a blocking client; keep it off the loop.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, functools.partial(rate_limit, key=f"ws:{ip}", limit=30, window_seconds=60)
        )

        self.session = VoiceSession(
            user_id=str(self.user_id)
        )

        self.session.is_playing_audio = False

        self.session.current_tts_task = None

        self.session.state = (
            VoiceState.LISTENING
        )

        self.session.metrics.session_started = (
            VoiceMetrics.now()
        )

        await self.accept()

        self.log_queue = asyncio.Queue()

        self.log_task = asyncio.create_task(
            self._log_worker()
        )

        self.listen_task = asyncio.create_task(
            self.listen_llm_responses()
        )

        # Persistent gRPC channel created once per WebSocket connection.
        # Reused for every transcription request to avoid per-utterance
        # TCP + HTTP/2 handshake overhead.
        self._grpc_target = config.GRPC_DEPLOYMENT_TYPE
        if self._grpc_target == "remote":
            # Headless Service resolves to every STT pod IP; the dns:/// resolver
            # plus round_robin spreads calls across them. A plain ClusterIP would
            # pin every call to a single pod over this one HTTP/2 connection.
            self._grpc_host = "dns:///voice-ai-grpc:50051"
            channel_options = [("grpc.lb_policy_name", "round_robin")]
        else:
            self._grpc_host = "localhost:50051"
            channel_options = []

        self.grpc_channel = grpc.aio.insecure_channel(
            self._grpc_host, options=channel_options
        )
        self.grpc_stub = service_pb2_grpc.AudioServiceStub(self.grpc_channel)

        # Use deque for O(1) append/pop instead of repeated np.concatenate
        # which creates new arrays on every frame and causes O(n^2) GC pressure.
        self.vad_frame_buffer = deque()

        # bytearray grows efficiently without repeated bytes concatenation
        self.session.audio_buffer = bytearray()

        self.warmup_frames = 5

        logger.info("Connected user %s", self.user_id)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:

            data = json.loads(text_data)

            if data.get("event") == "audio_finished":
                self.session.is_playing_audio = False
                self.session.set_state(VoiceState.LISTENING)
                await self.emit_event(VoiceState.LISTENING)
                await self.log("[VOICE] Playback finished, returning to LISTENING")

            return

        audio = np.frombuffer(bytes_data, dtype=np.int16).astype(np.float32)
        audio /= INT16_MAX

        loop = asyncio.get_running_loop()

        # O(1) append to deque instead of np.concatenate
        self.vad_frame_buffer.extend(audio.tolist())

        smooth_frame_count = max(
            1, int(SMOOTH_WINDOW_MS / (FRAME_SAMPLES / TARGET_SR * 1000))
        )

        while len(self.vad_frame_buffer) >= FRAME_SAMPLES:
            frame_float = np.array(
                list(self.vad_frame_buffer)[:FRAME_SAMPLES], dtype=np.float32
            )
            # consume exactly FRAME_SAMPLES from the left
            for _ in range(FRAME_SAMPLES):
                self.vad_frame_buffer.popleft()

            if self.warmup_frames > 0:
                self.warmup_frames -= 1
                continue

            now = time.monotonic()
            rms = np.sqrt(np.mean(frame_float**2))

            if rms < RMS_GATE:
                prob = 0.0
            else:
                # running torch forward pass off the event loop
                # avoiding stalling the websocket consumer for long periods of time
                prob = float(
                    await loop.run_in_executor(
                        None, VADService.speech_prob, frame_float, TARGET_SR
                    )
                )

            self.session.prob_history.append(prob)
            if len(self.session.prob_history) > smooth_frame_count:
                self.session.prob_history.pop(0)

            smooth_prob = (
                prob if not self.session.in_speech else float(np.mean(self.session.prob_history))
            )

            if VAD_DEBUG:
                await self.log(
                    f"[VAD] rms={rms:.4f} "
                    f"prob={prob:.3f} "
                    f"smooth={smooth_prob:.3f} "
                    f"in_speech={self.session.in_speech}"
                )

            if not self.session.in_speech and smooth_prob > SPEECH_START_PROB:

                await self.log("[VAD] SPEECH START")

                if self.session.state == VoiceState.SPEAKING:
                    await self.log(
                        "[BARGE-IN] User interrupted TTS"
                    )

                    self.session.interrupt()

                    await self.emit_event(
                        VoiceState.INTERRUPTED
                    )

                    await self.send(
                        text_data=json.dumps(
                            {
                                "event": "stop_audio"
                            }
                        )
                    )

                self.session.in_speech = True
                self.session.state = VoiceState.SPEECH_STARTED
                started = VoiceMetrics.now()
                self.session.metrics.session_started = started
                self.session.metrics.vad_started = started

                self.session.last_speech_ts = now

                await self.emit_event(VoiceState.SPEECH_STARTED)

                # audio collection for transcription
                self.session.state = VoiceState.TRANSCRIBING

            if self.session.in_speech:
                # Efficient bytes accumulation with bytearray
                self.session.audio_buffer.extend(
                    (frame_float * INT16_MAX).astype(np.int16).tobytes()
                )

                if smooth_prob > SPEECH_END_PROB:
                    self.session.last_speech_ts = now

                elif (now - self.session.last_speech_ts) > SILENCE_TIMEOUT:
                    await self.log("[VAD] SPEECH END")
                    self.session.metrics.vad_finished = (
                        VoiceMetrics.now()
                    )
                    self.session.metrics.observe_vad()

                    await self.emit_event(
                        VoiceState.TRANSCRIBING
                    )

                    await self.process_buffer()

                    self.session.in_speech = False
                    self.session.audio_buffer = bytearray()
                    self.session.last_speech_ts = None
                    self.session.prob_history.clear()
                    self.warmup_frames = 3

    async def process_buffer(self):
        await self.log("enter the process buffer method")
        min_bytes = int(TARGET_SR * 2 * 0.5)  # 0.5 sec PCM16
        if len(self.session.audio_buffer) < min_bytes:
            await self.log("[VAD] Dropped short utterance")
            return

        audio_bytes = bytes(self.session.audio_buffer)
        VoiceMetrics.observe_audio_bytes(len(audio_bytes))

        with tracer.start_as_current_span(
            "voice.websocket.utterance",
            kind=SpanKind.SERVER,
            attributes={
                "voice.user_id": str(self.user_id),
                "voice.audio_bytes": len(audio_bytes),
            },
        ) as span:
            try:
                grpc_type = config.GRPC_DEPLOYMENT_TYPE
                self.session.state = (VoiceState.TRANSCRIBING)
                self.session.metrics.stt_started = (VoiceMetrics.now())
                if grpc_type == "remote":
                    await self.log("[gRPC] Using persistent channel (remote)")
                    response = await self.send_to_grpc_separate(audio_bytes)
                else:
                    await self.log("[gRPC] Using persistent channel (local)")
                    response = await self.send_to_grpc(audio_bytes)

                self.session.metrics.stt_finished = (VoiceMetrics.now())
                self.session.metrics.observe_stt()
                self.session.state = (VoiceState.THINKING)

                transcript = response.get("transcript")
                span.set_attribute("voice.transcript_chars", len(transcript or ""))

                await self.emit_event(VoiceState.THINKING, {"transcript": transcript})

                self.session.metrics.websocket_sent = VoiceMetrics.now()
                self.session.metrics.observe(
                    "stt_roundtrip",
                    self.session.metrics.session_started,
                    self.session.metrics.websocket_sent,
                )
                await self.send(text_data=json.dumps(response))
                await self.log("called the grpc method successfully")

            except Exception as e:
                VoiceMetrics.count_error("websocket_process_buffer")
                record_exception(span, e)
                await self.send(text_data=json.dumps({"error": str(e)}))

    async def send_to_grpc_separate(self, audio_bytes: bytes):
        """
        Stream audio to gRPC using the persistent channel created in connect().
        """
        user_id = str(self.user_id) if self.user_id else "anonymous"
        await self.log(f"[gRPC] Using persistent channel to {self._grpc_host}")

        async def gen_chunks():
            chunk_size = 16000
            for i in range(0, len(audio_bytes), chunk_size * 2):
                chunk = audio_bytes[i : i + chunk_size * 2]
                if not chunk:
                    break
                yield audio_pb2.AudioChunk(pcm=chunk)
                await asyncio.sleep(0)  # yield control to event loop

        async def consume_stream():
            with tracer.start_as_current_span(
                "voice.grpc.client_stream_transcribe",
                kind=SpanKind.CLIENT,
                attributes={
                    "rpc.system": "grpc",
                    "rpc.service": "AudioService",
                    "rpc.method": "StreamTranscribe",
                    "net.peer.name": self._grpc_host,
                    "voice.audio_bytes": len(audio_bytes),
                },
            ) as span:
                transcript_parts = []
                metadata = tuple(current_trace_headers().items()) + (("user_id", user_id),)
                async for response in self.grpc_stub.StreamTranscribe(
                    gen_chunks(), metadata=metadata
                ):
                    if response.transcript:
                        transcript_parts.append(response.transcript)
                transcript = " ".join(transcript_parts)
                span.set_attribute("voice.transcript_chars", len(transcript))
                await self.log(
                    "[gRPC] Method invoked successfully on separate deployment"
                )
                return {"transcript": transcript}

        try:
            return await asyncio.wait_for(consume_stream(), timeout=90.0)

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
        Stream audio in small chunks to the gRPC AudioService using the
        persistent channel created in connect().
        """
        user_id = str(self.user_id) if self.user_id else "anonymous"
        await self.log("entered the grpc method")

        async def gen_chunks():
            """
            Split audio_bytes into small PCM16 chunks and yield them.
            """
            chunk_size = 16000
            for i in range(0, len(audio_bytes), chunk_size * 2):
                chunk = audio_bytes[i : i + chunk_size * 2]
                if not chunk:
                    break
                yield audio_pb2.AudioChunk(pcm=chunk)
                await asyncio.sleep(0)

        async def consume_stream():
            with tracer.start_as_current_span(
                "voice.grpc.client_stream_transcribe",
                kind=SpanKind.CLIENT,
                attributes={
                    "rpc.system": "grpc",
                    "rpc.service": "AudioService",
                    "rpc.method": "StreamTranscribe",
                    "net.peer.name": self._grpc_host,
                    "voice.audio_bytes": len(audio_bytes),
                },
            ) as span:
                transcript_parts = []
                metadata = tuple(current_trace_headers().items()) + (("user_id", user_id),)
                async for response in self.grpc_stub.StreamTranscribe(
                    gen_chunks(), metadata=metadata
                ):
                    if response.transcript:
                        transcript_parts.append(response.transcript)
                transcript = " ".join(transcript_parts)
                span.set_attribute("voice.transcript_chars", len(transcript))
                await self.log("method invoked successfully")
                return {"transcript": transcript}

        try:
            return await asyncio.wait_for(consume_stream(), timeout=90.0)

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
            "audio_responses_exchange", aio_pika.ExchangeType.DIRECT, durable=True
        )

        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(exchange, routing_key="audio_responses")
        await self.log(f"[LLM] Queue declared and bound: {queue.name}")

        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    data = json.loads(message.body)
                    parent_context = context_from_metadata(data.get("trace", {}).items())
                    with tracer.start_as_current_span(
                        "voice.websocket.deliver_response",
                        context=parent_context,
                        kind=SpanKind.SERVER,
                        attributes={
                            "voice.user_id": str(self.user_id),
                            "voice.response_chars": len(data.get("response") or ""),
                            "voice.tts.audio_base64_chars": len(data.get("audio_bytes") or ""),
                        },
                    ) as span:
                        try:
                            await self.log(f"sending the message {data}")
                            if str(data.get("user_id")) == str(self.user_id):
                                await self.log(f"sending the message {data}")
                                self.session.state = (VoiceState.SPEAKING)

                                await self.emit_event(VoiceState.SPEAKING)
                                await self.send(
                                    text_data=json.dumps(
                                        {
                                            "llmResponse": data.get("response"),
                                            "audioBase64": data.get("audio_bytes"),
                                        }
                                    )
                                )
                                if data.get("audio_bytes"):
                                    self.session.metrics.websocket_sent = VoiceMetrics.now()
                                    self.session.metrics.observe_total()
                        except Exception as exc:
                            record_exception(span, exc)
                            raise

    async def _log_worker(self):
        try:
            while True:
                msg = await self.log_queue.get()
                logger.info(msg)
                await asyncio.sleep(0.05)
                self.log_queue.task_done()
        except asyncio.CancelledError:
            pass

    async def log(self, msg):
        if hasattr(self, "log_queue"):
            await self.log_queue.put(msg)

    async def disconnect(self, code):
        logger.info("Disconnected %s, code=%s", self.user_id, code)

        if hasattr(self, "log_task"):
            self.log_task.cancel()

        if hasattr(self, "listen_task"):
            self.listen_task.cancel()

        # Close persistent gRPC channel gracefully
        if hasattr(self, "grpc_channel") and self.grpc_channel is not None:
            await self.grpc_channel.close()
            self.grpc_channel = None
            self.grpc_stub = None

        self.vad_frame_buffer = deque()
        self.session.audio_buffer = bytearray()
        self.session.in_speech = False
        self.session.prob_history.clear()

    async def cleanup(self):
        self.session.audio_buffer = bytearray()
        self.vad_frame_buffer = deque()
        self.session.in_speech = False
        self.session.last_speech_ts = None
