"use client";

import { useEffect, useRef } from "react";

interface Props {
  analyser: AnalyserNode | null;
}

export default function VoiceVisualizer({ analyser }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;

    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    if (!ctx) return;

    const BAR_COUNT = 40;

    const data = analyser
      ? new Uint8Array(analyser.frequencyBinCount)
      : null;

    let animationFrame: number;

    const draw = () => {
      animationFrame = requestAnimationFrame(draw);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const center = canvas.height / 2;
      const barWidth = 8;
      const gap = 8;

      for (let i = 0; i < BAR_COUNT; i++) {
        let height = 10;

        if (analyser && data) {
          analyser.getByteFrequencyData(data);

          height = Math.max(
            8,
            (data[i] ?? 0) * 0.8
          );
        }

        const x = i * (barWidth + gap);

        ctx.fillStyle = analyser
          ? "#2563eb"
          : "#374151";

        ctx.beginPath();

        ctx.roundRect(
          x,
          center - height / 2,
          barWidth,
          height,
          10
        );

        ctx.fill();
      }
    };

    draw();

    return () => {
      cancelAnimationFrame(animationFrame);
    };
  }, [analyser]);

  return (
    <canvas
      ref={canvasRef}
      width={700}
      height={120}
      className="w-full max-w-xl rounded-xl bg-gray-900"
    />
  );
}