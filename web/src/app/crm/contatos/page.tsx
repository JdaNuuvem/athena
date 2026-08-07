"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// ponytail: /crm/contatos (cad_clientes) e /crm/leads (crm_leads) viraram
// telas redundantes de pessoas no CRM — consolidado em /crm/leads a
// pedido do usuario. Redirect client-side, mesmo padrao de
// web/src/app/atendimento/chat/page.tsx. Backend (listar_clientes_filtrado,
// indices) fica intacto, so' a rota deixa de ser navegavel.
export default function CrmContatosRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace("/crm/leads"); }, [router]);
  return null;
}
