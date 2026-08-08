"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { api } from "@/lib/api";

export interface LojaInfo {
  id: number;
  nome: string;
  ativa: boolean;
  bling_id?: number | null;
  tipo?: "fisica" | "virtual";
  shopee_conectado?: boolean;
}

interface StoreContextValue {
  lojaId: string;
  lojas: LojaInfo[];
  setLojaId: (id: string) => void;
  /** Tipo da loja atualmente selecionada — null quando "todas" ou loja sem tipo definido */
  tipoLojaSelecionada: "fisica" | "virtual" | null;
}

const StoreContext = createContext<StoreContextValue>({
  lojaId: "todas",
  lojas: [],
  setLojaId: () => {},
  tipoLojaSelecionada: null,
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

  const tipoLojaSelecionada: "fisica" | "virtual" | null =
    lojaId === "todas" ? null : (lojas.find(l => String(l.id) === lojaId)?.tipo ?? null);

  return (
    <StoreContext.Provider value={{ lojaId, lojas, setLojaId: handleSetLoja, tipoLojaSelecionada }}>
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  return useContext(StoreContext);
}
