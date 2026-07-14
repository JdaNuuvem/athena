"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import PageHeader from "@/app/_components/PageHeader";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";

interface Role {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
  isSystem: boolean;
  permissionCodes: string[];
  createdAt: string;
}

interface Permission {
  id: string;
  code: string;
  module: string;
  action: string;
  description: string | null;
}

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [editPerms, setEditPerms] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([api.roles(), api.permissions()])
      .then(([rolesData, permsData]) => {
        setRoles(rolesData.roles || []);
        setPermissions(permsData.permissions || []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const openEditor = (role: Role) => {
    setSelectedRole(role);
    setEditPerms(new Set(role.permissionCodes));
  };

  const togglePerm = (code: string) => {
    const next = new Set(editPerms);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setEditPerms(next);
  };

  const savePermissions = async () => {
    if (!selectedRole) return;
    setSaving(true);
    try {
      const permIds = permissions.filter(p => editPerms.has(p.code)).map(p => p.id);
      await api.rolesUpdatePermissions(selectedRole.id, permIds);
      setRoles(prev => prev.map(r => r.id === selectedRole.id ? { ...r, permissionCodes: [...editPerms] } : r));
      setSelectedRole(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const groupedPerms = permissions.reduce((acc, p) => {
    if (!acc[p.module]) acc[p.module] = [];
    acc[p.module].push(p);
    return acc;
  }, {} as Record<string, Permission[]>);

  if (loading) return <LoadingState />;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <PageHeader title="Cargos e Permissões" subtitle="Gerencie os cargos do sistema e suas permissões de acesso." />

      {error && <ErrorAlert message={error} />}

      {/* Roles table */}
      <Can permission="roles:view">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden mt-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3">Cargo</th>
                <th className="text-left px-4 py-3">Descrição</th>
                <th className="text-left px-4 py-3">Permissões</th>
                <th className="text-left px-4 py-3">Sistema</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {roles.map(role => (
                <tr key={role.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="px-4 py-3 font-medium text-neutral-200">{role.name}</td>
                  <td className="px-4 py-3 text-neutral-400">{role.description || "-"}</td>
                  <td className="px-4 py-3 text-neutral-400">{role.permissionCodes.length} permissões</td>
                  <td className="px-4 py-3">{role.isSystem ? "✅" : "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${role.active ? "bg-green-900/50 text-green-400" : "bg-neutral-800 text-neutral-500"}`}>
                      {role.active ? "ativo" : "inativo"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Can permission="roles:manage">
                      <button
                        onClick={() => openEditor(role)}
                        className="text-indigo-400 hover:text-indigo-300 text-xs font-medium"
                      >
                        Editar Permissões
                      </button>
                    </Can>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Can>

      {/* Permission editor modal */}
      {selectedRole && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setSelectedRole(null)}>
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b border-neutral-800 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-neutral-100">Permissões: {selectedRole.name}</h2>
                <p className="text-xs text-neutral-500 mt-1">Marque as permissões que este cargo deve ter.</p>
              </div>
              <button onClick={() => setSelectedRole(null)} className="text-neutral-500 hover:text-neutral-300 text-lg">✕</button>
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
                          checked={editPerms.has(p.code)}
                          onChange={() => togglePerm(p.code)}
                          className="rounded border-neutral-700 bg-neutral-800 text-indigo-600 focus:ring-indigo-600"
                        />
                        <span className="text-neutral-300">{p.action}</span>
                        {p.description && <span className="text-neutral-600 text-xs ml-auto truncate">{p.description}</span>}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-neutral-800 flex justify-end gap-3">
              <button onClick={() => setSelectedRole(null)} className="px-4 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button
                onClick={savePermissions}
                disabled={saving}
                className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium"
              >
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
