import { useEffect, useState } from 'react'
import { getOfferingCandidates, getDeployConfig, createOffering, getOfferings } from '../api'

/**
 * Issuance console — turn a "Token Offering"-stage deal into a live offering.
 *
 * Flow:
 *   1. Pick a candidate deal (already at the Token Offering stage).
 *   2. Set token economics → generate the exact contract-deploy config.
 *   3. Run the printed command on your machine (testnet) → paste addresses.
 *   4. Publish → it goes live in the investor app + website.
 *
 * Everything defaults to TESTNET. Mainnet ("live") waits until the LLC and
 * legal structure are in place.
 */
export default function Issuance() {
  const [candidates, setCandidates] = useState([])
  const [published, setPublished] = useState([])
  const [sel, setSel] = useState(null)
  const [econ, setEcon] = useState({ symbol: '', total_tokens: 100000, sale_tokens: 70000, token_price_usd: 25, network: 'baseSepolia', agent_address: '' })
  const [cfg, setCfg] = useState(null)
  const [addr, setAddr] = useState({ token_address: '', sale_address: '', distribution_vault_address: '', usdc_address: '' })
  const [msg, setMsg] = useState('')

  async function load() {
    const [c, p] = await Promise.all([getOfferingCandidates(), getOfferings(false)])
    setCandidates(c.data.candidates)
    setPublished(p.data.offerings)
  }
  useEffect(() => { load() }, [])

  async function genConfig() {
    if (!sel) return
    const { data } = await getDeployConfig({ lead_id: sel.lead_id, ...econ })
    setCfg(data)
  }

  async function publish() {
    if (!sel) return
    try {
      await createOffering({
        lead_id: sel.lead_id,
        symbol: econ.symbol,
        chain: econ.network === 'base' ? 'base' : 'base-sepolia',
        total_tokens: econ.total_tokens,
        sale_tokens: econ.sale_tokens,
        token_price_usdc: econ.token_price_usd,
        ...addr,
        is_live: true,
      })
      setMsg('Published — now live in the investor app & website.')
      setSel(null); setCfg(null); setAddr({ token_address: '', sale_address: '', distribution_vault_address: '', usdc_address: '' })
      load()
    } catch (e) {
      setMsg('Publish failed: ' + (e?.response?.data?.detail || e.message))
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-baseline justify-between mb-1">
        <h1 className="text-2xl font-bold">Issuance Console</h1>
        <span className="badge-warm">Testnet — not live until legal is ready</span>
      </div>
      <p className="text-gray-500 text-sm mb-6">Publish a Token Offering–stage deal as on-chain tokens.</p>

      {msg && <div className="card p-3 mb-4 text-sm text-vesta-100">{msg}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Candidates */}
        <div className="card p-4">
          <h2 className="font-semibold mb-3">1 · Candidate deals</h2>
          {candidates.length === 0 && <p className="text-gray-500 text-sm">No deals at the Token Offering stage yet. Move one there in the pipeline.</p>}
          {candidates.map((c) => (
            <button
              key={c.lead_id}
              onClick={() => { setSel(c); setEcon((e) => ({ ...e, symbol: e.symbol || '' })) }}
              className={`block w-full text-left p-3 rounded-lg mb-2 border ${sel?.lead_id === c.lead_id ? 'border-vesta-500 bg-vesta-900/30' : 'border-gray-800 hover:bg-gray-800'}`}
            >
              <div className="font-medium">{c.address}</div>
              <div className="text-xs text-gray-500">{c.property_type} · deal value ${Number(c.deal_value || 0).toLocaleString()} · score {c.score}</div>
            </button>
          ))}
        </div>

        {/* Economics + config */}
        <div className="card p-4">
          <h2 className="font-semibold mb-3">2 · Token economics</h2>
          {!sel ? (
            <p className="text-gray-500 text-sm">Select a candidate to configure.</p>
          ) : (
            <div className="space-y-3">
              <Field label="Symbol"><input className="inp" value={econ.symbol} onChange={(e) => setEcon({ ...econ, symbol: e.target.value.toUpperCase() })} placeholder="VATL" /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Total tokens"><input type="number" className="inp" value={econ.total_tokens} onChange={(e) => setEcon({ ...econ, total_tokens: +e.target.value })} /></Field>
                <Field label="For sale"><input type="number" className="inp" value={econ.sale_tokens} onChange={(e) => setEcon({ ...econ, sale_tokens: +e.target.value })} /></Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Price / token (USD)"><input type="number" className="inp" value={econ.token_price_usd} onChange={(e) => setEcon({ ...econ, token_price_usd: +e.target.value })} /></Field>
                <Field label="Network">
                  <select className="inp" value={econ.network} onChange={(e) => setEcon({ ...econ, network: e.target.value })}>
                    <option value="baseSepolia">Base Sepolia (testnet)</option>
                    <option value="base">Base mainnet (live)</option>
                  </select>
                </Field>
              </div>
              <Field label="Transfer agent address (optional)"><input className="inp" value={econ.agent_address} onChange={(e) => setEcon({ ...econ, agent_address: e.target.value })} placeholder="defaults to your deployer" /></Field>
              <div className="text-xs text-gray-500">Target raise: ${(econ.sale_tokens * econ.token_price_usd).toLocaleString()}</div>
              <button onClick={genConfig} className="btn-primary w-full">Generate deploy config</button>
            </div>
          )}
        </div>
      </div>

      {/* Deploy + publish */}
      {cfg && (
        <div className="card p-4 mt-6">
          <h2 className="font-semibold mb-3">3 · Deploy contracts, then publish</h2>
          <p className="text-sm text-gray-400 mb-2">Paste this into <code className="text-vesta-100">contracts/.env</code> and run the command:</p>
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-green-300 overflow-x-auto whitespace-pre-wrap">{cfg.env_block}</pre>
          <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-vesta-100 mt-2">{cfg.command}</pre>

          <h3 className="font-medium mt-4 mb-2 text-sm">Paste deployed addresses</h3>
          <div className="grid grid-cols-2 gap-3">
            {['token_address', 'sale_address', 'distribution_vault_address', 'usdc_address'].map((k) => (
              <Field key={k} label={k.replace(/_/g, ' ')}>
                <input className="inp" value={addr[k]} onChange={(e) => setAddr({ ...addr, [k]: e.target.value })} placeholder="0x…" />
              </Field>
            ))}
          </div>
          <button onClick={publish} className="btn-primary mt-4" disabled={!addr.token_address || !addr.sale_address}>
            Publish offering (go live in app & site)
          </button>
        </div>
      )}

      {/* Published */}
      <div className="card p-4 mt-6">
        <h2 className="font-semibold mb-3">Published offerings</h2>
        {published.length === 0 ? (
          <p className="text-gray-500 text-sm">None yet.</p>
        ) : (
          published.map((o) => (
            <div key={o.id} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
              <div><span className="font-medium">{o.name}</span> <span className="text-gray-500 text-sm">· {o.symbol} · {o.chain}</span></div>
              <span className={o.is_live ? 'badge-hot' : 'badge-cold'}>{o.is_live ? 'LIVE' : 'draft'}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-500 mb-1 capitalize">{label}</span>
      {children}
    </label>
  )
}
