import { DollarSign, TrendingUp, CreditCard, Wallet } from 'lucide-react'

export function Finance() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <DollarSign className="w-8 h-8 text-emerald-400" />
        <h1 className="text-3xl font-bold">Financeiro</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Receita (mês)', value: 'R$ —', icon: TrendingUp },
          { label: 'Despesas (mês)', value: 'R$ —', icon: CreditCard },
          { label: 'Lucro Bruto', value: 'R$ —', icon: DollarSign },
          { label: 'Saldo Caixa', value: 'R$ —', icon: Wallet },
        ].map((kpi) => (
          <div key={kpi.label} className="bg-slate-800 border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 text-slate-400 mb-2">
              <kpi.icon className="w-4 h-4" />
              <span className="text-sm">{kpi.label}</span>
            </div>
            <p className="text-2xl font-bold">{kpi.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
        <p className="text-slate-400 text-center py-12">
          Módulo financeiro em desenvolvimento. Conecte APIs bancárias e gateways de pagamento via MCP.
        </p>
      </div>
    </div>
  )
}
