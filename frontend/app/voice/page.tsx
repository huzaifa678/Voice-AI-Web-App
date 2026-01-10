"use client";

import { useStreamingSTT } from "./hooks/useStreamingSST"; 
import { useSelector } from "react-redux";
import { RootState } from "@redux/store"; 

export default function StreamingPage() {
  const accessToken = useSelector((state: RootState) => state.auth.accessToken);

  const { start, stop } = useStreamingSTT(
    "ws://localhost:8000/ws/audio/",
    accessToken || "" 
  );

  return (
    <div className="flex flex-col items-center justify-center gap-2">
      <button onClick={start} className="bg-blue-500 text-white p-2 rounded">
        Start
      </button>
      <button onClick={stop} className="bg-red-500 text-white p-2 rounded">
        Stop
      </button>
    </div>
  );
}

