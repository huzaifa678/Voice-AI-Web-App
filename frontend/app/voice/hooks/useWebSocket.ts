import { useRef } from "react";

export function useWebSocket(url: string, token?: string) {
  const wsRef = useRef<WebSocket | null>(null);

  const connect = () => {
    wsRef.current = new WebSocket(
      token ? `${url}?token=${token}` : url
    );
  };

  const send = (pcm: Int16Array) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(pcm.buffer);
    }
  };

  const close = () => {
    wsRef.current?.close();
  };

  return { connect, send, close };
}
