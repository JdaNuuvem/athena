import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import AgentDetail from './pages/AgentDetail'
import Workflows from './pages/Workflows'
import Metrics from './pages/Metrics'
import Business from './pages/Business'
import ShopeeIntegration from './pages/ShopeeIntegration'
import Integrations from './pages/Integrations'
import BlingIntegration from './pages/BlingIntegration'
import HermesIntegration from './pages/HermesIntegration'
import ShopeeAdsIntegration from './pages/ShopeeAdsIntegration'
import Produtos from './pages/Produtos'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout><Dashboard /></Layout></ProtectedRoute>} />
        <Route path="/agents" element={<ProtectedRoute><Layout><Agents /></Layout></ProtectedRoute>} />
        <Route path="/agents/:id" element={<ProtectedRoute><Layout><AgentDetail /></Layout></ProtectedRoute>} />
        <Route path="/workflows" element={<ProtectedRoute><Layout><Workflows /></Layout></ProtectedRoute>} />
        <Route path="/metrics" element={<ProtectedRoute><Layout><Metrics /></Layout></ProtectedRoute>} />
        <Route path="/business" element={<ProtectedRoute><Layout><Business /></Layout></ProtectedRoute>} />
        <Route path="/shopee" element={<ProtectedRoute><Layout><ShopeeIntegration /></Layout></ProtectedRoute>} />
        <Route path="/bling" element={<ProtectedRoute><Layout><BlingIntegration /></Layout></ProtectedRoute>} />
        <Route path="/hermes" element={<ProtectedRoute><Layout><HermesIntegration /></Layout></ProtectedRoute>} />
        <Route path="/shopee-ads" element={<ProtectedRoute><Layout><ShopeeAdsIntegration /></Layout></ProtectedRoute>} />
        <Route path="/integrations" element={<ProtectedRoute><Layout><Integrations /></Layout></ProtectedRoute>} />
        <Route path="/produtos" element={<ProtectedRoute><Layout><Produtos /></Layout></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
