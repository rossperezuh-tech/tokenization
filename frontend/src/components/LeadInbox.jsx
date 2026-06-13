import { useEffect, useState, useCallback } from 'react'
import { getLeads, moveToPipeline, generateEmail } from '../api'
import OutreachModal from './OutreachModal'

const fmt = (n) => n == null ? '—' : `$${(n >= 1e6 ? (n/1e6).toFixed(2)+'M' : n.toLocaleString())}`

function HeatBadge({ score }) {
  if (score >= 80) return <span className="badge-hot">🔴 Hot</span>
  if (score >= 50) return <span className="badge-warm">🟡 Warm</span>
  return <span className="badge-cold">🟢 Cold</span>
}

function SourceBadge({ source }) {
  const inbound = source?.includes('Inbound')
  return <span className={inbound ? 'badge-inbound' : 'badge-outbound'}>
    {inbound ? 'Inbound' : 'Outbound'}
  </span>
}

function ScoreBar({ score }) {
  const color = score >= 80 ? 'bg-red-500' : score >= 50 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm font-mono font-semibold">{score}</span>
    </div>
  )
}

export default function LeadInbox() {
  const [leads, setLeads] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [outreachLead, setOutreachLead] = useState(null)
  const [filter, setFilter] = useState({ source: '', minScore: '' })
  const [pipelineAdded, setPipelineAdded] = useState(new Set())
  const [toast, setToast] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (filter.source) params.source = filter.source
      if (filter.minScore) params.min_score = Number(filter.minScore)
      const { data } = await getLeads(params)
      setLeads(data.leads)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  const handlePipeline = async (lead) => {
    await moveToPipeline(lead.id)
    setPipelineAdded(prev => new Set([...prev, lead.id]))
    setToast(`${lead.address} added to pipeline`)
    setTimeout(() => setToast(null), 3000)
  }

  return (
    <div className="p-6">
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Lead Inbox</h2>
          <p className="text-sm text-gray-500">{total} leads · sorted by score</p>
        </div>
        <div className="flex gap-2">
          <select
            value={filter.source}
            onChange={e => setFilter(f => ({ ...f, source: e.target.value }))}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200"
          >
            <option value="">All sources</option>
            <option value="Inbound">Inbound only</option>
            <option value="Outbound">Outbound only</option>
          </select>
          <select
            value={filter.minScore}
            onChange={e => setFilter(f => ({ ...f, minScore: e.target.value }))}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200"
          >
            <option value="">All scores</option>
            <option value="80">Hot (80+)</option>
            <option value="50">Warm+ (50+)</option>
          </select>
          <button onClick={load} className="btn-ghost text-sm">↻ Refresh</button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-vesta-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm">
          ✓ {toast}
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wide">
                <th className="text-left px-4 py-3">Score</th>
                <th className="text-left px-4 py-3">Heat</th>
                <th className="text-left px-4 py-3">Source</th>
                <th className="text-left px-4 py-3">Address</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-left px-4 py-3">Price</th>
                <th className="text-left px-4 py-3">DOM</th>
                <th className="text-left px-4 py-3">Contact</th>
                <th className="text-left px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={9} className="text-center py-12 text-gray-500">Loading…</td>
                </tr>
              )}
              {!loading && leads.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center py-12 text-gray-500">
                    No leads yet. Run <code className="bg-gray-800 px-1 rounded">python demo_leads.py</code> to seed sample data.
                  </td>
                </tr>
              )}
              {leads.map(lead => (
                <tr
                  key={lead.id}
                  onClick={() => setSelected(selected?.id === lead.id ? null : lead)}
                  className={`border-b border-gray-800/50 cursor-pointer transition-colors ${
                    selected?.id === lead.id ? 'bg-gray-800' : 'hover:bg-gray-800/50'
                  }`}
                >
                  <td className="px-4 py-3">
                    <ScoreBar score={lead.score} />
                  </td>
                  <td className="px-4 py-3"><HeatBadge score={lead.score} /></td>
                  <td className="px-4 py-3"><SourceBadge source={lead.source} /></td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-white">{lead.address}</div>
                    <div className="text-gray-500 text-xs">{lead.city}, {lead.state}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-300">{lead.property_type || '—'}</td>
                  <td className="px-4 py-3 font-mono text-gray-200">{fmt(lead.asking_price)}</td>
                  <td className="px-4 py-3 text-gray-400">{lead.days_on_market != null ? `${lead.days_on_market}d` : '—'}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {lead.source?.includes('Inbound')
                      ? <>{lead.seller_name}<br/>{lead.seller_phone}</>
                      : <>{lead.broker_name}<br/>{lead.broker_phone}</>
                    }
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                      {!lead.in_pipeline && !pipelineAdded.has(lead.id) ? (
                        <button
                          onClick={() => handlePipeline(lead)}
                          className="btn-primary text-xs whitespace-nowrap"
                        >
                          + Pipeline
                        </button>
                      ) : (
                        <span className="text-xs text-vesta-500 font-medium">In pipeline</span>
                      )}
                      <button
                        onClick={() => setOutreachLead(lead)}
                        className="btn-ghost text-xs"
                      >
                        ✉ Email
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Expanded row detail */}
      {selected && (
        <div className="mt-4 card p-5 grid grid-cols-3 gap-6">
          <div>
            <h3 className="font-semibold text-white mb-2">{selected.address}</h3>
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Type</dt><dd>{selected.property_type || '—'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Price</dt><dd>{fmt(selected.asking_price)}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Sq Ft</dt><dd>{selected.sqft?.toLocaleString() || '—'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Cap Rate</dt><dd>{selected.cap_rate ? `${selected.cap_rate}%` : '—'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">DOM</dt><dd>{selected.days_on_market ?? '—'}</dd></div>
            </dl>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-2">Contact</h4>
            <dl className="space-y-1 text-sm">
              {selected.source?.includes('Inbound') ? <>
                <div><dt className="text-gray-500">Seller</dt><dd>{selected.seller_name}</dd></div>
                <div><dt className="text-gray-500">Email</dt><dd>{selected.seller_email || '—'}</dd></div>
                <div><dt className="text-gray-500">Phone</dt><dd>{selected.seller_phone || '—'}</dd></div>
              </> : <>
                <div><dt className="text-gray-500">Broker</dt><dd>{selected.broker_name}</dd></div>
                <div><dt className="text-gray-500">Email</dt><dd>{selected.broker_email || '—'}</dd></div>
                <div><dt className="text-gray-500">Phone</dt><dd>{selected.broker_phone || '—'}</dd></div>
              </>}
            </dl>
            {selected.reason_for_selling && (
              <div className="mt-3">
                <div className="text-gray-500 text-xs mb-1">Reason for selling</div>
                <p className="text-xs text-gray-300 italic">"{selected.reason_for_selling}"</p>
              </div>
            )}
          </div>
          <div>
            <h4 className="font-semibold text-white mb-2">Score Breakdown</h4>
            {selected.score_breakdown?.motivation && (
              <div className="space-y-2 text-xs">
                {[
                  ['Motivation Signals', selected.score_breakdown.motivation.subtotal, 40],
                  ['Tokenization Fit',   selected.score_breakdown.tokenization_fit.subtotal, 40],
                  ['Deal Quality',       selected.score_breakdown.deal_quality.subtotal, 20],
                ].map(([label, val, max]) => (
                  <div key={label}>
                    <div className="flex justify-between text-gray-400 mb-0.5">
                      <span>{label}</span><span>{val}/{max}</span>
                    </div>
                    <div className="h-1.5 bg-gray-700 rounded-full">
                      <div className="h-full bg-vesta-500 rounded-full" style={{ width: `${(val/max)*100}%` }} />
                    </div>
                  </div>
                ))}
                <div className="flex justify-between text-white font-semibold mt-2 pt-2 border-t border-gray-700">
                  <span>Total</span><span>{selected.score}/100</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {outreachLead && (
        <OutreachModal lead={outreachLead} onClose={() => setOutreachLead(null)} />
      )}
    </div>
  )
}
