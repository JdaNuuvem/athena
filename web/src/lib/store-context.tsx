"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { api } from "@/lib/api";

export interface LojaInfo {
  id: number;
  nome: string;
  ativa: boolean;
  bling_id?: number | null;
}

interface StoreContextValue {
  lojaId: string;
  lojas: LojaInfo[];
  setLojaId: (id: string) => void;
}

const StoreContext = createContext<StoreContextValue>({
  lojaId: "todas",
  lojas: [],
  setLojaId: () => {},
});

export function StoreProvider({ children }: { children: ReactNode }) {
  const [lojaId, setLojaId] = useState<string>(() => {
    if (typeof window === "undefined") return "todas";
    return localStorage.getItem("loja") || "todas";
  });
  const [lojas, setLojas] = useState<LojaInfo[]>([]);

  useEffect(() => {
    api.lojasManage().then(r => {
      const list = r.lojas as LojaInfo[];
      if (list.length === 0) {
        api.lojasSyncBling().then(() =>
          api.lojasManage().then(r2 => setLojas(r2.lojas as LojaInfo[])).catch(() => {})
        ).catch(() => {});
      } else {
        setLojas(list);
      }
    }).catch(() => {});
  }, []);

  const handleSetLoja = useCallback((id: string) => {
    setLojaId(id);
    localStorage.setItem("loja", id);
    window.dispatchEvent(new Event("loja-changed"));
  }, []);

  useEffect(() => {
    const handler = () => {
      setLojaId(localStorage.getItem("loja") || "todas");
    };
    window.addEventListener("loja-changed", handler);
    return () => window.removeEventListener("loja-changed", handler);
  }, []);

  return (
    <StoreContext.Provider value={{ lojaId, lojas, setLojaId: handleSetLoja }}>
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  return useContext(StoreContext);
}
