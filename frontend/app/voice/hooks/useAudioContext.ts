import { useRef } from "react";

export function useAudioContext() {
  const ctxRef = useRef<AudioContext | null>(null);

  const getContext = async () => {
    if (!ctxRef.current) {
      const ctx = new AudioContext({ sampleRate: 16000 });
      await ctx.audioWorklet.addModule("/audio/pcm-processor.js");
      ctxRef.current = ctx;
    }
    return ctxRef.current;
  };

  const close = async () => {
    await ctxRef.current?.close();
    ctxRef.current = null;
  };

  return { getContext, close };
}
