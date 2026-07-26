"use client";

import { useState, useEffect, useCallback } from "react";

interface OperadorPDV {
  id: number;
  nome: string;
  role: string;
  ativo: boolean;
  desconto_maximo_percent: number;
}

export default function OperadoresPDVPage() {
  const [operadores, setOperadores] = useState<OperadorPDV[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [pinModal, setPinModal] = useState<{ id: number; nome: string } | null>(null);
  const [pinValor, setPinValor] = useState("");
  const [codigoGerado, setCodigoGerado] = useState<{ nome: string; codigo: string } | null>(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/pdv/operadores").then(res => res.json());
      setOperadores(r.data || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const salvarPin = async () => {
    if (!pinModal) return;
    if (!/^\d{4,6}$/.test(pinValor)) { setErro("PIN deve ter de 4 a 6 dígitos numéricos"); return; }
    setErro(""); setSucesso("");
    try {
      const r = await fetch(`/api/pdv/operadores/${pinModal.id}/pin`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: pinValor }),
      }).then(res => res.json());
      if (r.error) { setErro(r.error); return; }
      setSucesso(`PIN definido para ${pinModal.nome}.`);
      setPinModal(null); setPinValor("");
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao definir PIN"); }
  };

  const gerarCodigoBarras = async (op: OperadorPDV) => {
    setErro(""); setSucesso("");
    try {
      const r = await fetch(`/api/pdv/operadores/${op.id}/codigo-barras`, { method: "POST" }).then(res => res.json());
      if (r.error) { setErro(r.error); return; }
      setCodigoGerado({ nome: op.nome, codigo: r.codigo_barras });
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao gerar código de barras"); }
  };

  const gerencial = (role: string) => ["gerente", "admin"].includes(role.toLowerCase());

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Operadores do PDV</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Defina PIN e gere código de barras (crachá) para operadores Gerente/Admin — usados para autorizar ações sensíveis no caixa sem precisar de logout/login.
        </p>
      </div>

      {erro && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>}
      {sucesso && <div className="text-emerald-400 text-sm bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-4 py-3">{sucesso}</div>}

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <div className="overflow-x-auto border border-neutral-800 rounded-lg">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-neutral-900 text-neutral-400 text-left">
                <th className="px-3 py-2 font-medium">Nome</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium text-right">Desconto máx.</th>
                <th className="px-3 py-2 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {operadores.map(op => (
                <tr key={op.id} className="border-t border-neutral-800 text-neutral-300">
                  <td className="px-3 py-2 font-medium text-neutral-200">{op.nome}</td>
                  <td className="px-3 py-2 capitalize">{op.role}</td>
                  <td className="px-3 py-2 text-right numeric">{op.desconto_maximo_percent}%</td>
                  <td className="px-3 py-2">
                    {gerencial(op.role) ? (
                      <div className="flex gap-2">
                        <button
                          onClick={() => { setPinModal({ id: op.id, nome: op.nome }); setPinValor(""); }}
                          className="text-[10px] bg-indigo-600 hover:bg-indigo-500 text-white px-2 py-1 rounded-lg"
                        >
                          Definir PIN
                        </button>
                        <button
                          onClick={() => gerarCodigoBarras(op)}
                          className="text-[10px] bg-sky-600 hover:bg-sky-500 text-white px-2 py-1 rounded-lg"
                        >
                          Gerar código de barras
                        </button>
                      </div>
                    ) : (
                      <span className="text-[10px] text-neutral-600">PIN/crachá só para Gerente/Admin</span>
                    )}
                  </td>
                </tr>
              ))}
              {operadores.length === 0 && (
                <tr><td colSpan={4} className="px-3 py-8 text-center text-neutral-500">Nenhum operador cadastrado</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {pinModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setPinModal(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-80" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Definir PIN — {pinModal.nome}</h3>
            <input
              type="password" inputMode="numeric" maxLength={6} autoFocus
              value={pinValor}
              onChange={e => setPinValor(e.target.value.replace(/\D/g, ""))}
              placeholder="PIN de 4 a 6 dígitos"
              onKeyDown={e => e.key === "Enter" && salvarPin()}
              className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200 mb-3"
            />
            <div className="flex gap-2">
              <button onClick={() => setPinModal(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={salvarPin} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Salvar</button>
            </div>
          </div>
        </div>
      )}

      {codigoGerado && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCodigoGerado(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Código gerado — {codigoGerado.nome}</h3>
            <p className="text-xs text-amber-400 bg-amber-950/30 border border-amber-900/50 rounded-lg px-3 py-2 mb-3">
              Anote ou imprima este código agora — ele não pode ser recuperado depois (se perder, gere um novo).
            </p>
            <div className="bg-neutral-950 border border-neutral-700 rounded-lg px-4 py-3 text-center font-mono text-lg text-emerald-400 tracking-wider mb-3">
              {codigoGerado.codigo}
            </div>
            <p className="text-[10px] text-neutral-500 mb-3">
              Gere um código de barras (Code128) a partir deste texto e imprima numa etiqueta/crachá. O leitor de código de barras vai "digitar" esse valor no campo de bipagem do PDV.
            </p>
            <button onClick={() => setCodigoGerado(null)} className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Fechar</button>
          </div>
        </div>
      )}
    </div>
  );
}
