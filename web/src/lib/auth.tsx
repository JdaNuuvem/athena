"use client";
import React, { createContext, useContext, useState, useEffect, type ReactNode } from "react";

type AuthContextType = {
  user: { name: string; role: string; user_id?: number } | null;
  permissoes: string[];
  temPermissao: (codigo: string) => boolean;
  carregando: boolean;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
  user: null, permissoes: [], temPermissao: () => false, carregando: true,
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthContextType["user"]>(null);
  const [permissoes, setPermissoes] = useState<string[]>([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    fetch("/api/me", { credentials: "include" })
      .then(r => r.json())
      .then(d => {
        if (!d.error) {
          setUser({ name: d.name, role: d.role, user_id: d.user_id });
          setPermissoes(d.permissoes || []);
        }
      })
      .catch(() => {})
      .finally(() => setCarregando(false));
  }, []);

  const temPermissao = (codigo: string) => {
    if (permissoes.includes("*")) return true;
    return permissoes.includes(codigo);
  };

  const logout = () => {
    fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    localStorage.removeItem("token"); localStorage.removeItem("user");
    setUser(null); setPermissoes([]);
    window.location.href = "/login";
  };

  return React.createElement(AuthContext.Provider, { value: { user, permissoes, temPermissao, carregando, logout } }, children);
}

export function useAuth() { return useContext(AuthContext); }

export function usePermissao(codigo: string) {
  const { temPermissao } = useContext(AuthContext);
  return temPermissao(codigo);
}

export function Permitido({ permissao, children, fallback = null }: { permissao: string; children: ReactNode; fallback?: ReactNode }) {
  const { temPermissao, carregando } = useContext(AuthContext);
  if (carregando) return null;
  if (!temPermissao(permissao)) return fallback as any;
  return children as any;
}
