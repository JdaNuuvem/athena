"use client";

import { useState } from "react";

export function LoginForm({ onLogin, error }: { onLogin: (nome: string, senha: string) => Promise<void>; error: string }) {
  const [loginNome, setLoginNome] = useState("");
  const [loginSenha, setLoginSenha] = useState("");

  const handleLogin = () => onLogin(loginNome, loginSenha);

  return (
    <div className="h-screen flex items-center justify-center bg-neutral-950">
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-8 w-96">
        <h1 className="text-xl font-bold text-neutral-200 mb-2">PDV — Login</h1>
        <p className="text-sm text-neutral-500 mb-6">Identifique-se para operar o caixa</p>
        <div className="space-y-4">
          <input type="text" value={loginNome} onChange={e => setLoginNome(e.target.value)}
            placeholder="Nome do operador" autoFocus
            onKeyDown={e => e.key === "Enter" && handleLogin()}
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-3 text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
          <input type="password" value={loginSenha} onChange={e => setLoginSenha(e.target.value)}
            placeholder="Senha"
            onKeyDown={e => e.key === "Enter" && handleLogin()}
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-3 text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button onClick={handleLogin} className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg transition-colors">
            Entrar
          </button>
        </div>
        <p className="text-[10px] text-neutral-600 mt-4 text-center">Operador padrao: Admin / admin</p>
      </div>
    </div>
  );
}
