export type TipoConversa = "dm" | "grupo" | "canal_departamento" | "ticket";

export interface ConversaChat {
  id: number;
  tipo: TipoConversa;
  nome: string | null;
  descricao: string | null;
  foto_url: string | null;
  departamento: string | null;
  loja_id: number | null;
  ticket_ref_id: number | null;
  criado_por: number | null;
  created_at: string;
  ultima_atividade: string | null;
  assunto?: string;
  cliente?: string;
  canal_externo?: string;
  ticket_status?: string;
}

export interface MensagemChat {
  id: number;
  conversa_id: number;
  thread_pai_id: number | null;
  remetente_id: number | null;
  texto: string | null;
  anexo_id: number | null;
  created_at: string;
  editado_em: string | null;
  excluido_em: string | null;
}

export interface AnexoChat {
  id: number;
  nome_arquivo: string;
  mime: string | null;
  tamanho_bytes: number | null;
  storage_path: string;
  enviado_por: number | null;
  created_at: string;
}

export interface ParticipanteChat {
  user_id: number;
  nome: string;
  papel: string | null;
}
