export interface Ticket {
  id: number;
  numero: string | null;
  cliente: string;
  email?: string;
  telefone?: string;
  assunto: string;
  canal: string;
  prioridade: "baixa" | "normal" | "alta" | "urgente";
  status: "aberto" | "pendente" | "fechado";
  atendente_id: number | null;
  sla_vencimento: string | null;
  data_abertura: string;
  data_fechamento: string | null;
  tempo_resposta_min: number | null;
  observacoes?: string;
  error?: string;
}

export interface MensagemTicket {
  id: number;
  conversa_id: number;
  thread_pai_id: number | null;
  remetente_id: number | null;
  remetente_nome?: string;
  texto: string;
  anexo_id: number | null;
  anexo_url: string | null;
  created_at: string;
  editado_em: string | null;
  excluido_em: string | null;
  error?: string;
}

export interface MensagemTicketRaw {
  id: number;
  ticket_id: number;
  remetente: number | null;
  conteudo: string;
  tipo: string;
  anexo_url: string | null;
  enviado_em: string;
  error?: string;
}

export interface Atendente {
  id: number;
  nome: string;
}

export interface Notificacao {
  id: number;
  usuario_id: number;
  tipo: string;
  titulo: string;
  mensagem: string;
  link: string | null;
  lida: boolean;
  created_at: string;
}
