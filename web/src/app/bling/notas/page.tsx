"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import { listarBlingNotasLocais, sincronizarBlingNfce, sincronizarBlingNfse } from "@/lib/api";
import type { BlingNotaLocal } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";

const ABAS = [
  { key: "", label: "Todas" },
  { key: "nfe", label: "NF-e" },
  { key: "nfce", label: "NFC-e" },
  { key: "nfse", label: "NFS-e" },
] as const;

export default function BlingNotasPage() {
  const [notas, setNotas] = useState<BlingNotaLocal[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [tipo, setTipo] = useState<string>("");
  const [ambiente, setAmbiente] = useState("producao");

  const carregar = useCallback(async (t: string, amb: string) => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingNotasLocais(t, amb);
    if (r.error) setErro(r.error);
    setNotas(r.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    carregar(tipo, ambiente);
  }, [carregar, tipo, ambiente]);

  // NF-e nao tem rota de sync propria em bling_bp — o sync dela vive no fluxo
  // fiscal (core.fiscal.sincronizar_notas_fiscais_bling). Por isso o botao so'
  // aparece nas abas NFC-e e NFS-e.
  const podeSincronizar = tipo === "nfce" || tipo === "nfse";

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = tipo === "nfce" ? await sincronizarBlingNfce() : await sincronizarBlingNfse();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} notas sincronizadas`);
    setSincronizando(false);
    carregar(tipo, ambiente);
  };

  const total = notas.reduce((s, n) => s + (Number(n.valor_nf) || 0), 0);

  const seletorAmbiente = (
    <select
      value={ambiente}
      onChange={(e) => setAmbiente(e.target.value)}
      className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
    >
      <option value="producao">Produção</option>
      <option value="homologacao">Homologação</option>
      <option value="todos">Todos os ambientes</option>
    </select>
  );

  if (loading && notas.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <div className="flex flex-wrap gap-1 bg-neutral-800 rounded-lg p-1">
        {ABAS.map((aba) => (
          <button
            key={aba.key}
            onClick={() => setTipo(aba.key)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              tipo === aba.key ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {aba.label}
          </button>
        ))}
      </div>

      {podeSincronizar ? (
        <SyncToolbar
          onSync={handleSync}
          sincronizando={sincronizando}
          label={`Sincronizar ${tipo.toUpperCase()}`}
          total={notas.length}
          unidade="notas"
        >
          {seletorAmbiente}
        </SyncToolbar>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {seletorAmbiente}
          <span className="text-xs text-neutral-500 ml-auto">{notas.length} notas</span>
        </div>
      )}

      <div className="text-xs text-neutral-400">
        Valor total: <strong className="text-emerald-400">{fmtBRL(total)}</strong>
      </div>

      {notas.length === 0 ? (
        <EmptyState
          icon="📄"
          title="Nenhuma nota"
          description={
            podeSincronizar
              ? `Sincronize as notas ${tipo.toUpperCase()} do Bling para começar.`
              : "Nenhuma nota sincronizada neste filtro."
          }
          action={podeSincronizar ? { label: "Sincronizar Agora", onClick: handleSync } : undefined}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 w-[90px]">Nº</th>
                <th className="text-left p-3 w-[80px]">Tipo</th>
                <th className="text-left p-3">Contato</th>
                <th className="text-left p-3 w-[100px]">Emissão</th>
                <th className="text-right p-3 w-[120px]">Valor</th>
                <th className="text-center p-3 w-[100px]">Status</th>
                <th className="text-center p-3 w-[110px]">Ambiente</th>
              </tr>
            </thead>
            <tbody>
              {notas.map((n, i) => (
                <tr
                  key={n.id}
                  className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}
                >
                  <td className="p-3 text-indigo-400 font-mono">{n.numero || "—"}</td>
                  <td className="p-3 text-neutral-400 uppercase">{n.tipo_documento}</td>
                  <td className="p-3 text-neutral-200">
                    <div>{n.contato_nome || "—"}</div>
                    {n.chave_acesso && (
                      <div className="text-[10px] text-neutral-600 font-mono truncate max-w-[280px]">
                        {n.chave_acesso}
                      </div>
                    )}
                  </td>
                  <td className="p-3 text-neutral-400">
                    {n.data_emissao ? fmtDataBR(n.data_emissao) : "—"}
                  </td>
                  <td className="p-3 text-right text-neutral-200">
                    {fmtBRL(Number(n.valor_nf) || 0)}
                  </td>
                  <td className="p-3 text-center text-neutral-400">{n.status || "—"}</td>
                  <td className="p-3 text-center text-[10px] text-neutral-500">{n.ambiente}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
