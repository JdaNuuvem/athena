"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Section, SelectField, TextField } from "./shared";

const CARGOS = [
  { value: "proprietario", label: "Proprietário" },
  { value: "gerente_geral", label: "Gerente geral" },
  { value: "gerente_financeiro", label: "Gerente financeiro" },
  { value: "gerente_comercial", label: "Gerente comercial" },
  { value: "gerente_estoque", label: "Gerente de estoque" },
  { value: "responsavel_fiscal", label: "Responsável fiscal" },
  { value: "responsavel_pdv", label: "Responsável pelo PDV" },
  { value: "administrador", label: "Administrador da loja" },
];

interface Usuario { id: number; nome: string; email: string; }
interface Responsavel {
  id: number; usuario_id: number; usuario_nome: string; usuario_email: string;
  cargo: string; data_inicio: string; data_fim: string | null;
}

export default function ResponsaveisTab({ id }: { id: number }) {
  const [responsaveis, setResponsaveis] = useState<Responsavel[]>([]);
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [novo, setNovo] = useState({ usuario_id: "", cargo: "gerente_geral", data_inicio: "" });

  const carregar = () => {
    api.lojasResponsaveisListar(id).then((d) => setResponsaveis((d.responsaveis || []) as unknown as Responsavel[])).finally(() => setLoading(false));
  };

  useEffect(() => {
    carregar();
    api.rbacListUsuarios().then((d) => setUsuarios(d.usuarios || []));
  }, [id]);

  const vincular = async () => {
    if (!novo.usuario_id) { setErro("Escolha um usuário"); return; }
    setErro("");
    const r = await api.lojasResponsavelVincular(id, {
      usuario_id: Number(novo.usuario_id), cargo: novo.cargo,
      data_inicio: novo.data_inicio || undefined,
    });
    if (r.error) { setErro(r.error); return; }
    setNovo({ usuario_id: "", cargo: "gerente_geral", data_inicio: "" });
    carregar();
  };

  const encerrar = async (vinculoId: number) => {
    await api.lojasResponsavelAtualizar(id, vinculoId, { data_fim: new Date().toISOString().slice(0, 10) });
    carregar();
  };

  const remover = async (vinculoId: number) => {
    if (!confirm("Remover este vínculo?")) return;
    await api.lojasResponsavelRemover(id, vinculoId);
    carregar();
  };

  const cargoLabel = (c: string) => CARGOS.find((x) => x.value === c)?.label || c;

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      <Section title="Vincular responsável">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <SelectField
            label="Usuário"
            value={novo.usuario_id}
            onChange={(v) => setNovo((p) => ({ ...p, usuario_id: v }))}
            options={[{ value: "", label: "Selecione..." }, ...usuarios.map((u) => ({ value: String(u.id), label: `${u.nome} (${u.email})` }))]}
          />
          <SelectField label="Cargo" value={novo.cargo} onChange={(v) => setNovo((p) => ({ ...p, cargo: v }))} options={CARGOS} />
          <TextField label="Data de início" value={novo.data_inicio} onChange={(v) => setNovo((p) => ({ ...p, data_inicio: v }))} type="date" />
        </div>
        <button onClick={vincular} className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded-lg">Vincular</button>
      </Section>

      <Section title="Responsáveis atuais">
        {loading ? (
          <p className="text-xs text-neutral-500">Carregando...</p>
        ) : responsaveis.length === 0 ? (
          <p className="text-xs text-neutral-500">Nenhum responsável vinculado ainda.</p>
        ) : (
          <div className="space-y-2">
            {responsaveis.map((r) => (
              <div key={r.id} className="flex items-center justify-between bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2">
                <div>
                  <p className="text-sm text-neutral-200">{r.usuario_nome} <span className="text-neutral-500">— {cargoLabel(r.cargo)}</span></p>
                  <p className="text-[10px] text-neutral-600">
                    Desde {r.data_inicio}{r.data_fim ? ` até ${r.data_fim}` : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  {!r.data_fim && (
                    <button onClick={() => encerrar(r.id)} className="text-xs text-amber-400 hover:text-amber-300">Encerrar</button>
                  )}
                  <button onClick={() => remover(r.id)} className="text-xs text-red-400 hover:text-red-300">Remover</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
