import { useRecorder } from "./useRecorder";
import { useWebSocket } from "./useWebSocket";

export function useStreamingSTT(
  wsUrl: string,
  token?: string
) {
  const ws = useWebSocket(wsUrl, token);

  const recorder = useRecorder((pcm) => {
    ws.send(pcm);
  });

  const start = async () => {
    ws.connect();
    await recorder.start();
  };

  const stop = () => {
    recorder.stop();
    ws.close();
  };

  return { start, stop };
}
