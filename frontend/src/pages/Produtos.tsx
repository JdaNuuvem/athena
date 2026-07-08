import { useState, useEffect, useCallback } from 'react'
const n = (v: unknown, d = 0) => { const x = Number(v); return isNaN(x) ? d : x }
import { useApi } from '../hooks/useAuth'

interface ProdutoLoja {
  loja: string; preco: number; status: string
}
interface Produto {
  id: number; sku: string; nome: string; margem_pct: number
  receita_30d: number; vendidos_30d: number; total_lojas: number
  estoque_lojas: ProdutoLoja[]
}

export default function Produtos() {
  const api = useApi()
  const [produtos, setProdutos] = useState<Produto[]>([])
  const [total, setTotal] = useState(0)
  const [busca, setBusca] = useState('')
  const [lojaFiltro, setLojaFiltro] = useState('')
  const [margemMin, setMargemMin] = useState('')
  const [pagina, setPagina] = useState(1)
  const [loading, setLoading] = useState(false)
  const [expandido, setExpandido] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams({ pagina: String(pagina), por_pagina: '50' })
    if (busca) params.set('busca', busca)
    if (lojaFiltro) params.set('loja', lojaFiltro)
    if (margemMin) params.set('margem_min', margemMin)
    const data = await api<{ produtos: Produto[]; total: number }>(`/api/produtos?${params}`)
    if (data) { setProdutos(data.produtos); setTotal(data.total) }
    setLoading(false)
  }, [api, busca, lojaFiltro, margemMin, pagina])

  useEffect(() => { carregar() }, [carregar])

  const totalPaginas = Math.ceil(total / 50)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-white">📦 Produtos</h1>
        <p className="text-athena-600 text-sm">{total} produtos · {produtos.length} exibidos</p></div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4 space-y-3">
        <div className="flex gap-3 flex-wrap">
          <input value={busca} onChange={e => { setBusca(e.target.value); setPagina(1) }}
            placeholder="🔍 Buscar por SKU, nome..."
            className="flex-1 min-w-[200px] bg-athena-900 border border-athena-700 rounded px-3 py-2 text-sm text-white focus:border-athena-accent focus:outline-none" />
          <select value={lojaFiltro} onChange={e => { setLojaFiltro(e.target.value); setPagina(1) }}
            className="bg-athena-900 border border-athena-700 rounded px-3 py-2 text-sm text-white">
            <option value="">Todas as lojas</option>
            <option value="shopee">Shopee</option>
            <option value="mercado_livre">Mercado Livre</option>
            <option value="amazon">Amazon</option>
          </select>
          <select value={margemMin} onChange={e => { setMargemMin(e.target.value); setPagina(1) }}
            className="bg-athena-900 border border-athena-700 rounded px-3 py-2 text-sm text-white">
            <option value="">Qualquer margem</option>
            <option value="50">Margem &gt; 50%</option>
            <option value="30">Margem &gt; 30%</option>
            <option value="15">Margem &gt; 15%</option>
            <option value="0">Margem positiva</option>
          </select>
          <button onClick={carregar} disabled={loading}
            className="bg-athena-accent hover:bg-athena-accent/80 text-athena-900 px-4 py-2 rounded text-sm font-medium transition disabled:opacity-50">
            {loading ? 'Carregando...' : 'Buscar'}
          </button>
        </div>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-athena-700 bg-athena-900/50">
                <th className="text-left py-3 px-4 text-athena-400 font-medium">SKU</th>
                <th className="text-left py-3 px-4 text-athena-400 font-medium">Produto</th>
                <th className="text-right py-3 px-4 text-athena-400 font-medium">Lojas</th>
                <th className="text-right py-3 px-4 text-athena-400 font-medium">Vend. (30d)</th>
                <th className="text-right py-3 px-4 text-athena-400 font-medium">Receita</th>
                <th className="text-right py-3 px-4 text-athena-400 font-medium">Margem</th>
                <th className="text-center py-3 px-4 text-athena-400 font-medium">Detalhes</th>
              </tr>
            </thead>
            <tbody>
              {produtos.map(p => (
                <>
                  <tr key={p.sku} className="border-b border-athena-700/50 hover:bg-athena-900/30">
                    <td className="py-3 px-4 text-athena-accent font-mono text-xs">{p.sku}</td>
                    <td className="py-3 px-4 text-white font-medium">{p.nome}</td>
                    <td className="py-3 px-4 text-right text-white">{p.total_lojas}</td>
                    <td className="py-3 px-4 text-right text-white">{p.vendidos_30d}</td>
                    <td className="py-3 px-4 text-right text-white">R$ {n(p.receita_30d).toFixed(2)}</td>
                    <td className={`py-3 px-4 text-right font-medium ${n(p.margem_pct) >= 30 ? 'text-green-400' : n(p.margem_pct) >= 15 ? 'text-athena-accent' : n(p.margem_pct) > 0 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {n(p.margem_pct).toFixed(1)}%
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button onClick={() => setExpandido(expandido === p.sku ? null : p.sku)}
                        className="text-athena-accent hover:underline text-xs">
                        {expandido === p.sku ? '▲' : '▼'} Lojas
                      </button>
                    </td>
                  </tr>
                  {expandido === p.sku && (
                    <tr key={`${p.sku}-det`} className="bg-athena-900/50">
                      <td colSpan={7} className="p-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                          {p.estoque_lojas.map(e => (
                            <div key={`${p.sku}-${e.loja}`} className="bg-athena-900 rounded p-2 border border-athena-700">
                              <p className="text-athena-400 text-xs uppercase">{e.loja}</p>
                              <p className="text-white font-medium text-sm mt-1">
                                R$ {n(e.preco).toFixed(2)}
                              </p>
                              <span className={`text-xs px-1.5 py-0.5 rounded ${e.status === 'ativo' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                                {e.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
              {produtos.length === 0 && (
                <tr><td colSpan={7} className="text-center py-12 text-athena-600">Nenhum produto encontrado</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {totalPaginas > 1 && (
        <div className="flex justify-center gap-2">
          <button disabled={pagina <= 1} onClick={() => setPagina(p => p - 1)}
            className="px-3 py-1.5 rounded bg-athena-800 border border-athena-700 text-white text-sm disabled:opacity-50">←</button>
          <span className="px-4 py-1.5 text-athena-400 text-sm">Pág {pagina} de {totalPaginas}</span>
          <button disabled={pagina >= totalPaginas} onClick={() => setPagina(p => p + 1)}
            className="px-3 py-1.5 rounded bg-athena-800 border border-athena-700 text-white text-sm disabled:opacity-50">→</button>
        </div>
      )}
    </div>
  )
}
