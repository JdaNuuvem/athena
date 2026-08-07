import { api } from "@/lib/api";
import type { CrudService } from "../../_components/CrudPanel";
import type { FkPickerService } from "../../_components/FkPicker";

// Serviço HTTP para o CrudPanel apontando pro modulo Compras (/api/compras/*)
// — o default do CrudPanel aponta pra /api/cadastros/*, entao toda aba de
// Compras precisa passar isso explicitamente.
export const comprasService: CrudService = {
  list: api.comprasList,
  listPaginado: api.comprasListPaginado,
  create: api.comprasCreate,
  update: api.comprasUpdate,
  delete: api.comprasDelete,
};

// FkPicker que busca em tabelas de Compras (ex.: "pedidos", "solicitacoes")
// em vez do default (/api/cadastros/*) — usado pra fornecedor_id continua
// no default, ja que fornecedor e' cadastro unico (cad_fornecedores).
export const fkComprasService: FkPickerService = {
  get: api.comprasGet,
  listPaginado: api.comprasListPaginado,
};
