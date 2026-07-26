"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store-context";

interface ProdutoEncontrado {
  sku: string;
  descricao: string;
  codigo_barras: string | null;
  estoque_total: number;
}

interface HistoricoItem {
  sku: string;
  descricao: string;
  quantidade: number;
  hora: string;
}

export default function EntradaEstoquePage() {
  const { lojaId, lojas } = useStore();
  const [loja, setLoja] = useState("");
  const [codigo, setCodigo] = useState("");
  const [produto, setProduto] = useState<ProdutoEncontrado | null>(null);
  const [quantidade, setQuantidade] = useState("1");
  const [buscando, setBuscando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [erro, setErro] = useState("");
  const [historico, setHistorico] = useState<HistoricoItem[]>([]);
  const codigoRef = useRef<HTMLInputElement>(null);
  const qtdRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!loja && lojas.length > 0) {
      const atual = lojas.find(l => String(l.id) === lojaId);
      setLoja(atual?.nome || lojas[0].nome);
    }
  }, [lojas, lojaId, loja]);

  useEffect(() => {
    if (!produto) codigoRef.current?.focus();
    else qtdRef.current?.focus();
  }, [produto]);

  const buscar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!codigo.trim()) return;
    setErro(""); setBuscando(true);
    try {
      const r = await api.estoqueBuscarCodigo(codigo.trim());
      if (r.erro) { setErro(`Produto nao encontrado: ${codigo}`); setCodigo(""); return; }
      setProduto(r);
      setQuantidade("1");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao buscar produto");
    } finally {
      setBuscando(false);
    }
  };

  const confirmar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!produto || !loja) return;
    const qtd = parseFloat(quantidade);
    if (!qtd || qtd <= 0) { setErro("Quantidade invalida"); return; }
    setConfirmando(true); setErro("");
    try {
      const r = await api.estoqueEntrada(produto.sku, loja, qtd, "Entrada via scanner");
      if (r.erro) { setErro(r.erro); return; }
      setHistorico(h => [{
        sku: produto.sku, descricao: produto.descricao, quantidade: qtd,
        hora: new Date().toLocaleTimeString("pt-BR"),
      }, ...h]);
      setProduto(null);
      setCodigo("");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao dar entrada no estoque");
    } finally {
      setConfirmando(false);
    }
  };

  const cancelar = () => {
    setProduto(null);
    setCodigo("");
    setErro("");
  };

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Entrada de Estoque — Scanner</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Use um leitor de codigo de barras USB/Bluetooth (funciona como teclado) ou digite o codigo/SKU manualmente
        </p>
      </div>

      <div className="space-y-1 max-w-xs">
        <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Loja de destino</label>
        <select
          value={loja}
          onChange={e => setLoja(e.target.value)}
          className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
        >
          {lojas.map(l => <option key={l.id} value={l.nome}>{l.nome}</option>)}
        </select>
      </div>

      {erro && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      )}

      {!produto ? (
        <form onSubmit={buscar} className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 space-y-3">
          <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Bipe ou digite o codigo de barras / SKU</label>
          <input
            ref={codigoRef}
            autoFocus
            value={codigo}
            onChange={e => setCodigo(e.target.value)}
            disabled={buscando}
            placeholder="Aguardando leitura..."
            className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-4 py-3 text-lg text-neutral-100 font-mono focus:outline-none focus:border-indigo-500"
          />
          <button type="submit" disabled={buscando || !codigo.trim()} className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
            {buscando ? "Buscando..." : "Buscar"}
          </button>
        </form>
      ) : (
        <form onSubmit={confirmar} className="bg-neutral-900 border border-emerald-800 rounded-lg p-6 space-y-4">
          <div>
            <div className="text-xs text-neutral-500">SKU: <span className="font-mono text-neutral-300">{produto.sku}</span></div>
            <div className="text-sm text-neutral-200 font-medium mt-0.5">{produto.descricao}</div>
            <div className="text-xs text-neutral-500 mt-1">Estoque atual: {produto.estoque_total} un</div>
          </div>
          <div className="space-y-1 max-w-[160px]">
            <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Quantidade a adicionar</label>
            <input
              ref={qtdRef}
              type="number" step="1" min="1"
              value={quantidade}
              onChange={e => setQuantidade(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={confirmando} className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
              {confirmando ? "Confirmando..." : "Confirmar Entrada"}
            </button>
            <button type="button" onClick={cancelar} className="text-sm text-neutral-400 hover:text-neutral-200 px-4 py-2">Cancelar</button>
          </div>
        </form>
      )}

      {historico.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-neutral-400 mb-2">Bipados nesta sessao</h2>
          <div className="space-y-1">
            {historico.map((h, i) => (
              <div key={i} className="flex items-center justify-between bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-xs">
                <div>
                  <span className="font-mono text-neutral-400">{h.sku}</span>
                  <span className="text-neutral-300 ml-2">{h.descricao}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-emerald-400 font-medium">+{h.quantidade}</span>
                  <span className="text-neutral-600">{h.hora}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
