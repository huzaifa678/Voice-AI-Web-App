import { useState } from "react";
import { useRecorder } from "./useRecorder";
import { useWebSocket } from "./useWebSocket";
import { store } from "@redux/store";
import { setCredentials } from "@redux/authSlice";
import { refreshAccessToken } from "@/api/auth/refresh.route";
import { jwtDecode } from "jwt-decode";

export function useStreamingSTT(wsUrl: string, token?: string) {
  const [transcript, setTranscript] = useState<string>("");
  const [llmResponse, setLlmResponse] = useState<string>("");

  const recorder = useRecorder((pcmBuffer) => {
    ws.send(pcmBuffer);
  });

  const ws = useWebSocket(wsUrl, recorder, (event) => {
    const data = JSON.parse(event.data);
    if (data.transcript) setTranscript(data.transcript);
    if (data.llmResponse) {
      setLlmResponse(data.llmResponse);
    }
  });

  const isExpired = (token?: string) => {
    if (!token) return true; 
    try {
      const { exp } = jwtDecode<{ exp: number }>(token);
      return Date.now() >= exp * 1000;
    } catch (err) {
      console.warn("Invalid access token, treating as expired:", err);
      return true;
    }
  };

  const start = async () => {
    setTranscript("");
    setLlmResponse("");

    let access = token ?? store.getState().auth.accessToken;
    const refresh = localStorage.getItem('refresh-token')

    console.log(token)
    console.log(access)
    console.log("refresh", refresh)
    console.log(store.getState().auth);

    if (access && refresh && isExpired(access)) {
      try {
        const res = await refreshAccessToken(refresh);
        const refreshedToken = await res.access.access;
        access = refreshedToken;

        console.log("ACCESS", access)

        store.dispatch(
          setCredentials({ access: access, refresh: refresh
          })
        );
      } catch (err) {
        console.error("Failed to refresh token", err);
        return;
      }
    }

    if (!access) {
      console.error("No valid access token available");
      return;
    }

    console.log("ACCESS2", access)

    await ws.connect(access);

    await recorder.start();
  };

  const stop = () => {
    recorder.stop();
    ws.close();
  };

  return { start, stop, transcript, llmResponse };
}
