// Autolookup client-side de CNPJ (BrasilAPI) e CEP (ViaCEP) — dados
// publicos, sem chave de API, por isso chamados direto do navegador em vez
// de passar pelo backend.

export interface DadosCNPJ {
  razao_social?: string;
  nome_fantasia?: string;
  logradouro?: string;
  numero?: string;
  bairro?: string;
  municipio?: string;
  uf?: string;
  cep?: string;
  ddd_telefone_1?: string;
  email?: string;
}

export async function buscarCNPJ(cnpj: string): Promise<DadosCNPJ | null> {
  const d = cnpj.replace(/\D/g, "");
  if (d.length !== 14) return null;
  try {
    const r = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${d}`);
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

export interface DadosCEP {
  logradouro?: string;
  bairro?: string;
  localidade?: string;
  uf?: string;
  erro?: boolean;
}

export async function buscarCEP(cep: string): Promise<DadosCEP | null> {
  const d = cep.replace(/\D/g, "");
  if (d.length !== 8) return null;
  try {
    const r = await fetch(`https://viacep.com.br/ws/${d}/json/`);
    if (!r.ok) return null;
    const json = await r.json();
    if (json.erro) return null;
    return json;
  } catch { return null; }
}

// Aplica o resultado de buscarCNPJ() nos campos do formulario que existirem
// (cada tabela de Cadastros usa nomes de campo diferentes pra "nome" —
// razao_social em Empresas, nome nas demais — por isso o mapa cobre os
// dois e so' aplica o que a tabela atual realmente tem).
export function aplicarCNPJ(dados: DadosCNPJ, onChange: (key: string, value: string) => void, keysDisponiveis: Set<string>) {
  const mapa: Record<string, string | undefined> = {
    razao_social: dados.razao_social,
    nome: dados.razao_social,
    logradouro: dados.logradouro,
    numero: dados.numero,
    bairro: dados.bairro,
    cidade: dados.municipio,
    uf: dados.uf,
    cep: dados.cep,
    telefone: dados.ddd_telefone_1,
    email: dados.email,
  };
  for (const [k, v] of Object.entries(mapa)) {
    if (v && keysDisponiveis.has(k)) onChange(k, v);
  }
  // tabelas com endereco como campo unico de texto (ex.: cad_empresas.endereco)
  if (keysDisponiveis.has("endereco") && !keysDisponiveis.has("logradouro")) {
    const partes = [dados.logradouro, dados.numero, dados.bairro, dados.municipio, dados.uf].filter(Boolean);
    if (partes.length) onChange("endereco", partes.join(", "));
  }
}

export function aplicarCEP(dados: DadosCEP, onChange: (key: string, value: string) => void, keysDisponiveis: Set<string>) {
  const mapa: Record<string, string | undefined> = {
    logradouro: dados.logradouro,
    bairro: dados.bairro,
    cidade: dados.localidade,
    uf: dados.uf,
  };
  for (const [k, v] of Object.entries(mapa)) {
    if (v && keysDisponiveis.has(k)) onChange(k, v);
  }
}
