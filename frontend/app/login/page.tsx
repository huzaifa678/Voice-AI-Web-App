"use client";

import { useState } from "react";
import { useAppDispatch } from "@redux/hooks"; 
import { setCredentials } from "@redux/authSlice";
import { useRouter } from "next/navigation";
import { loginUser } from "@/api/auth/login.route";

export default function LoginPage() {
  const dispatch = useAppDispatch();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const tokens = await loginUser(username, password); // just fetch API
      dispatch(setCredentials(tokens)); // hook inside client component
      router.push("/voice");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Login failed");
    }
  };

  const goToRegister = () => {
    router.push("/register");
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-2xl mb-4">Login</h1>
      <form onSubmit={handleLogin} className="flex flex-col gap-2 w-80">
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="border p-2 rounded"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="border p-2 rounded"
        />
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button type="submit" className="bg-blue-500 transition duration-300 hover:bg-blue-700 text-white p-2 rounded mt-2">
          Login
        </button>
        <button
          type="button" 
          onClick={goToRegister}
          className="bg-green-500 transition duration-300 hover:bg-green-700 text-white p-2 rounded mt-2"
        >
          Register if new
        </button>
      </form>
    </div>
  );
}
