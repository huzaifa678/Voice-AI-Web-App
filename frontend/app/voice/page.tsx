"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStreamingSTT } from "./hooks/useStreamingSST";
import { useAppDispatch } from "@redux/hooks"; 
import { logout } from "@redux/authSlice";

export default function StreamingPage() {

  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const router = useRouter();
  const dispatch = useAppDispatch();

  useEffect(() => {
    setAccessToken(localStorage.getItem("access-token"));
    setRefreshToken(localStorage.getItem("refresh-token"));
  }, []);

  console.log(accessToken)
  console.log(refreshToken)
  const {start, stop, transcript, llmResponse,} = useStreamingSTT(
    "ws://localhost:8000/ws/audio/",
    accessToken || undefined
  );

  const handleLogout = () => {
    dispatch(logout())
    router.push("/login");
  };

  return (
    <div className="flex flex-col items-center gap-4 p-6">
      <div className="self-end">
        <button
          onClick={handleLogout}
          className="bg-gray-500 text-white px-3 py-1 rounded text-sm"
        >
          Logout
        </button>
      </div>

      <div className="flex gap-2">
        <button
          onClick={start}
          className="bg-blue-500 text-white px-4 py-2 rounded"
        >
          Start
        </button>

        <button
          onClick={stop}
          className="bg-red-500 text-white px-4 py-2 rounded"
        >
          Stop
        </button>
      </div>

      {transcript && (
        <div className="w-full max-w-xl p-4 bg-gray-100 rounded">
          <h3 className="font-semibold mb-1">Transcript</h3>
          <p>{transcript}</p>
        </div>
      )}

      {llmResponse && (
        <div className="w-full max-w-xl p-4 bg-green-100 rounded">
          <h3 className="font-semibold mb-1">LLM Response</h3>
          <p>{llmResponse}</p>
        </div>
      )}
    </div>
  );
}

