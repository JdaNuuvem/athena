"use client";
import React, { createContext, useContext, useState, useEffect, type ReactNode } from "react";

type AuthUser = { id: string; name: string; role: string; roles?: string[] };

type AuthContextType = {
  user: AuthUser | null;
  permissions: string[];
  hasPermission: (code: string) => boolean;
  loading: boolean;
  login: (token: string, user: AuthUser, perms: string[]) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
  user: null, permissions: [], hasPermission: () => false, loading: true,
  login: () => {}, logout: () => {},
});

const fetchMe = (): Promise<{ id: string; name: string; role: string; roles: string[]; permissions: string[] } | null> => {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (!token) return Promise.resolve(null);
  return fetch("/api/auth/me", { headers: { Authorization: `Bearer ${token}` } })
    .then(r => r.ok ? r.json() : null)
    .catch(() => null);
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe().then(d => {
      if (d) {
        setUser({ id: d.id, name: d.name, role: d.role, roles: d.roles });
        setPermissions(d.permissions || []);
      }
    }).finally(() => setLoading(false));
  }, []);

  const hasPermission = (code: string) => {
    if (permissions.length === 0) return false;
    return permissions.includes(code);
  };

  const login = (token: string, u: AuthUser, perms: string[]) => {
    localStorage.setItem("token", token);
    setUser(u);
    setPermissions(perms);
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
    setPermissions([]);
    window.location.href = "/login";
  };

  return React.createElement(AuthContext.Provider, {
    value: { user, permissions, hasPermission, loading, login, logout },
  }, children);
}

export function useAuth() { return useContext(AuthContext); }

export function useHasPermission(code: string) {
  const { hasPermission } = useContext(AuthContext);
  return hasPermission(code);
}

export function Can({ permission, children, fallback = null }: { permission: string; children: ReactNode; fallback?: ReactNode }) {
  const { hasPermission, loading } = useContext(AuthContext);
  if (loading) return null;
  if (!hasPermission(permission)) return fallback as ReactNode;
  return children as ReactNode;
}
