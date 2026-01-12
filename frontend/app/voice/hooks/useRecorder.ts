import { useRef } from "react";
import { useAudioContext } from "./useAudioContext";

export function useRecorder(onFrame: (pcmBuffer: ArrayBuffer) => void) {
  const { getContext } = useAudioContext();
  const nodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const start = async () => {
    const ctx = await getContext();

    streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = ctx.createMediaStreamSource(streamRef.current);

    const node = new AudioWorkletNode(ctx, "pcm-processor");
    node.port.onmessage = e => {
      const pcm = e.data as Int16Array;

      const rms = Math.sqrt(pcm.reduce((sum, val) => sum + val * val, 0) / pcm.length);
      console.log("Audio RMS:", rms.toFixed(3));

      onFrame(pcm.buffer as ArrayBuffer);
    }

    source.connect(node);
    node.connect(ctx.destination);

    nodeRef.current = node;
  };

  const stop = () => {
    nodeRef.current?.disconnect();
    streamRef.current?.getTracks().forEach(t => t.stop());
  };

  return { start, stop };
}