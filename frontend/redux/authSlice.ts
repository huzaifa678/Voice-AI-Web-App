import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: { username: string } | null;
}

const initialState: AuthState = {
  accessToken: null,
  refreshToken: null,
  user: null,
};

export const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials: (
      state,
      action: PayloadAction<{ access: string | null; refresh: string; user?: any }>
    ) => {
      state.accessToken = action.payload.access;
      state.refreshToken = action.payload.refresh;
      if (action.payload.user) state.user = action.payload.user;

      localStorage.setItem("access-token", state.accessToken || "");
      localStorage.setItem("refresh-token", state.refreshToken);
    },
    logout: (state) => {
      state.accessToken = null;
      state.refreshToken = null;
      state.user = null;
    },
  },
});

export const { setCredentials, logout } = authSlice.actions;
export default authSlice.reducer;
