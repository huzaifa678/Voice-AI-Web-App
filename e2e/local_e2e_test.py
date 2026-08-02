import asyncio
import json
import os
from urllib.parse import quote
import numpy as np
import pytest
import httpx
from websockets.asyncio.client import connect
import soundfile as sf
from app.common.logger import get_logger

logger = get_logger(__name__)

TARGET_SR = 16000
INT16_MAX = 32767

HTTP_BASE = os.getenv("HTTP_BASE", "http://localhost:8000/api")
HTTP_BASE_HEALTH = os.getenv("HTTP_BASE_HEALTH", "http://localhost:8000")
WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/audio/")


async def wait_for_server():
    async with httpx.AsyncClient() as client:
        for _ in range(40):
            try:
                r = await client.get(f"{HTTP_BASE_HEALTH}/health/")
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError("Backend never became ready")


async def login():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HTTP_BASE}/auth/register/",
            json={
                "username": "e2e_user",
                "email": "e2e@test.com",
                "password": "password123",
            },
        )

        if resp.status_code not in (201, 400):
            pytest.fail(f"Unexpected register status {resp.status_code}")

        resp = await client.post(
            f"{HTTP_BASE}/auth/login/",
            json={
                "username": "e2e_user",
                "password": "password123",
            },
        )

        assert resp.status_code == 200
        return resp.json()["access"]["access"]


def load_fixture(filename):
    pcm, sr = sf.read(f"fixtures/{filename}", dtype="int16")
    assert sr == TARGET_SR
    return pcm


def silence(seconds):
    return np.zeros(int(TARGET_SR * seconds), dtype=np.int16)


async def stream_audio(websocket, pcm):
    pcm16 = pcm.astype(np.int16).tobytes()
    frame_bytes = 512 * 2

    for i in range(0, len(pcm16), frame_bytes):
        await websocket.send(pcm16[i : i + frame_bytes])
        await asyncio.sleep(0.01)

    trailing = silence(2.5).tobytes()
    for i in range(0, len(trailing), frame_bytes):
        await websocket.send(trailing[i : i + frame_bytes])
        await asyncio.sleep(0.01)

    await asyncio.sleep(1.5)
    await websocket.send(b"")


async def collect_responses(websocket, deadline_seconds=240):
    transcript_received = False
    llm_received = False
    deadline = asyncio.get_event_loop().time() + deadline_seconds

    while asyncio.get_event_loop().time() < deadline:
        try:
            msg = await asyncio.wait_for(websocket.recv(), timeout=5)
        except asyncio.TimeoutError:
            continue

        payload = json.loads(msg)

        if "transcript" in payload:
            transcript_received = True
            logger.info("TRANSCRIPT: %s", payload["transcript"])

        if "llmResponse" in payload:
            llm_received = True
            logger.info("LLM: %s", payload["llmResponse"])

        if transcript_received and llm_received:
            break

    return transcript_received, llm_received


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,fixture",
    [
        ("full", "test.wav"),
        ("partial", "test_partial.wav"),
        ("paused", "test_paused.wav"),
        ("stuttering", "test_stuttering.wav"),
        ("quiet", "test_quiet.wav"),
        ("loud", "test_loud.wav"),
        ("noisy", "test_noisy.wav"),
        ("long_pause", "test_long_pause.wav"),
        ("clipped_start", "test_clipped_start.wav"),
        ("fast", "test_fast.wav"),
        ("slow", "test_slow.wav"),
        ("repeat", "test_repeat.wav"),
        ("fade_in", "test_fade_in.wav"),
        ("echo", "test_echo.wav"),
    ],
)
async def test_audio_flow_e2e_smoke(name, fixture):
    await wait_for_server()

    logger.info("Running audio flow case: %s", name)

    access_token = await login()

    ws_url = f"{WS_URL}?token={quote(access_token)}"

    async with connect(
        ws_url,
        max_size=10 * 1024 * 1024,
    ) as websocket:
        await stream_audio(websocket, load_fixture(fixture))

        transcript_received, llm_received = await collect_responses(websocket)

        assert transcript_received, "gRPC transcription never returned"
        assert llm_received, "LLM response never returned"
