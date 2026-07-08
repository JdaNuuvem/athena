import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [err, setErr] = useState('')
  const { login } = useAuth()
  const nav = useNavigate()

  const submit = async (e: React.FormEvent) => { e.preventDefault(); setErr(''); const ok = await login(u, p); if (ok) nav('/'); else setErr('Invalid credentials') }

  return (
    <div className="min-h-screen flex items-center justify-center bg-athena-900">
      <form onSubmit={submit} className="bg-athena-800 p-8 rounded-xl border border-athena-700 w-96 shadow-2xl">
        <h1 className="text-athena-accent text-2xl font-bold text-center mb-6">⚡ ATHENA OS</h1>
        {err && <div className="bg-athena-error/20 text-athena-error text-sm p-2 rounded mb-4 text-center">{err}</div>}
        <input value={u} onChange={e => setU(e.target.value)} placeholder="Username" className="w-full bg-athena-900 border border-athena-700 rounded p-2.5 text-athena-200 mb-3 focus:border-athena-accent focus:outline-none" autoFocus />
        <input value={p} onChange={e => setP(e.target.value)} type="password" placeholder="Password" className="w-full bg-athena-900 border border-athena-700 rounded p-2.5 text-athena-200 mb-4 focus:border-athena-accent focus:outline-none" />
        <button type="submit" className="w-full bg-athena-accent text-athena-900 font-semibold py-2.5 rounded hover:brightness-110 transition">Sign In</button>
        <p className="text-athena-600 text-xs text-center mt-4">admin / athena-admin-2026</p>
      </form>
    </div>
  )
}
