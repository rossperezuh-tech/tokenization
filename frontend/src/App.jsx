import { useState } from 'react'
import LeadInbox from './components/LeadInbox'
import MapView from './components/MapView'
import PipelineKanban from './components/PipelineKanban'
import Analytics from './components/Analytics'
import Issuance from './components/Issuance'
import Login from './components/Login'
import { getToken, logout } from './api'

const TABS = [
  { id: 'inbox',    label: '📥 Lead Inbox' },
  { id: 'map',      label: '🗺️ Map View' },
  { id: 'pipeline', label: '📊 Pipeline' },
  { id: 'issuance', label: '🪙 Issuance' },
  { id: 'analytics',label: '📈 Analytics' },
]

export default function App() {
  const [tab, setTab] = useState('inbox')
  const [authed, setAuthed] = useState(!!getToken())

  if (!authed) return <Login onSuccess={() => setAuthed(true)} />

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold tracking-tight text-white">
            ◈ Vesta
          </span>
          <span className="text-xs text-gray-500 font-medium uppercase tracking-widest">
            Tokenization Pipeline
          </span>
        </div>
        <nav className="flex gap-1 items-center">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t.id
                  ? 'bg-vesta-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              {t.label}
            </button>
          ))}
          <button
            onClick={() => { logout(); setAuthed(false) }}
            className="ml-2 px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-white hover:bg-gray-800"
          >
            Sign out
          </button>
        </nav>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-auto">
        {tab === 'inbox'    && <LeadInbox />}
        {tab === 'map'      && <MapView />}
        {tab === 'pipeline' && <PipelineKanban />}
        {tab === 'issuance' && <Issuance />}
        {tab === 'analytics'&& <Analytics />}
      </main>
    </div>
  )
}
