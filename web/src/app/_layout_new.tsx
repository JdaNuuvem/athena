"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import "./globals.css";

const NAV_ITEMS: Array<{href:string;label:string;icon:string}> = [
  { href: "/dashboard", label: "Dashboard", icon: "⊞" },
  { href: "/cadastros", label: "Cadastros", icon: "📋" },
  { href: "/produtos", label: "Produtos", icon: "📦" },
  { href: "/estoque", label: "Estoque", icon: "🏭" },
  { href: "/compras", label: "Compras", icon: "🛒" },
  { href: "/vendas", label: "Vendas", icon: "💰" },
  { href: "/pdv", label: "PDV", icon: "🛍️" },
  { href: "/financeiro", label: "Financeiro", icon: "💳" },
  { href: "/fiscal", label: "Fiscal", icon: "📄" },
  { href: "/crm", label: "CRM", icon: "👥" },
  { href: "/atendimento", label: "Atendimento", icon: "💬" },
  { href: "/producao", label: "Produção", icon: "⚙️" },
  { href: "/rh", label: "RH", icon: "👤" },
  { href: "/bi", label: "BI", icon: "📊" },
  { href: "/documentos", label: "Documentos", icon: "📁" },
  { href: "/automacoes", label: "Automações", icon: "🔄" },
  { href: "/relatorios", label: "Relatórios", icon: "📈" },
];