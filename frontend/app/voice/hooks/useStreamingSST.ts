import { useState } from "react";
import { useRecorder } from "./useRecorder";
import { useWebSocket } from "./useWebSocket";
import { store } from "@redux/store";
import { setCredentials } from "@redux/authSlice";
import { refreshAccessToken } from "@/api/auth/refresh.route";
import { jwtDecode } from "jwt-decode";

function playAudioBase64(base64: string) {
  try {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    const url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    audio.onerror = () => URL.revokeObjectURL(url);
    audio.play().catch((err) => console.error("TTS audio playback failed", err));
  } catch (err) {
    console.error("Failed to decode TTS audio", err);
  }
}

export function useStreamingSST(wsUrl: string, token?: string) {
  const [transcript, setTranscript] = useState("");
  const [answer, setAnswer] = useState("");

  const recorder = useRecorder((pcmBuffer) => {
    ws.send(pcmBuffer);
  });

  const ws = useWebSocket(wsUrl, recorder, (event) => {
    const data = JSON.parse(event.data);

    if (data.transcript) {
      setTranscript(data.transcript);
      setAnswer("");
    }

    if (data.llmResponse) {
      setAnswer(data.llmResponse);
    }

    if (data.audioBase64) {
      playAudioBase64(data.audioBase64);
    }
  });

  const isExpired = (token?: string) => {
    if (!token) return true;

    try {
      const { exp } = jwtDecode<{ exp: number }>(token);
      return Date.now() >= exp * 1000;
    } catch {
      return true;
    }
  };

  const start = async () => {
    setTranscript("");
    setAnswer("");

    let access = token ?? store.getState().auth.accessToken;
    const refresh = localStorage.getItem("refresh-token");

    if (access && refresh && isExpired(access)) {
      try {
        const res = await refreshAccessToken(refresh);
        access = res.access.access;

        store.dispatch(
          setCredentials({
            access,
            refresh,
          })
        );
      } catch (err) {
        console.error("Failed to refresh access token", err);
        return;
      }
    }

    if (!access) {
      console.error("No valid access token");
      return;
    }

    await ws.connect(access);
    await recorder.start();
  };

  const stop = async () => {
    await recorder.stop();
    ws.close();
  };

  return {
    start,
    stop,
    transcript,
    answer,
    analyser: recorder.analyser,
  };
}
