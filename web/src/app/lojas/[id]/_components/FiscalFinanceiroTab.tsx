"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Section, TextField, SelectField, CheckboxField, strVal } from "./shared";

const CAMPOS_SENSIVEIS = new Set(["certificado_digital", "csc_nfce", "token_fiscal", "pix_chave"]);

const CAMPOS_FISCAL = ["regime_tributario", "serie_nfe", "serie_nfce", "ambiente_fiscal", "certificado_digital", "csc_nfce", "token_fiscal"];
const CAMPOS_FINANCEIRO = ["conta_bancaria", "conta_caixa_padrao", "centro_financeiro", "carteira_padrao", "gateway_pagamento", "pix_chave"];
const CAMPOS_ESTOQUE = ["deposito_principal", "permitir_estoque_negativo", "estoque_minimo_padrao", "estoque_reservado"];

// Campos sensiveis nunca voltam da API (GET /manage/<id> ja os filtra) — o
// form sempre parte vazio pra eles. So' entram no payload se o usuario
// digitar algo, pra nunca sobrescrever o valor real com string vazia.
function montarPayload(form: Record<string, string>, campos: string[], booleanos: string[] = [], numericos: string[] = []) {
  const payload: Record<string, unknown> = {};
  for (const c of campos) {
    const v = form[c];
    if (CAMPOS_SENSIVEIS.has(c) && !v) continue;
    if (numericos.includes(c) && !v) continue; // vazio = nao envia (coluna NUMERIC nao aceita string vazia)
    if (booleanos.includes(c)) payload[c] = v === "true";
    else if (numericos.includes(c)) payload[c] = Number(v);
    else payload[c] = v;
  }
  return payload;
}

export default function FiscalFinanceiroTab({ id, loja }: { id: number; loja: Record<string, unknown> | null }) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string>("");
  const [msg, setMsg] = useState<Record<string, string>>({});
  const [erro, setErro] = useState("");

  useEffect(() => {
    const todos = [...CAMPOS_FISCAL, ...CAMPOS_FINANCEIRO, ...CAMPOS_ESTOQUE];
    const inicial: Record<string, string> = {};
    for (const c of todos) inicial[c] = strVal(loja, c);
    setForm(inicial);
  }, [loja]);

  const set = (campo: string) => (v: string) => setForm((p) => ({ ...p, [campo]: v }));

  const salvar = async (secao: "fiscal" | "financeiro" | "estoque") => {
    setSaving(secao); setErro("");
    try {
      let r;
      if (secao === "fiscal") r = await api.lojasFiscalAtualizar(id, montarPayload(form, CAMPOS_FISCAL));
      else if (secao === "financeiro") r = await api.lojasFinanceiroAtualizar(id, montarPayload(form, CAMPOS_FINANCEIRO));
      else r = await api.lojasEstoqueConfigAtualizar(id, montarPayload(form, CAMPOS_ESTOQUE, ["permitir_estoque_negativo", "estoque_reservado"], ["estoque_minimo_padrao"]));
      if (r.error) { setErro(r.error); return; }
      setMsg((p) => ({ ...p, [secao]: "Salvo!" }));
      setTimeout(() => setMsg((p) => ({ ...p, [secao]: "" })), 2500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving("");
    }
  };

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      <Section title="Fiscal" onSave={() => salvar("fiscal")} saving={saving === "fiscal"} msg={msg.fiscal}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Regime tributário" value={form.regime_tributario || ""} onChange={set("regime_tributario")} />
          <TextField label="Série NF-e" value={form.serie_nfe || ""} onChange={set("serie_nfe")} />
          <TextField label="Série NFC-e" value={form.serie_nfce || ""} onChange={set("serie_nfce")} />
          <SelectField
            label="Ambiente fiscal"
            value={form.ambiente_fiscal || "homologacao"}
            onChange={set("ambiente_fiscal")}
            options={[{ value: "homologacao", label: "Homologação" }, { value: "producao", label: "Produção" }]}
          />
          <TextField label="Certificado digital" value={form.certificado_digital || ""} onChange={set("certificado_digital")} type="password" placeholder="Deixe em branco pra manter o atual" />
          <TextField label="CSC NFC-e" value={form.csc_nfce || ""} onChange={set("csc_nfce")} type="password" placeholder="Deixe em branco pra manter o atual" />
          <TextField label="Token fiscal" value={form.token_fiscal || ""} onChange={set("token_fiscal")} type="password" placeholder="Deixe em branco pra manter o atual" />
        </div>
      </Section>

      <Section title="Financeiro" onSave={() => salvar("financeiro")} saving={saving === "financeiro"} msg={msg.financeiro}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Conta bancária" value={form.conta_bancaria || ""} onChange={set("conta_bancaria")} />
          <TextField label="Conta caixa padrão" value={form.conta_caixa_padrao || ""} onChange={set("conta_caixa_padrao")} />
          <TextField label="Centro financeiro" value={form.centro_financeiro || ""} onChange={set("centro_financeiro")} />
          <TextField label="Carteira padrão" value={form.carteira_padrao || ""} onChange={set("carteira_padrao")} />
          <TextField label="Gateway de pagamento" value={form.gateway_pagamento || ""} onChange={set("gateway_pagamento")} />
          <TextField label="Chave PIX" value={form.pix_chave || ""} onChange={set("pix_chave")} type="password" placeholder="Deixe em branco pra manter a atual" />
        </div>
      </Section>

      <Section title="Configuração de estoque" onSave={() => salvar("estoque")} saving={saving === "estoque"} msg={msg.estoque}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Depósito principal" value={form.deposito_principal || ""} onChange={set("deposito_principal")} />
          <TextField label="Estoque mínimo padrão" value={form.estoque_minimo_padrao || ""} onChange={set("estoque_minimo_padrao")} type="number" />
        </div>
        <div className="flex gap-6">
          <CheckboxField label="Permitir estoque negativo" checked={form.permitir_estoque_negativo === "true"} onChange={(v) => set("permitir_estoque_negativo")(String(v))} />
          <CheckboxField label="Reservar estoque" checked={form.estoque_reservado === "true"} onChange={(v) => set("estoque_reservado")(String(v))} />
        </div>
      </Section>
    </div>
  );
}
