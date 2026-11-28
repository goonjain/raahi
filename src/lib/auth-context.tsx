import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type AuthUser } from "./api";

type AuthResult = {
  ok: boolean;
  user?: AuthUser;
  error?: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  refreshUser: () => Promise<AuthUser | null>;
  login: (email: string, password: string) => Promise<AuthResult>;
  signup: (name: string, email: string, password: string) => Promise<AuthResult>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    setLoading(true);
    const res = await api.getMe();
    const nextUser = res.data?.user ?? null;
    setUser(nextUser);
    setLoading(false);
    return nextUser;
  }, []);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string): Promise<AuthResult> => {
    const res = await api.login({ email, password });
    if (res.error || !res.data?.user) {
      return { ok: false, error: res.error || "Sign in failed." };
    }
    setUser(res.data.user);
    return { ok: true, user: res.data.user };
  }, []);

  const signup = useCallback(async (name: string, email: string, password: string): Promise<AuthResult> => {
    const res = await api.signup({ name, email, password });
    if (res.error || !res.data?.user) {
      return { ok: false, error: res.error || "Account creation failed." };
    }
    setUser(res.data.user);
    return { ok: true, user: res.data.user };
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

const FALLBACK_AUTH: AuthContextValue = {
  user: null,
  loading: false,
  refreshUser: async () => null,
  login: async () => ({ ok: false, error: "AuthProvider not mounted" }),
  signup: async () => ({ ok: false, error: "AuthProvider not mounted" }),
  logout: async () => {},
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  return ctx ?? FALLBACK_AUTH;
}

