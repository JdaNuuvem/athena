"use client";

import BlingVendasTab from "../_components/BlingVendasTab";
import BlingOrdersTab from "../_components/BlingOrdersTab";

export default function BlingPedidosVendaPage() {
  return (
    <div className="space-y-6">
      <BlingVendasTab />
      <BlingOrdersTab />
    </div>
  );
}
