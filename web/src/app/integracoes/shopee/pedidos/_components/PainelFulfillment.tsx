"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type ShopeeFulfillmentStatus } from "@/lib/api";

interface Props {
  orderSn: string;
  lojaId: number;
}

type Etapa = "" | "documento" | "despacho";

export default function PainelFulfillment({ orderSn, lojaId }: Props) {
  const [status, setStatus] = useState<ShopeeFulfillmentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [idBlingManual, setIdBlingManual] = useState("");
  const [processando, setProcessando] = useState<Etapa | "vincular" | "nota" | "">("");
  const [statusDocumento, setStatusDocumento] = useState<"" | "PROCESSING" | "READY" | "FAILED">("");

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeeFulfillmentStatus(orderSn, lojaId);
      if (r.erro) setErro(r.erro);
      else setStatus(r);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar fulfillment");
    } finally {
      setLoading(false);
    }
  }, [orderSn, lojaId]);
  useEffect(() => { carregar(); }, [carregar]);

  const vincular = async (idManual?: number) => {
    setProcessando("vincular");
    setErro(null);
    setMsg(null);
    try {
      const r = await api.shopeeFulfillmentVincularBling(orderSn, lojaId, idManual);
      if (r.erro) { setErro(r.erro); return; }
      setMsg("Pedido vinculado ao Bling");
      setIdBlingManual("");
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao vincular");
    } finally {
      setProcessando("");
    }
  };

  const emitirNota = async () => {
    if (!confirm("Emitir a NF-e deste pedido no Bling? Essa ação é fiscal e não pode ser desfeita pelo painel.")) return;
    setProcessando("nota");
    setErro(null);
    setMsg(null);
    try {
      const r = await api.shopeeFulfillmentEmitirNota(orderSn, lojaId);
      if (r.erro) { setErro(r.erro); return; }
      setMsg(`Nota fiscal #${r.bling_nota_fiscal_id} emitida`);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao emitir nota fiscal");
    } finally {
      setProcessando("");
    }
  };

  const baixarNotaPdf = async () => {
    setErro(null);
    try {
      const r = await api.shopeeFulfillmentNotaPdf(orderSn, lojaId);
      if ("error" in r) { setErro(r.error); return; }
      const url = URL.createObjectURL(r.blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao baixar PDF da nota");
    }
  };

  const gerarEtiqueta = async () => {
    setProcessando("documento");
    setErro(null);
    setMsg(null);
    try {
      const orderList = [{ order_sn: orderSn }];
      const param = await api.shopeeLogisticaCriarDocumento(lojaId, orderList);
      if (param.error) { setErro(param.error); return; }
      setMsg("Etiqueta em processamento — clique em \"Verificar status\" em alguns segundos");
      setStatusDocumento("PROCESSING");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao gerar etiqueta");
    } finally {
      setProcessando("");
    }
  };

  const verificarStatusDocumento = async () => {
    setErro(null);
    try {
      const orderList = [{ order_sn: orderSn }];
      const r = await api.shopeeLogisticaStatusDocumento(lojaId, orderList);
      if (r.error) { setErro(r.error); return; }
      const resultado = r.response?.result_list?.[0];
      setStatusDocumento((resultado?.status as "READY" | "FAILED" | "PROCESSING") || "");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao verificar status da etiqueta");
    }
  };

  const baixarEtiqueta = async () => {
    setErro(null);
    try {
      const orderList = [{ order_sn: orderSn }];
      const r = await api.shopeeLogisticaBaixarDocumento(lojaId, orderList);
      if ("error" in r) { setErro(r.error); return; }
      const url = URL.createObjectURL(r.blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao baixar etiqueta");
    }
  };

  const despachar = async () => {
    if (!confirm("Despachar este pedido na Shopee agora? Essa ação é irreversível — a Shopee rejeita um novo despacho do mesmo pacote.")) return;
    setProcessando("despacho");
    setErro(null);
    setMsg(null);
    try {
      const param = await api.shopeeLogisticaParametroEnvio(lojaId, orderSn);
      if (param.error) { setErro(param.error); return; }
      const info = param.response as Record<string, unknown> | undefined;
      const metodo = info?.pickup ? "pickup" : info?.dropoff ? "dropoff" : info?.non_integrated ? "non_integrated" : null;
      if (!metodo) { setErro("Nenhum método de envio disponível para este pedido — confira o pedido na Shopee"); return; }
      const packageList = [{ package_number: orderSn, [metodo]: info?.[metodo] }];
      const r = await api.shopeeLogisticaDespachar(lojaId, packageList);
      if (r.error || (r.response?.fail_list?.length ?? 0) > 0) {
        setErro(r.error || "Shopee rejeitou o despacho — confira package_list");
        return;
      }
      await api.shopeeFulfillmentDespacharConfirmar(orderSn, lojaId);
      setMsg("Pedido despachado com sucesso");
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao despachar pedido");
    } finally {
      setProcessando("");
    }
  };

  if (loading) return <p className="text-xs text-neutral-500">Carregando fulfillment...</p>;

  return (
    <div className="border-t border-neutral-800 pt-3 space-y-2">
      <p className="text-neutral-500 uppercase tracking-wider text-[10px] mb-1">Fulfillment — Bling &amp; envio</p>

      {erro && <div className="text-xs px-2 py-1.5 rounded bg-red-950/40 border border-red-900/50 text-red-400">{erro}</div>}
      {msg && <div className="text-xs px-2 py-1.5 rounded bg-emerald-950/40 border border-emerald-900/50 text-emerald-400">{msg}</div>}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        {/* Passo 1: vincular Bling */}
        {!status?.vinculado_bling ? (
          <div className="flex items-center gap-1.5">
            <button onClick={() => vincular()} disabled={processando === "vincular"}
              className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded">
              {processando === "vincular" ? "Buscando..." : "Vincular ao Bling (automático)"}
            </button>
            <span className="text-neutral-600">ou</span>
            <input type="number" value={idBlingManual} onChange={e => setIdBlingManual(e.target.value)}
              placeholder="ID do pedido Bling"
              className="w-32 bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-neutral-200" />
            <button onClick={() => vincular(Number(idBlingManual))} disabled={!idBlingManual || processando === "vincular"}
              className="px-2.5 py-1 bg-neutral-700 hover:bg-neutral-600 disabled:opacity-40 text-neutral-200 rounded">
              Vincular manualmente
            </button>
          </div>
        ) : (
          <span className="px-2 py-0.5 rounded bg-emerald-900/30 text-emerald-400">Bling #{status.bling_pedido_id} vinculado</span>
        )}
      </div>

      {status?.vinculado_bling && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {!status.nota_emitida ? (
            <button onClick={emitirNota} disabled={processando === "nota"}
              className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded">
              {processando === "nota" ? "Emitindo..." : "Emitir Nota Fiscal"}
            </button>
          ) : (
            <>
              <span className="px-2 py-0.5 rounded bg-emerald-900/30 text-emerald-400">NF-e #{status.bling_nota_fiscal_id} emitida</span>
              <button onClick={baixarNotaPdf} className="px-2.5 py-1 bg-neutral-700 hover:bg-neutral-600 text-neutral-200 rounded">
                Baixar PDF da nota
              </button>
            </>
          )}
        </div>
      )}

      {status?.nota_emitida && !status.despachado && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button onClick={gerarEtiqueta} disabled={processando === "documento"}
            className="px-2.5 py-1 bg-neutral-700 hover:bg-neutral-600 disabled:opacity-50 text-neutral-200 rounded">
            {processando === "documento" ? "Gerando..." : "Gerar etiqueta de envio"}
          </button>
          {statusDocumento && (
            <>
              <button onClick={verificarStatusDocumento} className="px-2.5 py-1 bg-neutral-700 hover:bg-neutral-600 text-neutral-200 rounded">
                Verificar status
              </button>
              <span className={statusDocumento === "READY" ? "text-emerald-400" : statusDocumento === "FAILED" ? "text-red-400" : "text-amber-400"}>
                {statusDocumento === "READY" ? "Etiqueta pronta" : statusDocumento === "FAILED" ? "Falhou" : "Processando..."}
              </span>
              {statusDocumento === "READY" && (
                <button onClick={baixarEtiqueta} className="px-2.5 py-1 bg-neutral-700 hover:bg-neutral-600 text-neutral-200 rounded">
                  Baixar etiqueta (PDF)
                </button>
              )}
            </>
          )}
          <button onClick={despachar} disabled={processando === "despacho"}
            className="px-2.5 py-1 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white rounded">
            {processando === "despacho" ? "Despachando..." : "Despachar pedido"}
          </button>
        </div>
      )}

      {status?.despachado && (
        <span className="text-xs px-2 py-0.5 rounded bg-emerald-900/30 text-emerald-400">
          Despachado {status.despachado_em ? new Date(status.despachado_em).toLocaleString("pt-BR") : ""}
        </span>
      )}
    </div>
  );
}
