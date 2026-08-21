import { redirect } from "next/navigation";

// O modulo Bling agora vive em /bling (fase 6). A remocao definitiva desta
// rota e o ajuste do card em /integracoes sao trabalho da fase 7.
export default function BlingLegacyPage() {
  redirect("/bling");
}
