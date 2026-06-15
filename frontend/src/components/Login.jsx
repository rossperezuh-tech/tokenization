import { useState } from 'react'
import { login } from '../api'

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(password)
      onSuccess()
    } catch {
      setError('Incorrect password')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950">
      <form onSubmit={submit} className="card w-full max-w-sm p-8">
        <div className="flex items-center gap-3 mb-6">
          <span className="text-2xl font-bold text-white">◈ Vesta</span>
          <span className="text-xs text-gray-500 uppercase tracking-widest">Operator</span>
        </div>
        <label className="block text-sm text-gray-400 mb-2">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white outline-none focus:border-vesta-500"
          placeholder="••••••••"
        />
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        <button type="submit" disabled={busy} className="btn-primary w-full mt-5 py-2.5">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
