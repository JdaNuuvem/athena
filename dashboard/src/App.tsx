import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ApolloProvider } from '@apollo/client/react'
import { client } from './lib/apollo-client'
import { Sidebar } from './components/Sidebar'
import { Overview } from './pages/Overview'
import { Orders } from './pages/Orders'
import { Inventory } from './pages/Inventory'
import { Production } from './pages/Production'
import { Molds } from './pages/Molds'
import { Customers } from './pages/Customers'
import { Admin } from './pages/Admin'

export default function App() {
  return (
    <ApolloProvider client={client}>
      <BrowserRouter>
        <div className="flex min-h-screen bg-slate-950 text-slate-200">
          <Sidebar />
          <main className="flex-1 p-6 overflow-auto">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/inventory" element={<Inventory />} />
              <Route path="/production" element={<Production />} />
              <Route path="/molds" element={<Molds />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/admin" element={<Admin />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ApolloProvider>
  )
}
