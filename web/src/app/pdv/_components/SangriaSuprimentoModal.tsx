"use client";

import { useState, useEffect } from "react";
import { Operador } from "./types";
import { AutorizacaoGerencial, type AutorizacaoGerencialValue } from "./AutorizacaoGerencial";

const LABEL_MOTIVO: Record<string, string> = {
  troco: "Troco",
  deposito_banco: "Depósito no banco",
  pagamento_fornecedor: "Pagamento a fornecedor",
  despesa_operacional: "Despesa operacional",
  outro: "Outro",
};

export function SangriaSuprimentoModal({ tipo, caixaId, operador, operadorSenha, onClose, onConcluido }: {
  tipo: "sangria" | "suprimento";
  caixaId: number;
  operador: Operador;
  operadorSenha: string;
  onClose: () => void;
  onConcluido: (msg: string) => void;
}) {
  const [valor, setValor] = useState("");
  const [motivo, setMotivo] = useState("troco");
  const [motivos, setMotivos] = useState<string[]>(Object.keys(LABEL_MOTIVO));
  const [limite, setLimite] = useState(200);
  const [senha, setSenha] = useState("");
  const [autorizacao, setAutorizacao] = useState<AutorizacaoGerencialValue>({ gerente_pin_id: null, pin: "" });
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    fetch("/api/pdv/sangria/limite").then(r => r.json()).then(d => {
      if (d.motivos?.length) setMotivos(d.motivos);
      if (d.limite) setLimite(d.limite);
    }).catch(() => {});
  }, []);

  const confirmar = async () => {
    const v = parseFloat(valor);
    if (!v || v <= 0) { setErro("Informe um valor válido"); return; }
    setEnviando(true); setErro("");
    try {
      const r = await fetch(`/api/pdv/caixa/${caixaId}/${tipo}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          valor: v, motivo, operador: operador.nome, operador_id: operador.id,
          senha: senha || operadorSenha,
          gerente_pin_id: autorizacao.gerente_pin_id, pin: autorizacao.pin,
        }),
      });
      const d = await r.json();
      if (d.error) { setErro(d.error); return; }
      if (d.pendente) {
        onConcluido(`Sangria de R$ ${v.toFixed(2)} ficou pendente de aprovação (acima de R$ ${limite}).`);
      } else {
        onConcluido(`${tipo === "sangria" ? "Sangria" : "Suprimento"} de R$ ${v.toFixed(2)} registrada.`);
      }
    } catch {
      setErro("Erro ao registrar");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-80" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">
          {tipo === "sangria" ? "Sangria (retirar dinheiro)" : "Suprimento (adicionar dinheiro)"}
        </h3>
        {tipo === "sangria" && (
          <p className="text-[10px] text-neutral-500 mb-2">Acima de R$ {limite} exige aprovação de um Gerente/Admin.</p>
        )}
        {erro && <p className="text-red-400 text-xs mb-2">{erro}</p>}
        <div className="space-y-2">
          <input type="number" step="0.01" min={0.01} value={valor} onChange={e => setValor(e.target.value)}
            placeholder="Valor" autoFocus
            className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
          <select value={motivo} onChange={e => setMotivo(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200">
            {motivos.map(m => <option key={m} value={m}>{LABEL_MOTIVO[m] || m}</option>)}
          </select>
          <input type="password" value={senha} onChange={e => setSenha(e.target.value)}
            placeholder="Sua senha"
            className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
          <AutorizacaoGerencial onChange={setAutorizacao} />
          <div className="flex gap-2 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
            <button onClick={confirmar} disabled={enviando}
              className="flex-1 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm rounded-lg">
              {enviando ? "Enviando..." : "Confirmar"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
