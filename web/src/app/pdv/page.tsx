"use client";

import { useState, useEffect, useCallback } from "react";
import { Operador } from "./_components/types";
import { LoginForm } from "./_components/LoginForm";
import { VendaTab } from "./_components/VendaTab";
import { CaixaTab } from "./_components/CaixaTab";
import { FechaModal } from "./_components/FechaModal";
import { HistoricoTab } from "./_components/HistoricoTab";
import { OrcamentosTab } from "./_components/OrcamentosTab";

export default function PDVPage() {
  const [operador, setOperador] = useState<Operador | null>(null);
  const [operadorSenha, setOperadorSenha] = useState("");
  const [loginError, setLoginError] = useState("");
  const [caixa, setCaixa] = useState<any>(null);
  const [tab, setTab] = useState<"venda" | "caixa" | "historico" | "orcamentos">("venda");
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  const [showFechaModal, setShowFechaModal] = useState(false);

  const notify = (text: string, type: "success" | "error" | "info" = "info") => { setMsg({ text, type }); setTimeout(() => setMsg(null), 3000); };

  const loadDashboard = useCallback(async () => {
    try { const r = await fetch("/api/pdv/dashboard"); const d = await r.json(); setCaixa(d.caixa_aberto); } catch {}
  }, []);
  useEffect(() => { if (operador) loadDashboard(); }, [loadDashboard, operador]);

  const handleLogin = async (nome: string, senha: string) => {
    setLoginError("");
    try {
      const r = await fetch("/api/pdv/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome, senha }),
      });
      const d = await r.json();
      if (d.error) { setLoginError(d.error); return; }
      setOperador({ id: d.id, nome: d.nome, role: d.role, desconto_maximo_percent: d.desconto_maximo_percent });
      setOperadorSenha(senha);
    } catch { setLoginError("Erro de conexao"); }
  };

  const handleLogout = () => { setOperador(null); setOperadorSenha(""); setCaixa(null); };

  const abrirCaixa = async (saldoInicial: number) => {
    if (!operador) return;
    try {
      const r = await fetch("/api/pdv/caixa/abrir", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operador: operador.nome, saldo_inicial: saldoInicial,
          operador_id: operador.id, senha: operadorSenha }),
      });
      const d = await r.json();
      if (d.error) { notify(d.error, "error"); return; }
      setCaixa(d); notify("Caixa aberto!", "success");
    } catch { notify("Erro ao abrir caixa", "error"); }
  };

  const handleFecharCaixaClick = () => setShowFechaModal(true);

  const handleCaixaFechada = (result: any) => {
    setShowFechaModal(false);
    setCaixa(null);
    notify(`Caixa fechado. Total vendas: R$ ${result.total_vendas?.toFixed(2)} | Em dinheiro: R$ ${result.vendas_dinheiro?.toFixed(2)} | Diferenca: R$ ${result.diferenca?.toFixed(2)}`, "info");
  };

  if (!operador) {
    return <LoginForm onLogin={handleLogin} error={loginError} />;
  }

  return (
    <div className="h-screen flex flex-col">
      <FechaModal open={showFechaModal} caixa={caixa} operador={operador}
        onClose={() => setShowFechaModal(false)} onFechar={handleCaixaFechada} />

      {/* Top bar */}
      <div className="bg-neutral-900 border-b border-neutral-800 px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-bold text-neutral-200">PDV</h1>
          <span className="text-[10px] text-neutral-500">{operador.nome} ({operador.role})</span>
        </div>
        <div className="flex items-center gap-3">
          {caixa && <span className="text-xs text-emerald-400">Caixa #{caixa.id} aberto</span>}
          <div className="flex gap-1 bg-neutral-800 rounded-lg p-0.5">
            {(["venda", "caixa", "historico", "orcamentos"] as const).map(t => (
              <button key={t} onClick={() => setTab(t)} className={"px-3 py-1 text-xs rounded-md " + (tab === t ? "bg-indigo-600 text-white" : "text-neutral-400")}>
                {t === "venda" ? "Venda" : t === "caixa" ? "Caixa" : t === "historico" ? "Historico" : "Orcamentos"}
              </button>
            ))}
          </div>
          <button onClick={handleLogout} className="text-[10px] text-neutral-500 hover:text-red-400">Sair</button>
        </div>
      </div>

      {msg && (
        <div className={"mx-4 mt-2 text-xs px-3 py-2 rounded-lg border " +
          (msg.type === "success" ? "bg-emerald-900/30 border-emerald-800 text-emerald-400" :
           msg.type === "error" ? "bg-red-900/30 border-red-800 text-red-400" : "bg-indigo-900/30 border-indigo-800 text-indigo-300")}>
          {msg.text}
        </div>
      )}

      {tab === "caixa" && (
        <CaixaTab operador={operador} operadorSenha={operadorSenha} caixa={caixa}
          onAbrirCaixa={abrirCaixa} onFecharCaixa={handleFecharCaixaClick} />
      )}

      {tab === "historico" && <HistoricoTab operador={operador} operadorSenha={operadorSenha} />}

      {tab === "orcamentos" && <OrcamentosTab caixa={caixa} operador={operador} operadorSenha={operadorSenha} onVendaCriada={loadDashboard} />}

      {tab === "venda" && (
        <VendaTab operador={operador} operadorSenha={operadorSenha} caixa={caixa}
          notify={notify} onCaixaChange={loadDashboard} />
      )}
    </div>
  );
}
