"use client";

import { useState, useEffect } from "react";
import { Operador } from "./types";
import { SangriaSuprimentoModal } from "./SangriaSuprimentoModal";
import { api } from "@/lib/api";

export function CaixaTab({ operador, operadorSenha, caixa, onAbrirCaixa, onFecharCaixa }: {
  operador: Operador;
  operadorSenha: string;
  caixa: any;
  onAbrirCaixa: (saldoInicial: number, lojaId: number | null) => Promise<void>;
  onFecharCaixa: () => void;
}) {
  const [saldoInicial, setSaldoInicial] = useState(0);
  const [modalTipo, setModalTipo] = useState<"sangria" | "suprimento" | null>(null);
  const [msg, setMsg] = useState("");
  const [lojasFisicas, setLojasFisicas] = useState<{ id: number; nome: string }[]>([]);
  const [lojaSelecionada, setLojaSelecionada] = useState<string>("");

  useEffect(() => {
    api.lojasManage().then((r) => {
      const fisicas = ((r.lojas ?? []) as unknown as Record<string, unknown>[])
        .filter((l) => l.tipo === "fisica")
        .map((l) => ({ id: l.id as number, nome: l.nome as string }));
      setLojasFisicas(fisicas);
    }).catch(() => {});
  }, []);

  const handleConcluido = (texto: string) => {
    setModalTipo(null);
    setMsg(texto);
    setTimeout(() => setMsg(""), 4000);
  };

  return (
    <div className="p-4 space-y-3">
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 max-w-md">
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Caixa</h3>
        {msg && <p className="text-xs text-emerald-400 mb-2">{msg}</p>}
        {caixa ? (
          <div className="space-y-2 text-sm">
            <p className="text-neutral-400">Status: <span className="text-emerald-400">Aberto</span></p>
            <p className="text-neutral-400">Saldo inicial: <span className="text-neutral-200">R$ {(caixa.saldo_inicial || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span></p>
            <div className="flex gap-2 pt-1">
              <button onClick={() => setModalTipo("sangria")} className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs rounded-lg">Sangria</button>
              <button onClick={() => setModalTipo("suprimento")} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white text-xs rounded-lg">Suprimento</button>
            </div>
            <button onClick={onFecharCaixa} className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500">Fechar Caixa</button>
          </div>
        ) : (
          <div className="space-y-2">
            <select value={lojaSelecionada} onChange={e => setLojaSelecionada(e.target.value)} className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200">
              <option value="">Selecione a loja</option>
              {lojasFisicas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
            </select>
            <input type="number" value={saldoInicial} onChange={e => setSaldoInicial(Number(e.target.value))} placeholder="Saldo inicial" className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200" />
            <button onClick={() => onAbrirCaixa(saldoInicial, lojaSelecionada ? Number(lojaSelecionada) : null)} className="w-full py-2 bg-emerald-600 text-white text-sm rounded-lg">Abrir Caixa</button>
          </div>
        )}
      </div>

      {modalTipo && caixa && (
        <SangriaSuprimentoModal
          tipo={modalTipo}
          caixaId={caixa.id}
          operador={operador}
          operadorSenha={operadorSenha}
          onClose={() => setModalTipo(null)}
          onConcluido={handleConcluido}
        />
      )}
    </div>
  );
}
