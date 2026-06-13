import { useEffect, useState, useCallback } from 'react'
import {
  DndContext, closestCenter, PointerSensor,
  useSensor, useSensors, DragOverlay
} from '@dnd-kit/core'
import {
  SortableContext, verticalListSortingStrategy, useSortable
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { getPipeline, updateStage, moveToPipeline } from '../api'

const fmt = (n) => n == null ? '—' : (n >= 1e6 ? `$${(n/1e6).toFixed(2)}M` : `$${n.toLocaleString()}`)
const STAGE_COLORS = {
  'New Lead':       'border-gray-600',
  'Contacted':      'border-blue-600',
  'Interested':     'border-yellow-600',
  'LOI Signed':     'border-orange-600',
  'Due Diligence':  'border-purple-600',
  'Token Offering': 'border-vesta-500',
  'Closed':         'border-green-600',
}

function DealCard({ item, isDragging }) {
  const heat = item.score >= 80 ? 'bg-red-900/30 border-red-700/50'
             : item.score >= 50 ? 'bg-yellow-900/20 border-yellow-700/40'
             : 'bg-gray-800 border-gray-700'

  return (
    <div className={`rounded-lg border p-3 ${heat} ${isDragging ? 'opacity-50' : ''} cursor-grab active:cursor-grabbing`}>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className="text-xs font-medium text-white leading-tight">{item.address}</span>
        <span className="text-xs font-mono font-semibold shrink-0 text-gray-300">{item.score}</span>
      </div>
      <div className="text-xs text-gray-400">{item.property_type} · {item.city}</div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs font-mono text-green-400">{fmt(item.deal_value || item.asking_price)}</span>
        <span className="text-xs text-gray-600">{item.days_on_market ? `${item.days_on_market}d` : ''}</span>
      </div>
    </div>
  )
}

function SortableCard({ item }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `${item.pipeline_id}`,
    data: { pipelineId: item.pipeline_id, currentStage: item.stage },
  })
  const style = { transform: CSS.Transform.toString(transform), transition }
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <DealCard item={item} isDragging={isDragging} />
    </div>
  )
}

function Column({ stage, items, color }) {
  const stageValue = items.reduce((s, i) => s + (i.deal_value || i.asking_price || 0), 0)
  return (
    <div className={`flex flex-col min-w-[210px] max-w-[210px] bg-gray-900 rounded-xl border-t-2 ${color} border-b border-x border-gray-800`}>
      <div className="px-3 py-2.5 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-200 uppercase tracking-wide truncate">{stage}</span>
          <span className="text-xs bg-gray-700 px-1.5 py-0.5 rounded-full text-gray-300 ml-2 shrink-0">{items.length}</span>
        </div>
        {stageValue > 0 && (
          <div className="text-xs text-green-500 font-mono mt-0.5">{fmt(stageValue)}</div>
        )}
      </div>
      <SortableContext items={items.map(i => `${i.pipeline_id}`)} strategy={verticalListSortingStrategy}>
        <div className="flex-1 overflow-y-auto p-2 space-y-2 kanban-col">
          {items.map(item => <SortableCard key={item.pipeline_id} item={item} />)}
          {items.length === 0 && (
            <div className="text-center text-xs text-gray-700 py-8">Drop here</div>
          )}
        </div>
      </SortableContext>
    </div>
  )
}

export default function PipelineKanban() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeItem, setActiveItem] = useState(null)

  const load = useCallback(async () => {
    const { data: d } = await getPipeline()
    setData(d)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  const handleDragStart = (event) => {
    const { active } = event
    const allItems = Object.values(data.by_stage).flat()
    setActiveItem(allItems.find(i => `${i.pipeline_id}` === active.id))
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    setActiveItem(null)
    if (!over || active.id === over.id) return

    const allItems = Object.values(data.by_stage).flat()
    const draggedItem = allItems.find(i => `${i.pipeline_id}` === active.id)
    if (!draggedItem) return

    // Find target stage: either a column header or another card's column
    let targetStage = null
    for (const [stage, items] of Object.entries(data.by_stage)) {
      if (items.some(i => `${i.pipeline_id}` === over.id)) {
        targetStage = stage
        break
      }
    }
    // Also check if dropped directly on a column (over.id === stage name)
    if (!targetStage && data.stages.includes(over.id)) {
      targetStage = over.id
    }
    if (!targetStage || targetStage === draggedItem.stage) return

    // Optimistic update
    setData(prev => {
      const next = { ...prev, by_stage: { ...prev.by_stage } }
      next.by_stage[draggedItem.stage] = next.by_stage[draggedItem.stage].filter(i => i.pipeline_id !== draggedItem.pipeline_id)
      const updated = { ...draggedItem, stage: targetStage }
      next.by_stage[targetStage] = [updated, ...next.by_stage[targetStage]]
      return next
    })

    await updateStage(draggedItem.pipeline_id, targetStage)
  }

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-500">Loading pipeline…</div>

  const totalValue = data?.total_pipeline_value || 0

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Tokenization Pipeline</h2>
          <p className="text-sm text-gray-500">
            {data?.total_deals} deals · Total value{' '}
            <span className="text-green-400 font-mono font-semibold">{fmt(totalValue)}</span>
          </p>
        </div>
        <button onClick={load} className="btn-ghost text-sm">↻ Refresh</button>
      </div>

      <div className="overflow-x-auto pb-4">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-3" style={{ minWidth: 'max-content' }}>
            {data?.stages.map(stage => (
              <Column
                key={stage}
                stage={stage}
                items={data.by_stage[stage] || []}
                color={STAGE_COLORS[stage] || 'border-gray-600'}
              />
            ))}
          </div>
          <DragOverlay>
            {activeItem && <DealCard item={activeItem} />}
          </DragOverlay>
        </DndContext>
      </div>

      {data?.total_deals === 0 && (
        <div className="text-center text-gray-500 mt-8">
          No deals in pipeline yet. Use the <strong className="text-gray-300">+ Pipeline</strong> button in Lead Inbox to add deals.
        </div>
      )}
    </div>
  )
}
