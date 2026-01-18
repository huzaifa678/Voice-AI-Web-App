import { useRef } from "react";

export function useAudioContext() {
  const ctxRef = useRef<AudioContext | null>(null);

  const createContext = async () => {
    if (ctxRef.current) {
      await ctxRef.current.close();
      ctxRef.current = null;
    }

    const ctx = new AudioContext({ sampleRate: 16000 });
    await ctx.audioWorklet.addModule("/audio/pcm-processor.js");

    console.log("AudioContext created, sampleRate =", ctx.sampleRate);

    ctxRef.current = ctx;
    return ctx;
  };

  const getContext = () => {
    if (!ctxRef.current) {
      throw new Error("AudioContext not initialized. Call createContext first.");
    }
    return ctxRef.current;
  };

  const closeContext = async () => {
    if (ctxRef.current) {
      await ctxRef.current.close();
      ctxRef.current = null;
      console.log("AudioContext closed");
    }
  };

  return { createContext, getContext, closeContext };
}

