"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Section, TextField, TextAreaField, strVal } from "./shared";

const CAMPOS_OPERACIONAL = [
  "dias_funcionamento", "fuso_horario", "moeda", "idioma", "codigo_interno",
  "codigo_erp", "centro_custo", "regiao", "area_atuacao", "horario_funcionamento",
];
const CAMPOS_COMERCIAL = [
  "politica_precos", "tabela_precos_padrao", "desconto_maximo_pct",
  "comissao_padrao_pct", "meta_mensal", "meta_anual",
];

export default function OperacionalComercialTab({ id, loja }: { id: number; loja: Record<string, unknown> | null }) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [savingOp, setSavingOp] = useState(false);
  const [savingCom, setSavingCom] = useState(false);
  const [msgOp, setMsgOp] = useState("");
  const [msgCom, setMsgCom] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    const todos = [...CAMPOS_OPERACIONAL, ...CAMPOS_COMERCIAL];
    const inicial: Record<string, string> = {};
    for (const c of todos) inicial[c] = strVal(loja, c);
    setForm(inicial);
  }, [loja]);

  const set = (campo: string) => (v: string) => setForm((p) => ({ ...p, [campo]: v }));

  const salvarOperacional = async () => {
    setSavingOp(true); setErro("");
    try {
      const campos: Record<string, unknown> = {};
      for (const c of CAMPOS_OPERACIONAL) campos[c] = form[c];
      const r = await api.lojasOperacionalAtualizar(id, campos);
      if (r.error) { setErro(r.error); return; }
      setMsgOp("Salvo!"); setTimeout(() => setMsgOp(""), 2500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSavingOp(false);
    }
  };

  const salvarComercial = async () => {
    setSavingCom(true); setErro("");
    try {
      const NUMERICOS = ["desconto_maximo_pct", "comissao_padrao_pct", "meta_mensal", "meta_anual"];
      const campos: Record<string, unknown> = {};
      for (const c of CAMPOS_COMERCIAL) {
        const v = form[c];
        if (NUMERICOS.includes(c)) {
          if (v) campos[c] = Number(v); // vazio = nao envia (coluna NUMERIC nao aceita string vazia)
        } else {
          campos[c] = v;
        }
      }
      const r = await api.lojasComercialAtualizar(id, campos);
      if (r.error) { setErro(r.error); return; }
      setMsgCom("Salvo!"); setTimeout(() => setMsgCom(""), 2500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSavingCom(false);
    }
  };

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      <Section title="Operacional" onSave={salvarOperacional} saving={savingOp} msg={msgOp}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Código interno" value={form.codigo_interno || ""} onChange={set("codigo_interno")} />
          <TextField label="Código ERP" value={form.codigo_erp || ""} onChange={set("codigo_erp")} />
          <TextField label="Centro de custo" value={form.centro_custo || ""} onChange={set("centro_custo")} />
          <TextField label="Região" value={form.regiao || ""} onChange={set("regiao")} />
          <TextField label="Área de atuação" value={form.area_atuacao || ""} onChange={set("area_atuacao")} />
          <TextField label="Fuso horário" value={form.fuso_horario || ""} onChange={set("fuso_horario")} placeholder="America/Sao_Paulo" />
          <TextField label="Moeda" value={form.moeda || ""} onChange={set("moeda")} placeholder="BRL" />
          <TextField label="Idioma" value={form.idioma || ""} onChange={set("idioma")} placeholder="pt-BR" />
          <TextField label="Dias de funcionamento" value={form.dias_funcionamento || ""} onChange={set("dias_funcionamento")} placeholder="seg,ter,qua,qui,sex,sab" />
        </div>
        <TextAreaField
          label='Horário de funcionamento (JSON: {"seg":"08:00-18:00","dom":"fechado"})'
          value={form.horario_funcionamento || ""}
          onChange={set("horario_funcionamento")}
          rows={2}
        />
      </Section>

      <Section title="Comercial" onSave={salvarComercial} saving={savingCom} msg={msgCom}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Política de preços" value={form.politica_precos || ""} onChange={set("politica_precos")} />
          <TextField label="Tabela de preços padrão" value={form.tabela_precos_padrao || ""} onChange={set("tabela_precos_padrao")} />
          <TextField label="Desconto máximo (%)" value={form.desconto_maximo_pct || ""} onChange={set("desconto_maximo_pct")} type="number" />
          <TextField label="Comissão padrão (%)" value={form.comissao_padrao_pct || ""} onChange={set("comissao_padrao_pct")} type="number" />
          <TextField label="Meta mensal (R$)" value={form.meta_mensal || ""} onChange={set("meta_mensal")} type="number" />
          <TextField label="Meta anual (R$)" value={form.meta_anual || ""} onChange={set("meta_anual")} type="number" />
        </div>
      </Section>
    </div>
  );
}
