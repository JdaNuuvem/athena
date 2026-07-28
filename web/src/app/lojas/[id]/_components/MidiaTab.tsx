"use client";

import { useEffect, useRef, useState } from "react";
import { api, lojasMidiaUpload } from "@/lib/api";
import { Section } from "./shared";

const TIPOS = [
  { value: "logo", label: "Logo" },
  { value: "banner", label: "Banner / Capa" },
  { value: "foto_fachada", label: "Fotos da fachada" },
  { value: "foto_interna", label: "Fotos internas" },
  { value: "galeria", label: "Galeria" },
  { value: "video", label: "Vídeo institucional" },
];

interface Midia { id: number; nome_original: string; mime_type: string; tags: string; }

export default function MidiaTab({ id }: { id: number }) {
  const [midia, setMidia] = useState<Midia[]>([]);
  const [uploading, setUploading] = useState<string>("");
  const [erro, setErro] = useState("");
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const carregar = () => {
    api.lojasMidiaListar(id).then((d) => setMidia((d.midia || []) as unknown as Midia[]));
  };

  useEffect(() => { carregar(); }, [id]);

  const upload = async (tipo: string, files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(tipo); setErro("");
    for (const file of Array.from(files)) {
      const r = await lojasMidiaUpload(id, tipo, file);
      if (r.error) { setErro(r.error); break; }
    }
    setUploading("");
    carregar();
  };

  const remover = async (midiaId: number) => {
    if (!confirm("Remover este arquivo?")) return;
    await api.lojasMidiaRemover(id, midiaId);
    carregar();
  };

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      {TIPOS.map((t) => {
        const itens = midia.filter((m) => m.tags === t.value);
        return (
          <Section key={t.value} title={t.label}>
            <div className="flex flex-wrap gap-3">
              {itens.map((m) => (
                <div key={m.id} className="relative group w-24 h-24 rounded-lg border border-neutral-700 bg-neutral-800 overflow-hidden">
                  {m.mime_type?.startsWith("image/") ? (
                    <img src={`/api/documentos/${m.id}`} alt={m.nome_original} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[10px] text-neutral-500 p-1 text-center">{m.nome_original}</div>
                  )}
                  <button
                    onClick={() => remover(m.id)}
                    className="absolute top-1 right-1 bg-red-600/80 hover:bg-red-600 text-white text-[10px] w-5 h-5 rounded-full opacity-0 group-hover:opacity-100"
                  >×</button>
                </div>
              ))}
              <button
                onClick={() => fileRefs.current[t.value]?.click()}
                disabled={uploading === t.value}
                className="w-24 h-24 rounded-lg border border-dashed border-neutral-700 text-neutral-500 hover:text-neutral-300 hover:border-neutral-500 text-xs flex items-center justify-center"
              >
                {uploading === t.value ? "Enviando..." : "+ Enviar"}
              </button>
              <input
                ref={(el) => { fileRefs.current[t.value] = el; }}
                type="file"
                accept={t.value === "video" ? "video/*" : "image/*"}
                multiple
                onChange={(e) => upload(t.value, e.target.files)}
                className="hidden"
              />
            </div>
          </Section>
        );
      })}
    </div>
  );
}
