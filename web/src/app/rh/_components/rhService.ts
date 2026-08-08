import { api } from "@/lib/api";
import type { CrudService } from "../../_components/CrudPanel";
import type { FkPickerService } from "../../_components/FkPicker";

// Serviço HTTP para o CrudPanel apontando pro modulo RH (/api/rh/*) — o
// default do CrudPanel aponta pra /api/cadastros/*.
export const rhService: CrudService = {
  list: api.rhList,
  listPaginado: api.rhListPaginado,
  create: api.rhCreate,
  update: api.rhUpdate,
  delete: api.rhDelete,
};

// FkPicker que busca em tabelas de RH (ex.: "funcionarios") em vez do
// default (/api/cadastros/*).
export const fkRhService: FkPickerService = {
  get: api.rhGet,
  listPaginado: api.rhListPaginado,
};
