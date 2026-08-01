from simulstreaming.whisper.whisper_streaming.base import (
    OnlineProcessorInterface,
    ASRBase,
)

import sys
import logging
import torch

from simulstreaming.whisper.simul_whisper.config import AlignAttConfig
from simulstreaming.whisper.simul_whisper.simul_whisper import (
    PaddedAlignAttWhisper
)


logger = logging.getLogger(__name__)


def simul_asr_factory(args):

    logger.setLevel(args.log_level)
    decoder = args.decoder

    if args.beams > 1:
        if decoder == "greedy":
            raise ValueError(
                "Invalid 'greedy' decoder type for beams > 1. Use 'beam'."
            )
        elif decoder is None or decoder == "beam":
            decoder = "beam"
        else:
            raise ValueError(
                "Invalid decoder type. Use 'beam' or 'greedy'."
            )

    else:

        if decoder is None:
            decoder = "greedy"

        elif decoder not in ("beam", "greedy"):
            raise ValueError(
                "Invalid decoder type. Use 'beam' or 'greedy'."
            )


    config = {
        value: getattr(args, value)
        for value in [
            "model_path",
            "cif_ckpt_path",
            "frame_threshold",
            "audio_min_len",
            "audio_max_len",
            "beams",
            "task",
            "never_fire",
            "init_prompt",
            "static_init_prompt",
            "max_context_tokens",
            "logdir",
        ]
    }


    config["language"] = args.lan
    config["segment_length"] = args.min_chunk_size
    config["decoder_type"] = decoder


    if args.min_chunk_size >= args.audio_max_len:

        raise ValueError(
            "min_chunk_size must be smaller than audio_max_len"
        )


    if args.audio_min_len > args.audio_max_len:

        raise ValueError(
            "audio_min_len must be smaller than audio_max_len"
        )


    logger.info(
        "SimulWhisper arguments: %s",
        config
    )


    asr = SimulWhisperASR(
        **config
    )


    online = SimulWhisperOnline(
        asr
    )


    return asr, online



class SimulWhisperASR(ASRBase):

    sep = " "


    def __init__(
        self,
        language,
        model_path,
        cif_ckpt_path,
        frame_threshold,
        audio_max_len,
        audio_min_len,
        segment_length,
        beams,
        task,
        decoder_type,
        never_fire,
        init_prompt,
        static_init_prompt,
        max_context_tokens,
        logdir,
    ):


        cfg = AlignAttConfig(

            model_path=model_path,

            segment_length=segment_length,

            frame_threshold=frame_threshold,

            language=language,

            audio_max_len=audio_max_len,

            audio_min_len=audio_min_len,

            cif_ckpt_path=cif_ckpt_path,

            decoder_type=decoder_type,

            beam_size=beams,

            task=task,

            never_fire=never_fire,

            init_prompt=init_prompt,

            max_context_tokens=max_context_tokens,

            static_init_prompt=static_init_prompt,

            logdir=logdir,
        )


        logger.info(
            "Loading SimulWhisper language=%s",
            language
        )


        self.model = PaddedAlignAttWhisper(
            cfg
        )



    def transcribe(
        self,
        audio,
        init_prompt=""
    ):

        raise NotImplementedError(
            "Use SimulWhisperOnline.process_iter()"
        )



    def warmup(
        self,
        audio,
        init_prompt=""
    ):

        self.model.insert_audio(
            audio
        )

        self.model.infer(
            True
        )

        self.model.refresh_segment(
            complete=True
        )



    def use_vad(self):

        print(
            "VAD not implemented",
            file=sys.stderr
        )



    def set_translate_task(self):

        pass





class SimulWhisperOnline(OnlineProcessorInterface):


    def __init__(
        self,
        asr
    ):

        self.model = asr.model

        self.file = None

        self.init()



    def init(
        self,
        offset=None
    ):

        self.audio_chunks = []


        if offset is not None:

            self.offset = offset

        else:

            self.offset = 0



        self.is_last = False


        self.beg = self.offset

        self.end = self.offset


        self.audio_bufer_offset = self.offset


        self.last_ts = -1


        self.model.refresh_segment(
            complete=True
        )


        self.unicode_buffer = []



    def insert_audio_chunk(
        self,
        audio
    ):

        self.audio_chunks.append(
            torch.from_numpy(audio)
        )



    def timestamped_text(
        self,
        tokens,
        generation
    ):

        if not generation:

            return []


        progress = generation["progress"]


        if (
            "result" not in generation
            or self.unicode_buffer != []
        ):

            split_words, split_tokens = (
                self.model.tokenizer.split_to_word_tokens(tokens)
            )

        else:

            split_words = generation["result"]["split_words"]

            split_tokens = generation["result"]["split_tokens"]



        frames = [
            item["most_attended_frames"][0]
            for item in progress
        ]



        tokens = tokens.copy()


        result = []


        for word, word_tokens in zip(
            split_words,
            split_tokens
        ):

            begin = None


            for token in word_tokens:

                current_token, frame = (
                    tokens.pop(0),
                    frames.pop(0)
                )


                if current_token != token:

                    raise ValueError(
                        f"Token mismatch {current_token} != {token}"
                    )


                if begin is None:

                    begin = frame



            end = frame


            result.append(
                {
                    "start": begin * 0.02 + self.audio_bufer_offset,

                    "end": end * 0.02 + self.audio_bufer_offset,

                    "text": word,

                    "tokens": word_tokens,
                }
            )


        return result




    def process_iter(self):

        if len(self.audio_chunks) == 0:

            audio = None

        else:

            audio = torch.cat(
                self.audio_chunks,
                dim=0
            )


            if audio.shape[0] == 0:

                audio = None


            else:

                self.end += (
                    audio.shape[0]
                    /
                    self.SAMPLING_RATE
                )


        self.audio_chunks = []


        self.audio_bufer_offset += (
            self.model.insert_audio(audio)
        )


        tokens, generation = (
            self.model.infer(
                is_last=self.is_last
            )
        )


        text = self.model.tokenizer.decode(
            tokens
        )


        if len(text) == 0:

            return {}



        words = self.timestamped_text(
            tokens,
            generation
        )



        return {

            "start": words[0]["start"]
            if words else self.beg,

            "end": words[-1]["end"]
            if words else self.end,

            "text": text,

            "tokens": tokens,

            "words": words,
        }




    def finish(self):

        logger.info(
            "Finishing SimulWhisper"
        )

        self.is_last = True
        output = self.process_iter()

        self.is_last = False


        self.model.refresh_segment(
            complete=True
        )

        return output