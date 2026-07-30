from dataclasses import dataclass
import time

from prometheus_client import Counter, Histogram

VOICE_EVENTS_TOTAL = Counter(
    "voice_events_total",
    "Voice state events emitted by the websocket layer.",
    ["event"],
)

VOICE_ERRORS_TOTAL = Counter(
    "voice_errors_total",
    "Voice pipeline errors by stage.",
    ["stage"],
)

VOICE_LATENCY_SECONDS = Histogram(
    "voice_latency_seconds",
    "Voice pipeline latency by stage.",
    ["stage"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60),
)

VOICE_AUDIO_BYTES = Histogram(
    "voice_audio_bytes",
    "PCM audio payload size sent to the backend pipeline.",
    buckets=(1024, 4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288),
)


@dataclass
class VoiceMetrics:

    session_started: float = 0.0

    vad_started: float = 0.0
    vad_finished: float = 0.0

    stt_started: float = 0.0
    stt_finished: float = 0.0

    llm_started: float = 0.0
    llm_finished: float = 0.0

    tts_started: float = 0.0
    tts_finished: float = 0.0

    websocket_sent: float = 0.0

    @staticmethod
    def now():
        return time.perf_counter()

    @staticmethod
    def observe(stage: str, started: float, finished: float | None = None):
        if not started:
            return
        end = finished or VoiceMetrics.now()
        if end >= started:
            VOICE_LATENCY_SECONDS.labels(stage=stage).observe(end - started)

    @staticmethod
    def count_event(event: str):
        VOICE_EVENTS_TOTAL.labels(event=event).inc()

    @staticmethod
    def count_error(stage: str):
        VOICE_ERRORS_TOTAL.labels(stage=stage).inc()

    @staticmethod
    def observe_audio_bytes(size: int):
        VOICE_AUDIO_BYTES.observe(size)

    def total_latency(self):
        if self.websocket_sent == 0:
            return None
        return self.websocket_sent - self.session_started

    def stt_latency(self):
        return self.stt_finished - self.stt_started

    def llm_latency(self):
        return self.llm_finished - self.llm_started

    def tts_latency(self):
        return self.tts_finished - self.tts_started

    def observe_vad(self):
        self.observe("vad", self.vad_started, self.vad_finished)

    def observe_stt(self):
        self.observe("stt", self.stt_started, self.stt_finished)

    def observe_llm(self):
        self.observe("llm", self.llm_started, self.llm_finished)

    def observe_tts(self):
        self.observe("tts", self.tts_started, self.tts_finished)

    def observe_total(self):
        self.observe("total", self.session_started, self.websocket_sent)
