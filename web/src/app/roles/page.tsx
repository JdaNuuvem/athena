"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import PageHeader from "@/app/_components/PageHeader";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import Icon from "@/app/_components/Icon";

interface Role {
  id: number;
  nome: string;
  descricao: string | null;
  created_at: string;
  permissoes: string[];
}

interface Permission {
  id: number;
  codigo: string;
  modulo: string;
  acao: string;
  descricao: string | null;
}

interface Usuario {
  id: number;
  nome: string;
  email: string;
  role_id: number | null;
  ativo: boolean;
}

interface LojaOpcao {
  id: number;
  nome: string;
  ativa: boolean;
}

const TABS = [
  { key: "cargos", label: "Cargos" },
  { key: "usuarios", label: "Usuários" },
] as const;

export default function RolesPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("cargos");
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [lojas, setLojas] = useState<LojaOpcao[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const carregar = () => {
    setLoading(true);
    Promise.all([api.roles(), api.permissions(), api.rbacListUsuarios(), api.lojasManage()])
      .then(([rolesData, permsData, usersData, lojasData]) => {
        setRoles(rolesData.roles || []);
        setPermissions(permsData.permissoes || []);
        setUsuarios(usersData.usuarios || []);
        setLojas(lojasData.lojas || []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const nomeDoRole = (roleId: number | null) => roles.find(r => r.id === roleId)?.nome || "—";

  if (loading) return <div className="p-6"><LoadingState /></div>;

  return (
    <div className="p-6 space-y-4">
      <PageHeader title="Cargos e Usuários" subtitle="Defina os papéis do sistema, o que cada um pode fazer, e quem está em cada papel." />
      {error && <ErrorAlert message={error} />}

      <div className="flex flex-wrap gap-1 bg-neutral-800 rounded-lg p-1 w-fit">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${tab === t.key ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "cargos" && (
        <CargosTab roles={roles} permissions={permissions} onChanged={carregar} setError={setError} />
      )}
      {tab === "usuarios" && (
        <UsuariosTab usuarios={usuarios} roles={roles} lojas={lojas} nomeDoRole={nomeDoRole} onChanged={carregar} setError={setError} />
      )}
    </div>
  );
}

function CargosTab({ roles, permissions, onChanged, setError }: {
  roles: Role[]; permissions: Permission[]; onChanged: () => void; setError: (e: string | null) => void;
}) {
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [editPerms, setEditPerms] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  const [criando, setCriando] = useState(false);
  const [novoNome, setNovoNome] = useState("");
  const [novaDescricao, setNovaDescricao] = useState("");

  const openEditor = (role: Role) => {
    setSelectedRole(role);
    setEditPerms(new Set(role.permissoes));
  };

  const togglePerm = (codigo: string) => {
    const next = new Set(editPerms);
    if (next.has(codigo)) next.delete(codigo);
    else next.add(codigo);
    setEditPerms(next);
  };

  const savePermissions = async () => {
    if (!selectedRole) return;
    setSaving(true);
    try {
      const r = await api.rolesUpdatePermissions(selectedRole.id, [...editPerms]);
      if ((r as { error?: string }).error) { setError((r as { error?: string }).error || "Erro ao salvar"); return; }
      setSelectedRole(null);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const criarCargo = async () => {
    if (!novoNome.trim()) { setError("Nome do cargo é obrigatório"); return; }
    try {
      const r = await api.roleCreate(novoNome.trim(), novaDescricao.trim(), []);
      if ((r as { error?: string }).error) { setError((r as { error?: string }).error || "Erro ao criar cargo"); return; }
      setCriando(false); setNovoNome(""); setNovaDescricao("");
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const excluirCargo = async (role: Role) => {
    if (!confirm(`Excluir o cargo "${role.nome}"? Usuários com esse cargo ficam sem permissões até serem reatribuídos.`)) return;
    try {
      const r = await api.roleDelete(role.id);
      if ((r as { error?: string }).error) { setError((r as { error?: string }).error || "Erro ao excluir"); return; }
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const groupedPerms = permissions.reduce((acc, p) => {
    if (!acc[p.modulo]) acc[p.modulo] = [];
    acc[p.modulo].push(p);
    return acc;
  }, {} as Record<string, Permission[]>);

  return (
    <div className="space-y-4">
      <Can permission="roles:manage">
        <div className="flex justify-end">
          <button onClick={() => setCriando(true)} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">
            + Novo Cargo
          </button>
        </div>
      </Can>

      <Can permission="roles:view">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3">Cargo</th>
                <th className="text-left px-4 py-3">Descrição</th>
                <th className="text-left px-4 py-3">Permissões</th>
                <th className="text-right px-4 py-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {roles.map(role => (
                <tr key={role.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="px-4 py-3 font-medium text-neutral-200">{role.nome}</td>
                  <td className="px-4 py-3 text-neutral-400">{role.descricao || "-"}</td>
                  <td className="px-4 py-3 text-neutral-400">{role.permissoes.length} permissões</td>
                  <td className="px-4 py-3 text-right space-x-3">
                    <Can permission="roles:manage">
                      <button onClick={() => openEditor(role)} className="text-indigo-400 hover:text-indigo-300 text-xs font-medium">
                        Editar Permissões
                      </button>
                      {role.nome !== "Admin" && (
                        <button onClick={() => excluirCargo(role)} className="text-red-400 hover:text-red-300 text-xs font-medium">
                          Excluir
                        </button>
                      )}
                    </Can>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Can>

      {criando && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setCriando(false)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Novo Cargo</h3>
            <div className="space-y-2">
              <input value={novoNome} onChange={e => setNovoNome(e.target.value)} placeholder="Nome do cargo"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novaDescricao} onChange={e => setNovaDescricao(e.target.value)} placeholder="Descrição (opcional)"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <p className="text-[11px] text-neutral-500 mt-2">Depois de criado, use &quot;Editar Permissões&quot; para definir o que esse cargo pode fazer.</p>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setCriando(false)} className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={criarCargo} className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium">Criar</button>
            </div>
          </div>
        </div>
      )}

      {selectedRole && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setSelectedRole(null)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-neutral-800 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-neutral-100">Permissões: {selectedRole.nome}</h2>
                <p className="text-xs text-neutral-500 mt-1">Marque o que este cargo pode fazer, módulo a módulo.</p>
              </div>
              <button onClick={() => setSelectedRole(null)} className="text-neutral-500 hover:text-neutral-300"><Icon name="close" size={16} /></button>
            </div>
            <div className="p-6 space-y-6">
              {Object.entries(groupedPerms).map(([mod, perms]) => (
                <div key={mod}>
                  <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">{mod}</h3>
                  <div className="grid grid-cols-2 gap-1">
                    {perms.map(p => (
                      <label key={p.id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-neutral-800/50 cursor-pointer text-sm">
                        <input
                          type="checkbox"
                          checked={editPerms.has(p.codigo)}
                          onChange={() => togglePerm(p.codigo)}
                          className="rounded border-neutral-700 bg-neutral-800 text-indigo-600 focus:ring-indigo-600"
                        />
                        <span className="text-neutral-300">{p.acao}</span>
                        {p.descricao && <span className="text-neutral-600 text-xs ml-auto truncate">{p.descricao}</span>}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-neutral-800 flex justify-end gap-3">
              <button onClick={() => setSelectedRole(null)} className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={savePermissions} disabled={saving}
                className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function UsuariosTab({ usuarios, roles, lojas, nomeDoRole, onChanged, setError }: {
  usuarios: Usuario[]; roles: Role[]; lojas: LojaOpcao[]; nomeDoRole: (id: number | null) => string; onChanged: () => void; setError: (e: string | null) => void;
}) {
  const [criando, setCriando] = useState(false);
  const [novo, setNovo] = useState({ nome: "", email: "", senha: "", role: "" });

  const [editando, setEditando] = useState<Usuario | null>(null);
  const [novoRole, setNovoRole] = useState("");

  const [pinAlvo, setPinAlvo] = useState<Usuario | null>(null);
  const [pin, setPin] = useState("");
  const [crachaGerado, setCrachaGerado] = useState<{ usuario: string; codigo: string } | null>(null);

  const [lojasAlvo, setLojasAlvo] = useState<Usuario | null>(null);
  const [lojasSelecionadas, setLojasSelecionadas] = useState<Set<number>>(new Set());
  const [carregandoLojas, setCarregandoLojas] = useState(false);
  const [salvandoLojas, setSalvandoLojas] = useState(false);

  const abrirCriar = () => { setNovo({ nome: "", email: "", senha: "", role: roles[0]?.nome || "" }); setCriando(true); };

  const criarUsuario = async () => {
    if (!novo.nome.trim() || !novo.email.trim() || !novo.senha || !novo.role) { setError("Preencha nome, e-mail, senha e cargo"); return; }
    try {
      const r = await api.rbacCreateUsuario(novo.nome.trim(), novo.email.trim(), novo.senha, novo.role);
      if ((r as { error?: string }).error) { setError((r as { error?: string }).error || "Erro ao criar usuário"); return; }
      setCriando(false);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const abrirEditar = (u: Usuario) => { setEditando(u); setNovoRole(nomeDoRole(u.role_id)); };

  const salvarRole = async () => {
    if (!editando) return;
    try {
      const r = await api.rbacUpdateUsuario(editando.id, { role: novoRole });
      if ((r as { error?: string }).error) { setError((r as { error?: string }).error || "Erro ao atualizar"); return; }
      setEditando(null);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const alternarAtivo = async (u: Usuario) => {
    try {
      const r = await api.rbacUpdateUsuario(u.id, { ativo: !u.ativo });
      if ((r as { error?: string }).error) { setError((r as { error?: string }).error || "Erro ao atualizar"); return; }
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const abrirPin = (u: Usuario) => { setPinAlvo(u); setPin(""); };

  const salvarPin = async () => {
    if (!pinAlvo) return;
    if (!/^\d{4,6}$/.test(pin)) { setError("PIN deve ter de 4 a 6 dígitos"); return; }
    try {
      const r = await api.rbacDefinirPin(pinAlvo.id, pin);
      if (r.error) { setError(r.error); return; }
      setPinAlvo(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const gerarCracha = async (u: Usuario) => {
    try {
      const r = await api.rbacGerarCodigoBarras(u.id);
      if (r.error) { setError(r.error); return; }
      setCrachaGerado({ usuario: u.nome, codigo: r.codigo_barras || "" });
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const abrirLojas = async (u: Usuario) => {
    setLojasAlvo(u);
    setLojasSelecionadas(new Set());
    setCarregandoLojas(true);
    try {
      const r = await api.rbacListarLojasUsuario(u.id);
      if (r.error) { setError(r.error); return; }
      setLojasSelecionadas(new Set((r.lojas || []).map(l => l.id)));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCarregandoLojas(false);
    }
  };

  const toggleLoja = (id: number) => {
    const next = new Set(lojasSelecionadas);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setLojasSelecionadas(next);
  };

  const salvarLojas = async () => {
    if (!lojasAlvo) return;
    setSalvandoLojas(true);
    try {
      const r = await api.rbacDefinirLojasUsuario(lojasAlvo.id, [...lojasSelecionadas]);
      if (r.error) { setError(r.error); return; }
      setLojasAlvo(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSalvandoLojas(false);
    }
  };

  return (
    <div className="space-y-4">
      <Can permission="roles:manage">
        <div className="flex justify-end">
          <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">
            + Novo Usuário
          </button>
        </div>
      </Can>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-3">Nome</th>
              <th className="text-left px-4 py-3">E-mail</th>
              <th className="text-left px-4 py-3">Cargo</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-right px-4 py-3">Ações</th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map(u => (
              <tr key={u.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                <td className="px-4 py-3 font-medium text-neutral-200">{u.nome}</td>
                <td className="px-4 py-3 text-neutral-400">{u.email}</td>
                <td className="px-4 py-3 text-neutral-400">{nomeDoRole(u.role_id)}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${u.ativo ? "bg-green-900/50 text-green-400" : "bg-neutral-800 text-neutral-500"}`}>
                    {u.ativo ? "ativo" : "inativo"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right space-x-3 whitespace-nowrap">
                  <Can permission="roles:manage">
                    <button onClick={() => abrirEditar(u)} className="text-indigo-400 hover:text-indigo-300 text-xs font-medium">Trocar cargo</button>
                    <button onClick={() => abrirLojas(u)} className="text-indigo-400 hover:text-indigo-300 text-xs font-medium">Lojas</button>
                    <button onClick={() => abrirPin(u)} className="text-amber-400 hover:text-amber-300 text-xs font-medium">Definir PIN</button>
                    <button onClick={() => gerarCracha(u)} className="text-amber-400 hover:text-amber-300 text-xs font-medium">Gerar crachá</button>
                    <button onClick={() => alternarAtivo(u)} className="text-neutral-400 hover:text-neutral-200 text-xs font-medium">
                      {u.ativo ? "Desativar" : "Ativar"}
                    </button>
                  </Can>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {criando && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setCriando(false)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Novo Usuário</h3>
            <div className="space-y-2">
              <input value={novo.nome} onChange={e => setNovo({ ...novo, nome: e.target.value })} placeholder="Nome"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novo.email} onChange={e => setNovo({ ...novo, email: e.target.value })} placeholder="E-mail" type="email"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novo.senha} onChange={e => setNovo({ ...novo, senha: e.target.value })} placeholder="Senha" type="password"
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <select value={novo.role} onChange={e => setNovo({ ...novo, role: e.target.value })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                {roles.map(r => <option key={r.id} value={r.nome}>{r.nome}</option>)}
              </select>
            </div>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setCriando(false)} className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={criarUsuario} className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium">Criar</button>
            </div>
          </div>
        </div>
      )}

      {editando && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setEditando(null)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Trocar cargo — {editando.nome}</h3>
            <select value={novoRole} onChange={e => setNovoRole(e.target.value)}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
              {roles.map(r => <option key={r.id} value={r.nome}>{r.nome}</option>)}
            </select>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setEditando(null)} className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={salvarRole} className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium">Salvar</button>
            </div>
          </div>
        </div>
      )}

      {lojasAlvo && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setLojasAlvo(null)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-sm p-6 max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-1">Lojas — {lojasAlvo.nome}</h3>
            <p className="text-[11px] text-neutral-500 mb-3">
              Marque as lojas que esta pessoa pode ver. Sem nenhuma marcada, ela não vê dado de loja nenhuma
              (a menos que o cargo dela tenha a permissão &quot;Ver todas as lojas&quot;).
            </p>
            {carregandoLojas ? (
              <LoadingState />
            ) : (
              <div className="space-y-1">
                {lojas.map(l => (
                  <label key={l.id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-neutral-800/50 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={lojasSelecionadas.has(l.id)}
                      onChange={() => toggleLoja(l.id)}
                      className="rounded border-neutral-700 bg-neutral-800 text-indigo-600 focus:ring-indigo-600"
                    />
                    <span className="text-neutral-300">{l.nome}</span>
                    {!l.ativa && <span className="text-neutral-600 text-xs ml-auto">inativa</span>}
                  </label>
                ))}
                {lojas.length === 0 && <p className="text-xs text-neutral-500">Nenhuma loja cadastrada.</p>}
              </div>
            )}
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setLojasAlvo(null)} className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={salvarLojas} disabled={salvandoLojas || carregandoLojas}
                className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium">
                {salvandoLojas ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {pinAlvo && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setPinAlvo(null)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Definir PIN — {pinAlvo.nome}</h3>
            <input type="password" inputMode="numeric" maxLength={6} value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, ""))}
              placeholder="4 a 6 dígitos" className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            <p className="text-[11px] text-neutral-500 mt-2">Esse PIN permite que a pessoa autorize ações sensíveis (ex: aprovar pagamento acima do limite) sem precisar de logout/login.</p>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setPinAlvo(null)} className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={salvarPin} className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium">Salvar</button>
            </div>
          </div>
        </div>
      )}

      {crachaGerado && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setCrachaGerado(null)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-2">Crachá gerado — {crachaGerado.usuario}</h3>
            <p className="text-[11px] text-amber-400 mb-3">Anote ou imprima agora — este código não pode ser recuperado depois, só gerado de novo.</p>
            <p className="font-mono text-lg text-neutral-100 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-center tracking-wider">
              {crachaGerado.codigo}
            </p>
            <div className="flex justify-end mt-4">
              <button onClick={() => setCrachaGerado(null)} className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium">Fechar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
