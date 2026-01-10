import api from "@lib/api.interceptor";

export const loginUser = async (username: string, password: string) => {
  const res = await api.post("/auth/login/", { username, password });
  return {
    access: res.data.access,
    refresh: res.data.refresh,
    user: { username },
  };
};
