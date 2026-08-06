"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

export type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  toggleTheme: () => {},
  setTheme: () => {},
});

// A tag <html> ja' chega com data-theme correto (script inline no <head>,
// antes da hidratacao) — aqui so' lemos o que o DOM ja' tem, sem flash.
function lerThemeInicial(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(lerThemeInicial);

  const applyTheme = useCallback((t: Theme) => {
    setThemeState(t);
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("theme", t);
  }, []);

  const toggleTheme = useCallback(() => {
    applyTheme(theme === "dark" ? "light" : "dark");
  }, [theme, applyTheme]);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme: applyTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

// Grade/eixo dos graficos recharts: props SVG puras (nao passam por CSS),
// entao nao herdam o retheme via --panel-*/--ink-* do globals.css — cada
// grafico resolve a propria cor de linha (semantica, varia por metrica)
// mas reusa este par grade/eixo, identico em todo o app.
export function chartAxisColors(theme: Theme): { grid: string; axis: string } {
  return theme === "dark" ? { grid: "#262626", axis: "#737373" } : { grid: "#e2e8f0", axis: "#64748b" };
}
