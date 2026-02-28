import asyncio
import json
import os
from urllib.parse import quote
import numpy as np
import pytest
import httpx
from websockets.asyncio.client import connect
import soundfile as sf

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


@pytest.mark.asyncio
async def test_audio_flow_e2e_smoke():
    await wait_for_server()

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
        resp_json = resp.json()
        print(resp_json)
        access_token = resp.json()["access"]["access"]
        print(type(access_token))

    base_ws = os.getenv("WS_URL", "ws://localhost:8000/ws/audio/")
    WS_URL = f"{base_ws}?token={quote(access_token)}"

    async with connect(
        WS_URL,
        max_size=10 * 1024 * 1024,
    ) as websocket:
        pcm, sr = sf.read("fixtures/test.wav", dtype="int16")
        assert sr == TARGET_SR
        pcm16 = pcm.tobytes()

        frame_bytes = 512 * 2
        for i in range(0, len(pcm16), frame_bytes):
            await websocket.send(pcm16[i : i + frame_bytes])
            await asyncio.sleep(0.01)

        silence_duration_sec = 2.5
        silence = np.zeros(
            int(TARGET_SR * silence_duration_sec), dtype=np.int16
        ).tobytes()

        for i in range(0, len(silence), frame_bytes):
            await websocket.send(silence[i : i + frame_bytes])
            await asyncio.sleep(0.01)

        await asyncio.sleep(1.5)
        await websocket.send(b"")

        transcript_received = False
        llm_received = False
        deadline = asyncio.get_event_loop().time() + 60

        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=5)
            except asyncio.TimeoutError:
                continue

            payload = json.loads(msg)

            if "transcript" in payload:
                transcript_received = True
                print("TRANSCRIPT:", payload["transcript"])

            if "llmResponse" in payload:
                llm_received = True
                print("LLM:", payload["llmResponse"])

            if transcript_received and llm_received:
                break

        assert transcript_received, "gRPC transcription never returned"
        assert llm_received, "LLM response never returned"
