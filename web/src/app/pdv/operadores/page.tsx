"use client";

import { useState, useEffect, useCallback } from "react";
import Icon from "@/app/_components/Icon";

interface OperadorPDV {
  id: number;
  nome: string;
  role: string;
  ativo: boolean;
  desconto_maximo_percent: number;
  tem_senha: boolean;
  tem_pin: boolean;
  tem_codigo_barras: boolean;
}

const ROLES = ["operador", "gerente", "admin"] as const;

// fetch(...).then(r => r.json()) explode com "Unexpected token '<'" quando a
// resposta e' uma pagina de erro HTML (404/405/502) em vez de JSON — troca
// por uma mensagem legivel baseada no status HTTP nesse caso.
async function apiJson<T = any>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const texto = await res.text();
  try {
    return JSON.parse(texto) as T;
  } catch {
    throw new Error(`Erro ${res.status} do servidor — resposta inesperada`);
  }
}

export default function OperadoresPDVPage() {
  const [operadores, setOperadores] = useState<OperadorPDV[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const [criando, setCriando] = useState(false);
  const [novoNome, setNovoNome] = useState("");
  const [novoRole, setNovoRole] = useState<string>("operador");
  const [novoDesconto, setNovoDesconto] = useState("0");

  const [senhaModal, setSenhaModal] = useState<{ id: number; nome: string } | null>(null);
  const [senhaValor, setSenhaValor] = useState("");
  const [senhaConfirma, setSenhaConfirma] = useState("");
  const [salvandoSenha, setSalvandoSenha] = useState(false);

  const [pinModal, setPinModal] = useState<{ id: number; nome: string } | null>(null);
  const [pinValor, setPinValor] = useState("");
  const [codigoGerado, setCodigoGerado] = useState<{ nome: string; codigo: string } | null>(null);

  const [editando, setEditando] = useState<OperadorPDV | null>(null);
  const [editRole, setEditRole] = useState("operador");
  const [editDesconto, setEditDesconto] = useState("0");
  const [editAtivo, setEditAtivo] = useState(true);
  const [salvandoEdicao, setSalvandoEdicao] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiJson<{ data?: OperadorPDV[] }>("/api/pdv/operadores");
      setOperadores(r.data || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const limparMsgs = () => { setErro(""); setSucesso(""); };

  const criarOperador = async () => {
    if (!novoNome.trim()) { setErro("Nome obrigatório"); return; }
    limparMsgs();
    setCriando(true);
    try {
      const r = await apiJson<{ error?: string }>("/api/pdv/operadores", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: novoNome.trim(), role: novoRole, desconto_maximo_percent: Number(novoDesconto) || 0 }),
      });
      if (r.error) { setErro(r.error); return; }
      setSucesso(`Operador ${novoNome.trim()} criado — defina uma senha para ele poder logar no PDV.`);
      setNovoNome(""); setNovoRole("operador"); setNovoDesconto("0");
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao criar operador");
    } finally {
      setCriando(false);
    }
  };

  const salvarSenha = async () => {
    if (!senhaModal) return;
    if (senhaValor.length < 6) { setErro("Senha deve ter no mínimo 6 caracteres"); return; }
    if (senhaValor !== senhaConfirma) { setErro("As senhas não coincidem"); return; }
    limparMsgs();
    setSalvandoSenha(true);
    try {
      const r = await apiJson<{ error?: string }>(`/api/pdv/operadores/${senhaModal.id}/senha`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ senha: senhaValor }),
      });
      if (r.error) { setErro(r.error); return; }
      setSucesso(`Senha definida para ${senhaModal.nome}. Já pode logar no PDV.`);
      setSenhaModal(null); setSenhaValor(""); setSenhaConfirma("");
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao definir senha");
    } finally {
      setSalvandoSenha(false);
    }
  };

  const salvarPin = async () => {
    if (!pinModal) return;
    if (!/^\d{4,6}$/.test(pinValor)) { setErro("PIN deve ter de 4 a 6 dígitos numéricos"); return; }
    limparMsgs();
    try {
      const r = await apiJson<{ error?: string }>(`/api/pdv/operadores/${pinModal.id}/pin`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: pinValor }),
      });
      if (r.error) { setErro(r.error); return; }
      setSucesso(`PIN definido para ${pinModal.nome}.`);
      setPinModal(null); setPinValor("");
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao definir PIN"); }
  };

  const gerarCodigoBarras = async (op: OperadorPDV) => {
    limparMsgs();
    try {
      const r = await apiJson<{ error?: string; codigo_barras?: string }>(`/api/pdv/operadores/${op.id}/codigo-barras`, { method: "POST" });
      if (r.error || !r.codigo_barras) { setErro(r.error || "Erro ao gerar código de barras"); return; }
      setCodigoGerado({ nome: op.nome, codigo: r.codigo_barras });
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao gerar código de barras"); }
  };

  const abrirEdicao = (op: OperadorPDV) => {
    setEditando(op);
    setEditRole(op.role);
    setEditDesconto(String(op.desconto_maximo_percent));
    setEditAtivo(op.ativo);
  };

  const salvarEdicao = async () => {
    if (!editando) return;
    limparMsgs();
    setSalvandoEdicao(true);
    try {
      const r = await apiJson<{ error?: string }>(`/api/pdv/operadores/${editando.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: editRole, desconto_maximo_percent: Number(editDesconto) || 0, ativo: editAtivo }),
      });
      if (r.error) { setErro(r.error); return; }
      setSucesso(`${editando.nome} atualizado.`);
      setEditando(null);
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar edição");
    } finally {
      setSalvandoEdicao(false);
    }
  };

  const excluirOperador = async (op: OperadorPDV) => {
    if (!window.confirm(`Excluir o operador "${op.nome}"? Esta ação não pode ser desfeita.`)) return;
    limparMsgs();
    try {
      const r = await apiJson<{ error?: string }>(`/api/pdv/operadores/${op.id}`, { method: "DELETE" });
      if (r.error) { setErro(r.error); return; }
      setSucesso(`${op.nome} excluído.`);
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao excluir operador"); }
  };

  const gerencial = (role: string) => ["gerente", "admin"].includes(role.toLowerCase());

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Operadores do PDV</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Cadastre operadores, defina a senha de login do caixa, e o PIN/crachá usado por Gerente/Admin para autorizar ações sensíveis sem logout/login.
        </p>
      </div>

      {erro && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>}
      {sucesso && <div className="text-emerald-400 text-sm bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-4 py-3">{sucesso}</div>}

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-neutral-200 mb-3">Novo operador</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-[10px] text-neutral-500 mb-1">Nome</label>
            <input
              type="text" value={novoNome} onChange={e => setNovoNome(e.target.value)}
              placeholder="Nome do operador"
              onKeyDown={e => e.key === "Enter" && criarOperador()}
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-[10px] text-neutral-500 mb-1">Role</label>
            <select value={novoRole} onChange={e => setNovoRole(e.target.value)}
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 capitalize">
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] text-neutral-500 mb-1">Desconto máx. (%)</label>
            <input
              type="number" min="0" max="100" value={novoDesconto} onChange={e => setNovoDesconto(e.target.value)}
              className="w-24 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
            />
          </div>
          <button
            onClick={criarOperador}
            disabled={criando || !novoNome.trim()}
            className="bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm transition-colors"
          >
            {criando ? "Criando..." : "Criar operador"}
          </button>
        </div>
      </div>

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
                <th className="px-3 py-2 font-medium">Status</th>
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
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${op.ativo ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-400"}`}>
                        {op.ativo ? "Ativo" : "Inativo"}
                      </span>
                      {!op.tem_senha && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-900/30 text-amber-400" title="Sem senha cadastrada — não consegue logar no PDV">
                          Sem senha
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        onClick={() => { setSenhaModal({ id: op.id, nome: op.nome }); setSenhaValor(""); setSenhaConfirma(""); }}
                        className="text-[10px] bg-teal-600 hover:bg-teal-500 text-white px-2 py-1 rounded-lg"
                      >
                        {op.tem_senha ? "Redefinir senha" : "Definir senha"}
                      </button>
                      <button
                        onClick={() => abrirEdicao(op)}
                        className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-200 px-2 py-1 rounded-lg"
                      >
                        Editar
                      </button>
                      {gerencial(op.role) && (
                        <>
                          <button
                            onClick={() => { setPinModal({ id: op.id, nome: op.nome }); setPinValor(""); }}
                            className="text-[10px] bg-indigo-600 hover:bg-indigo-500 text-white px-2 py-1 rounded-lg"
                          >
                            {op.tem_pin ? "Redefinir PIN" : "Definir PIN"}
                          </button>
                          <button
                            onClick={() => gerarCodigoBarras(op)}
                            className="text-[10px] bg-sky-600 hover:bg-sky-500 text-white px-2 py-1 rounded-lg"
                          >
                            {op.tem_codigo_barras ? "Gerar novo crachá" : "Gerar crachá"}
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => excluirOperador(op)}
                        className="text-[10px] bg-red-900/60 hover:bg-red-900 text-red-200 px-2 py-1 rounded-lg inline-flex items-center gap-1"
                      >
                        <Icon name="trash" size={11} /> Excluir
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {operadores.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-8 text-center text-neutral-500">Nenhum operador cadastrado</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {senhaModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setSenhaModal(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-80" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Definir senha — {senhaModal.nome}</h3>
            <div className="space-y-2 mb-3">
              <input
                type="password" autoFocus
                value={senhaValor}
                onChange={e => setSenhaValor(e.target.value)}
                placeholder="Nova senha (mín. 6 caracteres)"
                onKeyDown={e => e.key === "Enter" && salvarSenha()}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200"
              />
              <input
                type="password"
                value={senhaConfirma}
                onChange={e => setSenhaConfirma(e.target.value)}
                placeholder="Confirmar senha"
                onKeyDown={e => e.key === "Enter" && salvarSenha()}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200"
              />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setSenhaModal(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={salvarSenha} disabled={salvandoSenha} className="flex-1 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white text-sm rounded-lg">
                {salvandoSenha ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
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

      {editando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setEditando(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-80" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Editar — {editando.nome}</h3>
            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-[10px] text-neutral-500 mb-1">Role</label>
                <select value={editRole} onChange={e => setEditRole(e.target.value)}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 capitalize">
                  {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-neutral-500 mb-1">Desconto máx. (%)</label>
                <input
                  type="number" min="0" max="100" value={editDesconto} onChange={e => setEditDesconto(e.target.value)}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-neutral-300">
                <input type="checkbox" checked={editAtivo} onChange={e => setEditAtivo(e.target.checked)} className="accent-indigo-600" />
                Ativo
              </label>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setEditando(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={salvarEdicao} disabled={salvandoEdicao} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg">
                {salvandoEdicao ? "Salvando..." : "Salvar"}
              </button>
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
