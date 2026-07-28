"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Section, TextField, SelectField, strVal } from "./shared";

const STATUS_OPCOES = [
  { value: "ativa", label: "Ativa" },
  { value: "inativa", label: "Inativa" },
  { value: "em_implantacao", label: "Em implantação" },
  { value: "bloqueada", label: "Bloqueada" },
];

const CAMPOS_IDENTIFICACAO = [
  "nome", "nome_fantasia", "razao_social", "cnpj_cpf", "inscricao_estadual",
  "inscricao_municipal", "status", "cor_principal", "cor_secundaria", "tipo",
];
const CAMPOS_ENDERECO = ["cep", "rua", "numero", "complemento", "bairro", "cidade", "estado", "pais"];
const CAMPOS_CONTATO = ["telefone", "whatsapp", "email", "site", "instagram", "facebook", "tiktok", "youtube"];

export default function GeralTab({ id, loja, onUpdate }: { id: number; loja: Record<string, unknown> | null; onUpdate?: () => void }) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    const todos = [...CAMPOS_IDENTIFICACAO, ...CAMPOS_ENDERECO, ...CAMPOS_CONTATO];
    const inicial: Record<string, string> = {};
    for (const c of todos) inicial[c] = strVal(loja, c);
    setForm(inicial);
  }, [loja]);

  const set = (campo: string) => (v: string) => setForm((p) => ({ ...p, [campo]: v }));

  const salvar = async () => {
    setSaving(true); setErro(""); setMsg("");
    const nome = form.nome.trim();
    if (!nome) { setErro("Nome é obrigatório"); setSaving(false); return; }
    try {
      const r = await api.lojasAtualizarGeral(id, form);
      if (r.error) { setErro(r.error); return; }
      setMsg("Salvo!");
      onUpdate?.();
      setTimeout(() => setMsg(""), 2500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      <Section title="Identificação" onSave={salvar} saving={saving} msg={msg}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Nome" value={form.nome || ""} onChange={set("nome")} />
          <TextField label="Nome fantasia" value={form.nome_fantasia || ""} onChange={set("nome_fantasia")} />
          <TextField label="Razão social" value={form.razao_social || ""} onChange={set("razao_social")} />
          <TextField label="CNPJ/CPF" value={form.cnpj_cpf || ""} onChange={set("cnpj_cpf")} placeholder="00.000.000/0000-00" />
          <TextField label="Inscrição estadual" value={form.inscricao_estadual || ""} onChange={set("inscricao_estadual")} />
          <TextField label="Inscrição municipal" value={form.inscricao_municipal || ""} onChange={set("inscricao_municipal")} />
          <SelectField label="Status" value={form.status || "ativa"} onChange={set("status")} options={STATUS_OPCOES} />
          <SelectField
            label="Tipo"
            value={form.tipo || "fisica"}
            onChange={set("tipo")}
            options={[
              { value: "fisica", label: "Física" },
              { value: "virtual", label: "Virtual" },
              { value: "hibrida", label: "Híbrida" },
              { value: "marketplace", label: "Marketplace" },
            ]}
          />
          <TextField label="Cor principal" value={form.cor_principal || ""} onChange={set("cor_principal")} type="color" />
          <TextField label="Cor secundária" value={form.cor_secundaria || ""} onChange={set("cor_secundaria")} type="color" />
        </div>
      </Section>

      <Section title="Endereço" onSave={salvar} saving={saving}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <TextField label="CEP" value={form.cep || ""} onChange={set("cep")} placeholder="00000-000" />
          <TextField label="Rua" value={form.rua || ""} onChange={set("rua")} />
          <TextField label="Número" value={form.numero || ""} onChange={set("numero")} />
          <TextField label="Complemento" value={form.complemento || ""} onChange={set("complemento")} />
          <TextField label="Bairro" value={form.bairro || ""} onChange={set("bairro")} />
          <TextField label="Cidade" value={form.cidade || ""} onChange={set("cidade")} />
          <TextField label="Estado" value={form.estado || ""} onChange={set("estado")} placeholder="RJ" />
          <TextField label="País" value={form.pais || ""} onChange={set("pais")} placeholder="Brasil" />
        </div>
      </Section>

      <Section title="Contatos e redes sociais" onSave={salvar} saving={saving}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <TextField label="Telefone" value={form.telefone || ""} onChange={set("telefone")} />
          <TextField label="WhatsApp" value={form.whatsapp || ""} onChange={set("whatsapp")} />
          <TextField label="E-mail" value={form.email || ""} onChange={set("email")} type="email" />
          <TextField label="Site" value={form.site || ""} onChange={set("site")} />
          <TextField label="Instagram" value={form.instagram || ""} onChange={set("instagram")} placeholder="@usuario" />
          <TextField label="Facebook" value={form.facebook || ""} onChange={set("facebook")} />
          <TextField label="TikTok" value={form.tiktok || ""} onChange={set("tiktok")} />
          <TextField label="YouTube" value={form.youtube || ""} onChange={set("youtube")} />
        </div>
      </Section>
    </div>
  );
}
