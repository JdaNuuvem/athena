// ── Tipos de componentes UI (SSOT para toda a aplicação) ──

import type { ReactNode } from "react";

export interface KpiMetric {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}

export interface SubmenuItem {
  href: string;
  label: string;
  color: string;
}

export interface TabOption {
  key: string;
  label: string;
}

export interface Column<T = Record<string, unknown>> {
  key: string;
  label: string;
  align?: "left" | "center" | "right";
  render?: (value: unknown, row: T, index: number) => ReactNode;
}

export const STATUS_BADGE_VARIANTS = {
  success: "bg-emerald-900/30 text-emerald-400",
  danger: "bg-red-900/30 text-red-400",
  warning: "bg-amber-900/30 text-amber-400",
  neutral: "bg-neutral-700 text-neutral-400",
} as const;

export type StatusBadgeVariant = keyof typeof STATUS_BADGE_VARIANTS;

export interface SubItem {
  key: string;
  label: string;
  children?: SubItem[];
}
