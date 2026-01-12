import { useRef } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@redux/store";

export function useWebSocket(
  url: string,
  onMessage?: (event: MessageEvent) => void
) {
  const wsRef = useRef<WebSocket | null>(null);

  const { accessToken } = useSelector(
    (state: RootState) => state.auth
  );

  const connect = async (token?: string) => {

    const validToken = token || accessToken;

    if (!validToken) return console.error("No access token available");

    wsRef.current = new WebSocket(`${url}?token=${validToken}`);

    wsRef.current.onopen = () => console.log("WebSocket connected");

    wsRef.current.onmessage = (event) => onMessage?.(event);

    wsRef.current.onerror = (err) => console.error("WebSocket error", err);

    wsRef.current.onclose = async (event) => {
      console.log("WebSocket closed", event.code);
    };
  };

  const send = (pcm: Int16Array | ArrayBufferView | ArrayBuffer | string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(pcm);
    }
  };

  const close = () => wsRef.current?.close();

  return { connect, send, close };
}

