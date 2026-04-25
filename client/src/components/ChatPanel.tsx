import { useEffect, useRef } from 'react'

export interface Message {
  role: 'user' | 'assistant'
  text: string
  timestamp: string
  toolCalls?: { name: string; args: unknown }[]
}

interface Props {
  messages: Message[]
  loading: boolean
  onSend: (text: string) => void
}

const CATEGORY_ICONS: Record<string, string> = {
  food: '🛒', transport: '🚆', rent: '🏠',
  entertainment: '🎬', utilities: '💡', other: '📦',
}

function categoryIcon(cat: string) {
  return CATEGORY_ICONS[cat] ?? '📦'
}

export { categoryIcon }

export default function ChatPanel({ messages, loading, onSend }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function handleSend() {
    const val = inputRef.current?.value.trim()
    if (!val) return
    onSend(val)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 0,
      background: 'var(--card)', borderRadius: 'var(--radius)',
      padding: 16, height: '100%',
    }}>
      <h3 style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 10 }}>
        Chat with Finn
      </h3>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 4 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4, alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
            <div style={{
              padding: '10px 14px', borderRadius: 'var(--radius)',
              fontSize: '0.9rem', lineHeight: 1.5,
              background: m.role === 'user' ? 'var(--green)' : 'var(--card)',
              color: m.role === 'user' ? 'var(--dark)' : 'var(--text)',
              fontWeight: m.role === 'user' ? 500 : 400,
              border: m.role === 'assistant' ? '1px solid rgba(255,255,255,0.06)' : 'none',
              borderBottomRightRadius: m.role === 'user' ? 4 : undefined,
              borderBottomLeftRadius: m.role === 'assistant' ? 4 : undefined,
            }}>
              {m.text}
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--muted)', padding: '0 4px', textAlign: m.role === 'user' ? 'right' : 'left' }}>
              {m.timestamp}
            </div>
            {m.toolCalls?.map((tc, j) => (
              <details key={j} style={{
                background: 'rgba(0,220,132,0.05)', border: '1px solid rgba(0,220,132,0.15)',
                borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem',
              }}>
                <summary style={{ color: 'var(--green)', fontWeight: 600, cursor: 'pointer' }}>
                  ⚙ {tc.name}
                </summary>
                <pre style={{ marginTop: 8, color: 'var(--muted)', fontSize: '0.7rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {JSON.stringify(tc.args, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: 'flex-start', maxWidth: '80%' }}>
            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius)', fontSize: '0.9rem', color: 'var(--muted)', background: 'var(--card)', border: '1px solid rgba(255,255,255,0.06)' }}>
              Finn is thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input
          ref={inputRef}
          type="text"
          placeholder="Ask Finn something… e.g. 'What's my balance?'"
          disabled={loading}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
          style={{
            flex: 1, background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8,
            padding: '10px 14px', color: 'var(--text)', fontSize: '0.9rem',
            outline: 'none',
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading}
          style={{ background: 'var(--green)', color: 'var(--dark)', padding: '10px 18px', opacity: loading ? 0.4 : 1 }}
        >
          Send
        </button>
      </div>
    </div>
  )
}
