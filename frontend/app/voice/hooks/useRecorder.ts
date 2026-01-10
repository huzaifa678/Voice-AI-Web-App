import { useRef } from "react";
import { useAudioContext } from "./useAudioContext";

export function useRecorder(onFrame: (pcm: Int16Array) => void) {
  const { getContext } = useAudioContext();
  const nodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const start = async () => {
    const ctx = await getContext();

    streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = ctx.createMediaStreamSource(streamRef.current);

    const node = new AudioWorkletNode(ctx, "pcm-processor");
    node.port.onmessage = e => onFrame(e.data);

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

