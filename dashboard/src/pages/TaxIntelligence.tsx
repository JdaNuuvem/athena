import { FileText, Calculator, Shield } from 'lucide-react'

export function TaxIntelligence() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <FileText className="w-8 h-8 text-amber-400" />
        <h1 className="text-3xl font-bold">Tributário</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: 'ICMS ST', value: '—', icon: Calculator },
          { label: 'IPI', value: '—', icon: Calculator },
          { label: 'PIS/COFINS', value: '—', icon: Shield },
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
          Módulo de inteligência tributária em desenvolvimento. Classificação fiscal e cálculo de impostos via agentes especializados.
        </p>
      </div>
    </div>
  )
}
