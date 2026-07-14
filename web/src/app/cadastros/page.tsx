"use client";

export default function CadastrosPage() {
  return (
    <div className="p-6 space-y-4">
      <div><h1 className="text-lg font-bold text-neutral-100">Cadastros</h1><p className="text-xs text-neutral-500 mt-1">Gerencie clientes, fornecedores e categorias</p></div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {["Clientes", "Fornecedores", "Categorias"].map(m => (
          <div key={m} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-neutral-200">{m}</h3>
            <p className="text-xs text-neutral-500 mt-1">Em construcao</p>
          </div>
        ))}
      </div>
    </div>
  );
}
