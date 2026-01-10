import api from "@lib/api.interceptor";

export const registerUser = async (
  username: string,
  email: string,
  password: string
) => {
  const res = await api.post("/auth/register/", { username, email, password });
  return res.data;
};
