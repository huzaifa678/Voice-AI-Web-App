import { useState } from "react";
import { useRecorder } from "./useRecorder";
import { useWebSocket } from "./useWebSocket";
import { store } from "@redux/store";
import { setCredentials } from "@redux/authSlice";
import { refreshAccessToken } from "@/api/auth/refresh.route";
import { jwtDecode } from "jwt-decode";

export type LLMResponse = {
  llmResponse?: string;
  audioBase64?: string;
};

export function useStreamingSST(wsUrl: string, token?: string) {
  const [transcript, setTranscript] = useState("");
  const [llmResponse, setLlmResponse] = useState<LLMResponse | null>(null);

  const recorder = useRecorder((pcmBuffer) => {
    ws.send(pcmBuffer);
  });

  const ws = useWebSocket(wsUrl, recorder, (event) => {
    const data = JSON.parse(event.data);

    console.log("WS MESSAGE:", data);

    // if ("transcript" in data) {
    //   console.log("TRANSCRIPT:", data.transcript);
    // }

    if (data.transcript) {
      console.log("TRANSCRIPT:", data.transcript);
      setTranscript(data.transcript);
    }

    if (data.llmResponse || data.audioBase64) {
      setLlmResponse({
        llmResponse: data.llmResponse,
        audioBase64: data.audioBase64,
      });
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
    setLlmResponse(null);

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
    llmResponse,
    analyser: recorder.analyser,
  };
}
