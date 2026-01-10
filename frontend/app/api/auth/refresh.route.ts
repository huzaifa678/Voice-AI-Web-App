import api from "@lib/api.interceptor";

export const refreshAccessToken = async (refreshToken: string) => {
  const res = await api.post("/auth/refresh/", { refresh: refreshToken });
  return res.data.access;
};
