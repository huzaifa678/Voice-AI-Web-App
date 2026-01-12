import { store } from "../redux/store";
import { setCredentials, logout } from "../redux/authSlice";
import { api } from "./api.config";
import { refreshAccessToken } from "@/api/auth/refresh.route";
import axios from "axios";

api.interceptors.request.use((config) => {
  const token = store.getState().auth.accessToken;
  if (token && config.headers) config.headers["Authorization"] = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = store.getState().auth.refreshToken;
      if (!refreshToken) {
        store.dispatch(logout());
        return Promise.reject(error);
      }

      try {
        const data = await refreshAccessToken(refreshToken)
        const tokenToUse = data.access;
        store.dispatch(
          setCredentials({ access: tokenToUse, refresh: refreshToken })
        );
        originalRequest.headers["Authorization"] = `Bearer ${tokenToUse}`;
        return api(originalRequest);
      } catch (err) {
        store.dispatch(logout());
        return Promise.reject(err);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
