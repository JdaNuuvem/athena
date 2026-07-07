import { useState, useEffect, useCallback } from 'react'
import { Package, Search, Plus, RefreshCw, Edit2, AlertTriangle } from 'lucide-react'

interface ShopeeItem {
  item_id: number
  item_status: string
  update_time: number
}

interface ProductItem {
  item_id?: number
  item_name: string
  item_sku: string
  item_status: string
  stock: number
  price: number
  available?: number
  reserved?: number
}

const STATUS_COLORS: Record<string, string> = {
  NORMAL: 'bg-green-500/20 text-green-300 border-green-500/20',
  DELETED: 'bg-red-500/20 text-red-300 border-red-500/20',
  BANNED: 'bg-red-500/20 text-red-300 border-red-500/20',
  UNLIST: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/20',
  REVIEWING: 'bg-blue-500/20 text-blue-300 border-blue-500/20',
}

export function Products() {
  const [products, setProducts] = useState<ProductItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [status, setStatus] = useState('NORMAL')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [editItem, setEditItem] = useState<ProductItem | null>(null)
  const [newStock, setNewStock] = useState(0)
  const [newPrice, setNewPrice] = useState(0)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ item_name: '', description: '', price: 0, stock: 0, category_id: 0, weight: 0, images: [] as string[] })

  const fetchProducts = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const resp = await fetch(`/api/shopee/products?status=${status}&offset=${page * 50}&limit=50`)
      if (!resp.ok) { setError(await resp.text()); setLoading(false); return }
      const data = await resp.json()
      const items = (data.items ?? []).map((i: ShopeeItem) => ({ item_id: i.item_id, item_name: `#${i.item_id}`, item_sku: '', item_status: i.item_status, stock: 0, price: 0 }))
      // Fetch base info for enriched data
      if (items.length > 0) {
        const ids = items.map((i: ShopeeItem) => i.item_id)
        const detailResp = await fetch(`/api/shopee/products/${ids[0]}`)
        if (detailResp.ok) {
          // Fetch remaining details in parallel
          const details = await Promise.all(ids.map(async (id: number) => {
            try {
              const r = await fetch(`/api/shopee/products/${id}`)
              return r.ok ? await r.json() : null
            } catch { return null }
          }))
          const merged = items.map((item: ProductItem, i: number) => {
            const detail = details[i] as Record<string, any> | null
            if (!detail) return item
            return {
              ...item,
              item_name: detail.item_name ?? item.item_name,
              item_sku: detail.item_sku ?? item.item_sku ?? '',
              stock: detail.stock_info_v2?.summary_info?.total_available_stock ?? 0,
              available: detail.stock_info_v2?.summary_info?.total_available_stock ?? 0,
              reserved: detail.stock_info_v2?.summary_info?.total_reserved_stock ?? 0,
              price: detail.price_info && detail.price_info.length > 0 ? detail.price_info[0].current_price : 0,
            }
          })
          setProducts(merged)
        } else {
          setProducts(items)
        }
      } else {
        setProducts([])
      }
      setTotal(data.total ?? 0)
    } catch { setError('Falha ao conectar com Shopee') }
    setLoading(false)
  }, [status, page])

  useEffect(() => { fetchProducts() }, [fetchProducts])

  async function handleSync() {
    setSyncing(true)
    try {
      const resp = await fetch('/api/shopee/sync', { method: 'POST' })
      await resp.json()
      await fetchProducts()
    } finally { setSyncing(false) }
  }

  async function handleUpdateStock() {
    if (!editItem?.item_id) return
    try {
      const resp = await fetch(`/api/shopee/products/${editItem.item_id}/stock`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stock: Number(newStock) }),
      })
      const data = await resp.json()
      if (data.success) { setEditItem(null); await fetchProducts() }
    } catch { /* ignore */ }
  }

  async function handleUpdatePrice() {
    if (!editItem?.item_id) return
    try {
      const resp = await fetch(`/api/shopee/products/${editItem.item_id}/price`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ price: Number(newPrice) }),
      })
      const data = await resp.json()
      if (data.success) { setEditItem(null); await fetchProducts() }
    } catch { /* ignore */ }
  }

  async function handleCreate() {
    try {
      const resp = await fetch('/api/shopee/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await resp.json()
      if (data.item_id) { setShowCreate(false); await fetchProducts() }
    } catch { /* ignore */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Package size={20} className="text-cyan-400" />
          <h2 className="text-lg font-semibold text-slate-200">Produtos Shopee</h2>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSync} disabled={syncing} className="flex items-center gap-2 bg-cyan-500/20 text-cyan-300 px-4 py-2 rounded-xl text-sm border border-cyan-500/20 hover:bg-cyan-500/30 transition-colors">
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Sincronizando...' : 'Sincronizar'}
          </button>
          <button onClick={() => { setShowCreate(true); setForm({ item_name: '', description: '', price: 0, stock: 0, category_id: 0, weight: 0, images: [] }) }} className="flex items-center gap-2 bg-sky-500/20 text-sky-300 px-4 py-2 rounded-xl text-sm border border-sky-500/20 hover:bg-sky-500/30 transition-colors">
            <Plus size={14} />
            Novo Produto
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 relative flex-1 max-w-xs">
          <Search size={16} className="text-slate-500 absolute left-3" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar por nome..." className="bg-slate-800/50 border border-slate-700/50 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 w-full focus:outline-none focus:border-cyan-500/50" />
        </div>
        <select value={status} onChange={e => setStatus(e.target.value)} className="bg-slate-800/50 border border-slate-700/50 rounded-xl px-3 py-2 text-sm text-slate-200">
          <option value="NORMAL">Ativos</option>
          <option value="UNLIST">Não listados</option>
          <option value="BANNED">Banidos</option>
          <option value="DELETED">Excluídos</option>
          <option value="REVIEWING">Em revisão</option>
        </select>
        <span className="text-xs text-slate-500">{total} produtos</span>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-300">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {products.length === 0 && !loading && !error && (
        <div className="text-center text-slate-500 py-12 bg-slate-800/20 rounded-xl border border-slate-700/30">
          {status === 'NORMAL' ? 'Nenhum produto encontrado. Clique em "Sincronizar" para importar da Shopee.' : 'Nenhum produto com status ' + status}
        </div>
      )}

      {products.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-700/30">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-800/30 text-slate-400 text-xs">
                <th className="text-left px-4 py-3">Produto</th>
                <th className="text-left px-4 py-3">SKU</th>
                <th className="text-center px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">Estoque</th>
                <th className="text-right px-4 py-3">Reservado</th>
                <th className="text-right px-4 py-3">Preço</th>
                <th className="text-center px-4 py-3 w-20">Ações</th>
              </tr>
            </thead>
            <tbody>
              {products.filter(p => !search || p.item_name.toLowerCase().includes(search.toLowerCase())).map(p => (
                <tr key={p.item_id} className="border-t border-slate-700/20 hover:bg-slate-800/20 transition-colors">
                  <td className="px-4 py-3 text-slate-200 max-w-xs truncate">{p.item_name}</td>
                  <td className="px-4 py-3 text-slate-500 font-mono text-xs">{p.item_sku || '-'}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded-lg text-xs border ${STATUS_COLORS[p.item_status] ?? 'bg-slate-800/50 text-slate-400 border-slate-700/50'}`}>
                      {p.item_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-200 tabular-nums">{p.available ?? p.stock}</td>
                  <td className="px-4 py-3 text-right text-slate-500 tabular-nums">{p.reserved ?? '-'}</td>
                  <td className="px-4 py-3 text-right text-slate-200 tabular-nums">{(p.price ?? 0) > 0 ? `R$ ${(p.price / 100).toFixed(2)}` : '-'}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => { setEditItem(p); setNewStock(p.available ?? p.stock); setNewPrice(p.price ?? 0) }} className="text-slate-500 hover:text-cyan-400 transition-colors">
                      <Edit2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > 50 && (
        <div className="flex justify-center gap-2">
          <button disabled={page === 0} onClick={() => setPage(p => p - 1)} className="px-3 py-1.5 text-xs rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-300 disabled:opacity-30">
            Anterior
          </button>
          <span className="text-xs text-slate-500 py-1.5">Página {page + 1} de {Math.ceil(total / 50)}</span>
          <button disabled={page >= Math.ceil(total / 50) - 1} onClick={() => setPage(p => p + 1)} className="px-3 py-1.5 text-xs rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-300 disabled:opacity-30">
            Próximo
          </button>
        </div>
      )}

      {/* Edit Modal */}
      {editItem && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setEditItem(null)}>
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-sm space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-md font-semibold text-slate-200">{editItem.item_name}</h3>
            <div>
              <label className="text-xs text-slate-400">Estoque</label>
              <input type="number" value={newStock} onChange={e => setNewStock(Number(e.target.value))} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1" />
            </div>
            <div>
              <label className="text-xs text-slate-400">Preço (centavos)</label>
              <input type="number" value={newPrice} onChange={e => setNewPrice(Number(e.target.value))} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditItem(null)} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200">Cancelar</button>
              <button onClick={handleUpdateStock} className="px-4 py-2 text-sm bg-cyan-500/20 text-cyan-300 rounded-xl border border-cyan-500/20">Atualizar Estoque</button>
              <button onClick={handleUpdatePrice} className="px-4 py-2 text-sm bg-sky-500/20 text-sky-300 rounded-xl border border-sky-500/20">Atualizar Preço</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-lg space-y-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-md font-semibold text-slate-200">Novo Produto na Shopee</h3>
            <div>
              <label className="text-xs text-slate-400">Nome *</label>
              <input value={form.item_name} onChange={e => setForm({ ...form, item_name: e.target.value })} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1" />
            </div>
            <div>
              <label className="text-xs text-slate-400">Descrição</label>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={3} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1 resize-none" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400">Preço (centavos)</label>
                <input type="number" value={form.price} onChange={e => setForm({ ...form, price: Number(e.target.value) })} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1" />
              </div>
              <div>
                <label className="text-xs text-slate-400">Estoque</label>
                <input type="number" value={form.stock} onChange={e => setForm({ ...form, stock: Number(e.target.value) })} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1" />
              </div>
              <div>
                <label className="text-xs text-slate-400">ID da Categoria</label>
                <input type="number" value={form.category_id} onChange={e => setForm({ ...form, category_id: Number(e.target.value) })} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1" />
              </div>
              <div>
                <label className="text-xs text-slate-400">Peso (g)</label>
                <input type="number" value={form.weight} onChange={e => setForm({ ...form, weight: Number(e.target.value) })} className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 mt-1" />
              </div>
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200">Cancelar</button>
              <button onClick={handleCreate} className="px-4 py-2 text-sm bg-sky-500/20 text-sky-300 rounded-xl border border-sky-500/20">Publicar Produto</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
