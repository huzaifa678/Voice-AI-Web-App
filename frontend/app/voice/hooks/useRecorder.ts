import { useRef } from "react";
import { useAudioContext } from "./useAudioContext";

export function useRecorder(onFrame: (pcmBuffer: ArrayBufferLike) => void) {
  const { createContext, getContext } = useAudioContext();

  const nodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const start = async () => {
    const ctx = await createContext();

    streamRef.current = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    });

    const source = ctx.createMediaStreamSource(streamRef.current);
    const node = new AudioWorkletNode(ctx, "pcm-processor");
    let warmupFrames = 0;

    node.port.onmessage = e => {
      if (++warmupFrames < 10) return; 
      const pcm = e.data as Int16Array;
      onFrame(pcm.buffer);
    };

    source.connect(node);
    node.connect(ctx.destination);

    nodeRef.current = node;
  };

  const stop = async () => {
    if (nodeRef.current) {
      nodeRef.current.disconnect();
      nodeRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
  };

  return { start, stop };
}


