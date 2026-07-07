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
import { Settings } from './pages/Settings'
import { Finance } from './pages/Finance'
import { TaxIntelligence } from './pages/TaxIntelligence'
import { Chat } from './pages/Chat'
import { Products } from './pages/Products'

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
              <Route path="/settings" element={<Settings />} />
              <Route path="/finance" element={<Finance />} />
              <Route path="/tax-intelligence" element={<TaxIntelligence />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/products" element={<Products />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ApolloProvider>
  )
}
