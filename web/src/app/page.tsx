"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";

// A Shopee redireciona para o dominio raiz apos a autorizacao (?code=...&shop_id=...)
// quando o Redirect URL cadastrado no Console e' so o dominio, sem o path do callback.
// Encaminha esses parametros para a rota real de troca de token em vez de derruba-los
// no redirect padrao para /dashboard.
// ponytail: precisa ser client component (nao Server Component lendo searchParams)
// porque producao serve um export estatico (output: 'export'), que nao suporta
// leitura de searchParams no servidor. window.location.href (nao o router do
// Next) forca uma navegacao real de pagina — /api/shopee/callback e' uma rota
// do backend Flask, nao uma rota client-side do Next.js.
function HomeRedirect() {
  const searchParams = useSearchParams();

  useEffect(() => {
    const code = searchParams.get("code");
    if (code) {
      const qs = new URLSearchParams();
      searchParams.forEach((value, key) => qs.set(key, value));
      window.location.href = `/api/shopee/callback?${qs.toString()}`;
    } else {
      window.location.href = "/dashboard";
    }
  }, [searchParams]);

  return null;
}

export default function Home() {
  return (
    <Suspense fallback={null}>
      <HomeRedirect />
    </Suspense>
  );
}
