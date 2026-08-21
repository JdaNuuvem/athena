"use client";

import { useState } from "react";
import BlingProductsTab from "../_components/BlingProductsTab";
import ProductFormModal from "../_components/ProductFormModal";
import BulkStockModal from "../_components/BulkStockModal";

export default function BlingProdutosPage() {
  const [showProductForm, setShowProductForm] = useState(false);
  const [showStockModal, setShowStockModal] = useState(false);

  return (
    <>
      <BlingProductsTab
        onNewProduct={() => setShowProductForm(true)}
        onStockManage={() => setShowStockModal(true)}
      />
      {showProductForm && (
        <ProductFormModal
          onClose={() => setShowProductForm(false)}
          onSaved={() => setShowProductForm(false)}
        />
      )}
      {showStockModal && <BulkStockModal onClose={() => setShowStockModal(false)} />}
    </>
  );
}
