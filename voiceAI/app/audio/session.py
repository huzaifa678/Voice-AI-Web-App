import asyncio
from dataclasses import dataclass, field

import numpy as np

from app.audio.metrics import VoiceMetrics
from app.audio.state import VoiceState


@dataclass
class VoiceSession:

    user_id: str

    state: VoiceState = VoiceState.LISTENING

    metrics: VoiceMetrics = field(
        default_factory=VoiceMetrics
    )

    vad_frame_buffer: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=np.float32)
    )

    audio_buffer: bytes = b""

    prob_history: list = field(
        default_factory=list
    )

    in_speech: bool = False

    speech_ms: float = 0.0

    last_speech_ts: float | None = None

    warmup_frames: int = 5

    interruption_event: asyncio.Event = field(
        default_factory=asyncio.Event
    )

    is_playing_audio: bool = False

    current_tts_task: asyncio.Task | None = None

    transcript: str = ""

    llm_response: str = ""

    def set_state(
        self,
        state: VoiceState
    ):
        self.state = state

    def interrupt(self):
        """
        Called when user speaks
        while TTS is playing.
        """

        self.state = VoiceState.INTERRUPTED

        self.is_playing_audio = False

        self.interruption_event.set()

        if self.current_tts_task:
            self.current_tts_task.cancel()

    def reset_interrupt(self):
        self.interruption_event.clear()

        self.state = VoiceState.LISTENING
