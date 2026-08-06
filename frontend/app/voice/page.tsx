"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAppDispatch } from "@redux/hooks";
import { logout } from "@redux/authSlice";
import { useStreamingSST } from "./hooks/useStreamingSST";
import VoiceVisualizer from "../components/VoiceVisualizer";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function StreamingPage() {
  const [accessToken, setAccessToken] = useState<string | null>(null);

  const router = useRouter();
  const dispatch = useAppDispatch();

  useEffect(() => {
    setAccessToken(localStorage.getItem("access-token"));
  }, []);

  const {
    start,
    stop,
    transcript,
    answer,
    analyser,
  } = useStreamingSST(
    "ws://localhost:8000/ws/audio/",
    accessToken ?? undefined
  );

  const handleLogout = () => {
    dispatch(logout());
    router.push("/login");
  };

  return (
    <div className="flex min-h-screen flex-col items-center gap-6 p-8">
      <div className="flex w-full justify-end">
        <button
          onClick={handleLogout}
          className="rounded bg-gray-600 px-4 py-2 text-white hover:bg-gray-700"
        >
          Logout
        </button>
      </div>

      <h1 className="text-3xl font-bold">
        Streaming Speech-to-Text
      </h1>

      <VoiceVisualizer analyser={analyser} />

      <div className="flex gap-4">
        <button
          onClick={start}
          className="rounded bg-blue-600 px-6 py-2 text-white hover:bg-blue-700"
        >
          Start
        </button>

        <button
          onClick={stop}
          className="rounded bg-red-600 px-6 py-2 text-white hover:bg-red-700"
        >
          Stop
        </button>
      </div>

      {transcript && (
        <div className="w-full max-w-3xl rounded-xl border border-blue-200 bg-blue-50 p-5 shadow">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xl">🎤</span>
            <h2 className="font-semibold text-blue-700">
              You
            </h2>
          </div>

          <p className="whitespace-pre-wrap break-words text-gray-800">
            {transcript}
          </p>
        </div>
      )}

      {answer && (
        <div className="w-full max-w-3xl rounded-xl border border-green-200 bg-green-50 p-5 shadow">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-xl">🤖</span>
            <h2 className="font-semibold text-green-700">
              Assistant
            </h2>
          </div>

          <div className="prose prose-slate max-w-none overflow-x-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {answer}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
