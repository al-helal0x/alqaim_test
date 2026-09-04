"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { clearTokens, decodeTokenPayload, getAccessToken, setTokens } from "@/api-client/auth-storage";
import type { TokenResponse } from "@/api-client/types";

type AuthState = {
  isAuthenticated: boolean;
  isLoading: boolean;
  companyId: string | null;
  userId: string | null;
  login: (tokens: TokenResponse) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [companyId, setCompanyId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      const payload = decodeTokenPayload(token);
      setCompanyId((payload?.company_id as string) ?? null);
      setUserId((payload?.sub as string) ?? null);
    }
    setIsLoading(false);
  }, []);

  function login(tokens: TokenResponse) {
    setTokens(tokens.access_token, tokens.refresh_token);
    const payload = decodeTokenPayload(tokens.access_token);
    setCompanyId((payload?.company_id as string) ?? null);
    setUserId((payload?.sub as string) ?? null);
  }

  function logout() {
    clearTokens();
    setCompanyId(null);
    setUserId(null);
    router.push("/login");
  }

  return (
    <AuthContext.Provider
      value={{ isAuthenticated: !!companyId, isLoading, companyId, userId, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth يجب أن يُستخدم داخل AuthProvider");
  return ctx;
}
