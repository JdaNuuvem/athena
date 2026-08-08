"use client";

import { useStore } from "@/lib/store-context";
import EstoqueFisicoI9Logic from "./_components/EstoqueFisicoI9Logic";
import EstoqueRapidoVirtual from "./_components/EstoqueRapidoVirtual";
import AnunciosShopeeTab from "./_components/AnunciosShopeeTab";

export default function EstoquePage() {
  const { lojaId, lojas, tipoLojaSelecionada } = useStore();
  const loja = lojas.find(l => String(l.id) === lojaId);

  return (
    <div className="p-4 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Estoque</h1>
        <p className="text-xs text-neutral-500 mt-1">
          {loja ? `Loja: ${loja.nome}` : "Selecione uma loja no topo da pagina"}
        </p>
      </div>

      {!loja ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">Selecione uma loja para ver o estoque</p>
          <p className="text-neutral-600 text-xs mt-1">
            Lojas fisicas mostram o estoque ao vivo da i9Logic; lojas online usam o estoque rapido local.
          </p>
        </div>
      ) : tipoLojaSelecionada === "fisica" ? (
        <EstoqueFisicoI9Logic lojaId={loja.id} lojaNome={loja.nome} />
      ) : tipoLojaSelecionada === "virtual" && loja.shopee_conectado ? (
        <AnunciosShopeeTab lojaId={loja.id} lojaNome={loja.nome} />
      ) : (
        <EstoqueRapidoVirtual lojaNome={loja.nome} />
      )}
    </div>
  );
}
