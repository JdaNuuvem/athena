"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Section, TextField, TextAreaField, CheckboxField, strVal } from "./shared";

const CAMPOS_VIRTUAL = [
  "dominio", "subdominio", "tema", "seo_title", "seo_description",
  "google_analytics_id", "google_tag_manager_id", "pixel_meta", "pixel_tiktok",
  "pixel_kwai", "politica_privacidade", "termos_uso",
];
const CAMPOS_DELIVERY = ["raio_entrega_km", "taxa_entrega", "tempo_medio_entrega_min", "regioes_atendidas", "retirada_loja"];

export default function VirtualDeliveryTab({ id, loja }: { id: number; loja: Record<string, unknown> | null }) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string>("");
  const [msg, setMsg] = useState<Record<string, string>>({});
  const [erro, setErro] = useState("");

  useEffect(() => {
    const todos = [...CAMPOS_VIRTUAL, ...CAMPOS_DELIVERY];
    const inicial: Record<string, string> = {};
    for (const c of todos) inicial[c] = strVal(loja, c);
    setForm(inicial);
  }, [loja]);

  const set = (campo: string) => (v: string) => setForm((p) => ({ ...p, [campo]: v }));

  const salvarVirtual = async () => {
    setSaving("virtual"); setErro("");
    try {
      const campos: Record<string, unknown> = {};
      for (const c of CAMPOS_VIRTUAL) campos[c] = form[c];
      const r = await api.lojasVirtualAtualizar(id, campos);
      if (r.error) { setErro(r.error); return; }
      setMsg((p) => ({ ...p, virtual: "Salvo!" }));
      setTimeout(() => setMsg((p) => ({ ...p, virtual: "" })), 2500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving("");
    }
  };

  const salvarDelivery = async () => {
    setSaving("delivery"); setErro("");
    try {
      const campos: Record<string, unknown> = {
        raio_entrega_km: form.raio_entrega_km ? Number(form.raio_entrega_km) : undefined,
        taxa_entrega: form.taxa_entrega ? Number(form.taxa_entrega) : undefined,
        tempo_medio_entrega_min: form.tempo_medio_entrega_min ? Number(form.tempo_medio_entrega_min) : undefined,
        regioes_atendidas: form.regioes_atendidas,
        retirada_loja: form.retirada_loja === "true",
      };
      const r = await api.lojasDeliveryAtualizar(id, campos);
      if (r.error) { setErro(r.error); return; }
      setMsg((p) => ({ ...p, delivery: "Salvo!" }));
      setTimeout(() => setMsg((p) => ({ ...p, delivery: "" })), 2500);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving("");
    }
  };

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      <Section title="Loja virtual" onSave={salvarVirtual} saving={saving === "virtual"} msg={msg.virtual}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Domínio" value={form.dominio || ""} onChange={set("dominio")} placeholder="minhaloja.com.br" />
          <TextField label="Subdomínio" value={form.subdominio || ""} onChange={set("subdominio")} />
          <TextField label="Tema" value={form.tema || ""} onChange={set("tema")} />
          <TextField label="SEO — título" value={form.seo_title || ""} onChange={set("seo_title")} />
          <TextField label="Google Analytics ID" value={form.google_analytics_id || ""} onChange={set("google_analytics_id")} />
          <TextField label="Google Tag Manager ID" value={form.google_tag_manager_id || ""} onChange={set("google_tag_manager_id")} />
          <TextField label="Pixel Meta" value={form.pixel_meta || ""} onChange={set("pixel_meta")} />
          <TextField label="Pixel TikTok" value={form.pixel_tiktok || ""} onChange={set("pixel_tiktok")} />
          <TextField label="Pixel Kwai" value={form.pixel_kwai || ""} onChange={set("pixel_kwai")} />
        </div>
        <TextAreaField label="SEO — descrição" value={form.seo_description || ""} onChange={set("seo_description")} rows={2} />
        <TextAreaField label="Política de privacidade" value={form.politica_privacidade || ""} onChange={set("politica_privacidade")} rows={3} />
        <TextAreaField label="Termos de uso" value={form.termos_uso || ""} onChange={set("termos_uso")} rows={3} />
      </Section>

      <Section title="Delivery" onSave={salvarDelivery} saving={saving === "delivery"} msg={msg.delivery}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <TextField label="Raio de entrega (km)" value={form.raio_entrega_km || ""} onChange={set("raio_entrega_km")} type="number" />
          <TextField label="Taxa de entrega (R$)" value={form.taxa_entrega || ""} onChange={set("taxa_entrega")} type="number" />
          <TextField label="Tempo médio (min)" value={form.tempo_medio_entrega_min || ""} onChange={set("tempo_medio_entrega_min")} type="number" />
        </div>
        <TextAreaField label="Regiões atendidas" value={form.regioes_atendidas || ""} onChange={set("regioes_atendidas")} rows={2} />
        <CheckboxField label="Retirada na loja" checked={form.retirada_loja === "true"} onChange={(v) => set("retirada_loja")(String(v))} />
      </Section>
    </div>
  );
}
