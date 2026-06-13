import { useEffect, useState } from 'react'
import { generateEmail, sendEmail } from '../api'

export default function OutreachModal({ lead, onClose }) {
  const [emailData, setEmailData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)

  useEffect(() => {
    generateEmail(lead.id).then(({ data }) => {
      setEmailData(data)
      setLoading(false)
    })
  }, [lead.id])

  const handleSend = async () => {
    setSending(true)
    try {
      await sendEmail(lead.id)
      setSent(true)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <div>
            <h3 className="font-semibold text-white">Outreach Email</h3>
            <p className="text-xs text-gray-500">{lead.address} · Score {lead.score}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">×</button>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center text-gray-500">Generating…</div>
        ) : (
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">To</label>
              <div className="bg-gray-800 rounded px-3 py-2 text-sm text-gray-300">
                {emailData.recipient || '(no email on file)'}
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Subject</label>
              <div className="bg-gray-800 rounded px-3 py-2 text-sm text-gray-200 font-medium">
                {emailData.subject}
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Body</label>
              <pre className="bg-gray-800 rounded px-3 py-3 text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed overflow-y-auto max-h-72">
                {emailData.body}
              </pre>
            </div>
            <p className="text-xs text-gray-600">
              Type: <code className="bg-gray-800 px-1 rounded">{emailData.email_type}</code>
              {' · '}Remember to replace <code className="bg-gray-800 px-1 rounded">[YOUR NAME]</code> and <code className="bg-gray-800 px-1 rounded">[YOUR PHONE]</code>
            </p>
          </div>
        )}

        <div className="flex gap-3 justify-end px-5 py-4 border-t border-gray-800">
          <button onClick={onClose} className="btn-ghost">Cancel</button>
          {sent ? (
            <span className="text-green-400 text-sm font-medium self-center">✓ Email queued via Resend</span>
          ) : (
            <button
              onClick={handleSend}
              disabled={sending || !emailData?.recipient}
              className="btn-primary disabled:opacity-40"
            >
              {sending ? 'Sending…' : 'Send via Resend'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
