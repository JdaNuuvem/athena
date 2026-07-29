"use client";
import type { ParticipanteChat } from "@/lib/types/chat";

// Mantenha este regex em sincronia com _PADRAO_MENCAO em hermes_agents/core/chat.py.
const PADRAO_MENCAO = /@\[(?:user:(\d+):([^\]]*)|todos|dept:([a-z_]+):([^\]]*))\]/g;

export function construirMarcadorUsuario(userId: number, nome: string): string {
  return `@[user:${userId}:${nome}]`;
}

export function construirMarcadorTodos(): string {
  return "@[todos]";
}

export function construirMarcadorDepartamento(codigo: string, nome: string): string {
  return `@[dept:${codigo}:${nome}]`;
}

interface TrechoTexto {
  chave: string;
  texto: string;
  ehMencao: boolean;
}

export function partirMencoes(texto: string, participantes: ParticipanteChat[]): TrechoTexto[] {
  const nomePorId = new Map(participantes.map((p) => [p.user_id, p.nome]));
  const partes: TrechoTexto[] = [];
  const regex = new RegExp(PADRAO_MENCAO.source, "g");
  let ultimoIndice = 0;
  let contador = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(texto)) !== null) {
    if (match.index > ultimoIndice) {
      partes.push({ chave: `t${contador++}`, texto: texto.slice(ultimoIndice, match.index), ehMencao: false });
    }
    const [, userId, nomeSnapshotUser, deptCodigo, nomeSnapshotDept] = match;
    let rotulo: string;
    if (userId !== undefined) {
      rotulo = `@${nomePorId.get(Number(userId)) ?? nomeSnapshotUser}`;
    } else if (deptCodigo !== undefined) {
      rotulo = `@${nomeSnapshotDept}`;
    } else {
      rotulo = "@todos";
    }
    partes.push({ chave: `m${contador++}`, texto: rotulo, ehMencao: true });
    ultimoIndice = match.index + match[0].length;
  }
  if (ultimoIndice < texto.length) {
    partes.push({ chave: `t${contador++}`, texto: texto.slice(ultimoIndice), ehMencao: false });
  }
  return partes;
}

export function TextoComMencoes({ texto, participantes }: { texto: string; participantes: ParticipanteChat[] }) {
  const partes = partirMencoes(texto, participantes);
  return (
    <>
      {partes.map((p) =>
        p.ehMencao ? (
          <span key={p.chave} className="text-indigo-300 font-semibold">{p.texto}</span>
        ) : (
          <span key={p.chave}>{p.texto}</span>
        )
      )}
    </>
  );
}
