"use client";
import type { ParticipanteChat } from "@/lib/types/chat";
import { construirMarcadorUsuario, construirMarcadorTodos, construirMarcadorDepartamento } from "@/lib/chatMencoes";

export default function MencaoAutocomplete({
  participantes, filtro, mostrarTodos, departamento, onSelecionar,
}: {
  participantes: ParticipanteChat[];
  filtro: string;
  mostrarTodos: boolean;
  departamento: string | null;
  onSelecionar: (marcador: string) => void;
}) {
  const filtroBusca = filtro.toLowerCase();
  const opcoes: { chave: string; rotulo: string; marcador: string }[] = [];

  if (mostrarTodos && "todos".includes(filtroBusca)) {
    opcoes.push({ chave: "todos", rotulo: "todos", marcador: construirMarcadorTodos() });
  }
  if (departamento && departamento.toLowerCase().includes(filtroBusca)) {
    opcoes.push({
      chave: "dept", rotulo: departamento,
      marcador: construirMarcadorDepartamento(departamento, departamento),
    });
  }
  for (const p of participantes) {
    if (p.nome.toLowerCase().includes(filtroBusca)) {
      opcoes.push({ chave: `u${p.user_id}`, rotulo: p.nome, marcador: construirMarcadorUsuario(p.user_id, p.nome) });
    }
  }

  if (opcoes.length === 0) return null;

  return (
    <div className="absolute bottom-full mb-1 left-0 bg-neutral-800 border border-neutral-700 rounded-lg shadow-lg max-h-48 overflow-y-auto w-56 z-10">
      {opcoes.map((o) => (
        <button
          key={o.chave} type="button"
          onClick={() => onSelecionar(o.marcador)}
          className="block w-full text-left px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700"
        >
          @{o.rotulo}
        </button>
      ))}
    </div>
  );
}
