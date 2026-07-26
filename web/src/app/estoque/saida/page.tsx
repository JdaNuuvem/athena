"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store-context";
import { useAuth } from "@/lib/auth";

interface ProdutoEncontrado {
  sku: string;
  descricao: string;
  codigo_barras: string | null;
  estoque_total: number;
}

const LABEL_MOTIVO: Record<string, string> = {
  quebra: "Quebra",
  perda: "Perda",
  devolucao_fornecedor: "Devolução ao fornecedor",
  uso_interno: "Uso interno / consumo",
  furto_identificado: "Furto identificado",
  ajuste_inventario: "Ajuste de inventário",
  outro: "Outro",
};

const VELOCIDADE_BIPE_MS_POR_CHAR = 40;

export default function SaidaEstoquePage() {
  const { lojaId, lojas } = useStore();
  const { user } = useAuth();
  const podeDigitarManual = ["gerente", "admin"].includes((user?.role || "").toLowerCase());

  const [loja, setLoja] = useState("");
  const [motivo, setMotivo] = useState("quebra");
  const [motivos, setMotivos] = useState<string[]>(Object.keys(LABEL_MOTIVO));
  const [limite, setLimite] = useState(10);
  const [codigo, setCodigo] = useState("");
  const [produto, setProduto] = useState<ProdutoEncontrado | null>(null);
  const [quantidade, setQuantidade] = useState("1");
  const [buscando, setBuscando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const codigoRef = useRef<HTMLInputElement>(null);
  const qtdRef = useRef<HTMLInputElement>(null);
  const inicioDigitacao = useRef<number | null>(null);

  useEffect(() => {
    api.estoqueMotivos().then(r => {
      if (r.saida?.length) setMotivos(r.saida);
      if (r.limite_aprovacao_unidades) setLimite(r.limite_aprovacao_unidades);
    }).catch(() => {});
  }, []);

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

  const handleCodigoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (inicioDigitacao.current === null) inicioDigitacao.current = Date.now();
    setCodigo(e.target.value);
  };

  const buscar = async (e: React.FormEvent) => {
    e.preventDefault();
    const valor = codigo.trim();
    if (!valor) return;

    const decorrido = inicioDigitacao.current ? Date.now() - inicioDigitacao.current : 0;
    const msPorChar = valor.length > 0 ? decorrido / valor.length : 999;
    const foiBipado = msPorChar <= VELOCIDADE_BIPE_MS_POR_CHAR;
    inicioDigitacao.current = null;

    if (!foiBipado && !podeDigitarManual) {
      setErro("Digitacao manual detectada — apenas Gerente/Admin pode digitar o codigo. Use o leitor de codigo de barras.");
      setCodigo("");
      return;
    }

    setErro(""); setBuscando(true);
    try {
      const r = await api.estoqueBuscarCodigo(valor);
      if (r.erro) { setErro(`Produto nao encontrado: ${valor}`); setCodigo(""); return; }
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
    setConfirmando(true); setErro(""); setSucesso("");
    try {
      const r = await api.estoqueSaida(produto.sku, loja, qtd, motivo);
      if (r.erro) { setErro(r.erro); return; }
      if (r.pendente) {
        setSucesso(`Saida de ${qtd} un de ${produto.sku} ficou pendente de aprovacao (acima de ${limite} unidades).`);
      } else {
        setSucesso(`Saida de ${qtd} un de ${produto.sku} aplicada. Estoque atual: ${r.atual}.`);
      }
      setProduto(null);
      setCodigo("");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao registrar saida");
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
        <h1 className="text-lg font-light text-neutral-300">Saida de Estoque</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Saidas acima de {limite} unidades ficam pendentes ate um Gerente/Admin aprovar.{" "}
          {!podeDigitarManual && "Digitacao manual e' restrita a Gerente/Admin."}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 max-w-md">
        <div className="space-y-1">
          <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Loja</label>
          <select
            value={loja}
            onChange={e => setLoja(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
          >
            {lojas.map(l => <option key={l.id} value={l.nome}>{l.nome}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Motivo</label>
          <select
            value={motivo}
            onChange={e => setMotivo(e.target.value)}
            className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
          >
            {motivos.map(m => <option key={m} value={m}>{LABEL_MOTIVO[m] || m}</option>)}
          </select>
        </div>
      </div>

      {erro && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      )}
      {sucesso && (
        <div className="text-emerald-400 text-sm bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-4 py-3">{sucesso}</div>
      )}

      {!produto ? (
        <form onSubmit={buscar} className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 space-y-3">
          <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Bipe o codigo de barras / SKU</label>
          <input
            ref={codigoRef}
            autoFocus
            value={codigo}
            onChange={handleCodigoChange}
            disabled={buscando}
            placeholder="Aguardando leitura..."
            className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-4 py-3 text-lg text-neutral-100 font-mono focus:outline-none focus:border-indigo-500"
          />
          <button type="submit" disabled={buscando || !codigo.trim()} className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
            {buscando ? "Buscando..." : "Buscar"}
          </button>
        </form>
      ) : (
        <form onSubmit={confirmar} className="bg-neutral-900 border border-amber-800 rounded-lg p-6 space-y-4">
          <div>
            <div className="text-xs text-neutral-500">SKU: <span className="font-mono text-neutral-300">{produto.sku}</span></div>
            <div className="text-sm text-neutral-200 font-medium mt-0.5">{produto.descricao}</div>
            <div className="text-xs text-neutral-500 mt-1">Estoque atual: {produto.estoque_total} un</div>
          </div>
          <div className="space-y-1 max-w-[160px]">
            <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Quantidade a retirar</label>
            <input
              ref={qtdRef}
              type="number" step="1" min="1"
              value={quantidade}
              onChange={e => setQuantidade(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-indigo-500"
            />
          </div>
          {parseFloat(quantidade || "0") > limite && (
            <div className="text-xs text-amber-400 bg-amber-950/30 border border-amber-900/50 rounded-lg px-3 py-2">
              Acima de {limite} unidades — vai ficar pendente de aprovacao de um Gerente/Admin.
            </div>
          )}
          <div className="flex gap-2">
            <button type="submit" disabled={confirmando} className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
              {confirmando ? "Enviando..." : "Registrar Saida"}
            </button>
            <button type="button" onClick={cancelar} className="text-sm text-neutral-400 hover:text-neutral-200 px-4 py-2">Cancelar</button>
          </div>
        </form>
      )}
    </div>
  );
}
