import logging
import os
from types import SimpleNamespace

import numpy as np

from app.common.config import config
from simulstreaming.whisper_factory import (
    simul_asr_factory,
)


logger = logging.getLogger(__name__)

ENVIRONMENT = config.ENVIRONMENT


class SimulWhisperService:

    _asr = None
    _online = None

    MODEL_PATH = (
        config.WHISPER_MODEL_PATH or config.WHISPER_MODEL_PATH_DEFAULT_REMOTE
    )

    @classmethod
    def model(cls):

        if cls._online is None:

            logger.info(
                "[SimulWhisper] Loading model..."
            )

            if ENVIRONMENT == "local":
                model_path = os.path.expanduser(
                    config.WHISPER_MODEL_PATH
                    or config.WHISPER_MODEL_PATH_DEFAULT_LOCAL
                )
            else:
                model_path = cls.MODEL_PATH

            args = SimpleNamespace(
                log_level=logging.INFO,
                model_path=model_path,
                cif_ckpt_path=None,
                frame_threshold=25,
                audio_min_len=0.0,
                audio_max_len=30.0,
                beams=1,
                decoder="greedy",
                task="transcribe",
                never_fire=False,
                init_prompt=None,
                static_init_prompt=None,
                max_context_tokens=None,
                lan="en",
                min_chunk_size=config.WHISPER_MIN_CHUNK,
                logdir=None,
            )

            cls._asr, cls._online = (
                simul_asr_factory(
                    args
                )
            )

            logger.info(
                "[SimulWhisper] Model loaded"
            )

        return cls._online

    @classmethod
    def transcribe_chunk(
        cls,
        audio: np.ndarray
    ):

        model = cls.model()

        model.insert_audio_chunk(
            audio
        )

        result = model.process_iter()

        logger.info("process_iter returned: %r", result)
        logger.info("type: %s", type(result))
        logger.info(type(model))

        if not result:

            return ""

        return result.get(
            "text",
            ""
        )

    @classmethod
    def finish(cls):
        """
        Flush remaining buffered audio.
        Called when stream closes.
        """

        if cls._online is None:
            return ""

        result = cls._online.finish()

        if not result:

            return ""

        return result.get(
            "text",
            ""
        )
