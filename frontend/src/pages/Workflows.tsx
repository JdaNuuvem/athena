import { useState, useEffect } from 'react'
import { useApi } from '../hooks/useAuth'

type Workflow = { instanceId: string; workflowName: string; status: string; startedAt: string; steps: Array<{ id: string; label: string; status: string }> }

export default function Workflows() {
  const api = useApi()
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [wfName, setWfName] = useState('order-processing')
  const [input, setInput] = useState('{"customerId":"CUST-001","skus":["PT-001"],"amount":150}')

  const trigger = async () => {
    const r = await api<{ instanceId: string; status: string }>('/api/workflows/trigger', { method: 'POST', body: JSON.stringify({ workflowName: wfName, input: JSON.parse(input) }) })
    if (r) alert(`Workflow ${r['instanceId']}: ${r['status']}`)
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-xl font-bold text-white">Workflows</h2>
        <p className="text-athena-600 text-sm">Deploy and monitor DAG workflows</p>
      </div>

      <div className="bg-athena-800 rounded-lg border border-athena-700 p-4">
        <h3 className="text-sm font-semibold text-athena-400 mb-3">Trigger Workflow</h3>
        <div className="flex gap-3">
          <select value={wfName} onChange={e => setWfName(e.target.value)} className="bg-athena-900 border border-athena-700 rounded px-3 py-2 text-sm text-athena-200">
            <option value="order-processing">order-processing</option>
            <option value="injection-quality-flow">injection-quality-flow</option>
            <option value="inventory-management-flow">inventory-management-flow</option>
            <option value="customer-intelligence-flow">customer-intelligence-flow</option>
          </select>
          <input value={input} onChange={e => setInput(e.target.value)} className="flex-1 bg-athena-900 border border-athena-700 rounded px-3 py-2 text-sm text-athena-200 font-mono" />
          <button onClick={trigger} className="bg-athena-accent text-athena-900 font-semibold px-4 py-2 rounded text-sm hover:brightness-110">Trigger</button>
        </div>
      </div>

      <div className="space-y-3">
        {workflows.map(wf => (
          <div key={wf.instanceId} className="bg-athena-800 rounded-lg border border-athena-700 p-4">
            <div className="flex items-center justify-between mb-3">
              <div><span className="text-athena-accent font-mono text-sm">{wf.instanceId}</span><span className="text-athena-600 text-xs ml-2">{wf.workflowName}</span></div>
              <span className={`px-2 py-0.5 rounded text-xs ${wf.status === 'completed' ? 'bg-athena-success/20 text-athena-success' : wf.status === 'failed' ? 'bg-athena-error/20 text-athena-error' : 'bg-athena-warn/20 text-athena-warn'}`}>{wf.status}</span>
            </div>
            <div className="flex gap-2">
              {wf.steps.map(s => (
                <div key={s.id} className={`flex-1 p-3 rounded text-center text-xs ${s.status === 'completed' ? 'bg-athena-success/10 text-athena-success' : s.status === 'running' ? 'bg-athena-accent/10 text-athena-accent' : 'bg-athena-700 text-athena-600'}`}>
                  <p className="font-medium mb-0.5">{s.label}</p><p className="opacity-60">{s.status}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
