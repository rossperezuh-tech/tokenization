import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend
} from 'recharts'
import { getAnalytics } from '../api'

const fmt = (n) => n >= 1e6 ? `$${(n/1e6).toFixed(1)}M` : `$${(n/1e3).toFixed(0)}K`
const PIE_COLORS = ['#ef4444', '#eab308', '#22c55e', '#4263eb', '#a855f7', '#06b6d4', '#f97316']

function StatCard({ label, value, sub }) {
  return (
    <div className="card p-4">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-sm font-medium text-gray-300 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

const DARK_TOOLTIP = {
  contentStyle: { background: '#1f2937', border: '1px solid #374151', borderRadius: 8 },
  labelStyle: { color: '#d1d5db' },
  itemStyle: { color: '#9ca3af' },
}

export default function Analytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAnalytics().then(({ data: d }) => { setData(d); setLoading(false) })
  }, [])

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-500">Loading analytics…</div>

  const { totals, this_week, this_month, avg_score, heat_distribution, pipeline, property_breakdown, daily_leads } = data

  const sourceWeek = [
    { name: 'Inbound', value: this_week.inbound },
    { name: 'Outbound', value: this_week.outbound },
  ]
  const sourceMonth = [
    { name: 'Inbound', value: this_month.inbound },
    { name: 'Outbound', value: this_month.outbound },
  ]
  const heatData = [
    { name: '🔴 Hot', value: heat_distribution.hot },
    { name: '🟡 Warm', value: heat_distribution.warm },
    { name: '🟢 Cold', value: heat_distribution.cold },
  ]
  const stageData = pipeline.by_stage.map(s => ({
    name: s.stage.replace(' ', '\n'),
    count: s.count,
    value: s.value / 1e6,
  }))

  return (
    <div className="p-6 space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Leads"    value={totals.all_leads} sub={`${totals.inbound} inbound / ${totals.outbound} outbound`} />
        <StatCard label="In Pipeline"    value={totals.in_pipeline} />
        <StatCard label="Pipeline Value" value={fmt(pipeline.total_value)} />
        <StatCard label="Avg Score"      value={`${avg_score.inbound} / ${avg_score.outbound}`} sub="Inbound / Outbound" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Leads over time */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-white mb-4">Leads Over Time (30d)</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={daily_leads}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#6b7280' }} />
              <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
              <Tooltip {...DARK_TOOLTIP} />
              <Line type="monotone" dataKey="count" stroke="#4263eb" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Source split */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-white mb-4">Leads by Source</h3>
          <div className="flex gap-6">
            <div className="flex-1">
              <div className="text-xs text-gray-500 mb-2 text-center">This week</div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={sourceWeek}>
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <Tooltip {...DARK_TOOLTIP} />
                  <Bar dataKey="value" fill="#4263eb" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1">
              <div className="text-xs text-gray-500 mb-2 text-center">This month</div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={sourceMonth}>
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
                  <Tooltip {...DARK_TOOLTIP} />
                  <Bar dataKey="value" fill="#3451d1" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Heat distribution */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-white mb-4">Lead Heat Distribution</h3>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width={160} height={160}>
              <PieChart>
                <Pie data={heatData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} dataKey="value">
                  {heatData.map((_, i) => (
                    <Cell key={i} fill={['#ef4444','#eab308','#22c55e'][i]} />
                  ))}
                </Pie>
                <Tooltip {...DARK_TOOLTIP} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {heatData.map((d, i) => (
                <div key={d.name} className="flex items-center gap-2 text-sm">
                  <span style={{ color: ['#ef4444','#eab308','#22c55e'][i] }}>●</span>
                  <span className="text-gray-300">{d.name}</span>
                  <span className="font-semibold text-white ml-auto">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Pipeline by stage */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-white mb-4">Pipeline by Stage (deals)</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={stageData} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 10, fill: '#6b7280' }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: '#9ca3af' }} width={80} />
              <Tooltip {...DARK_TOOLTIP} formatter={(v, n) => n === 'value' ? [`$${v.toFixed(1)}M`, 'Value'] : [v, 'Deals']} />
              <Bar dataKey="count" fill="#4263eb" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Property type table */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold text-white mb-4">Best Performing Property Types</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 uppercase border-b border-gray-800">
              <th className="text-left py-2 px-3">Type</th>
              <th className="text-right py-2 px-3">Leads</th>
              <th className="text-right py-2 px-3">Avg Score</th>
            </tr>
          </thead>
          <tbody>
            {property_breakdown.map(row => (
              <tr key={row.type} className="border-b border-gray-800/50">
                <td className="py-2 px-3 text-gray-200">{row.type}</td>
                <td className="py-2 px-3 text-right text-gray-400">{row.count}</td>
                <td className="py-2 px-3 text-right font-semibold text-white">{row.avg_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
