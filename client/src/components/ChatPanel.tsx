import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export interface Message {
  id?: string
  role: 'user' | 'assistant'
  text: string
  timestamp: string
  toolCalls?: { name: string; args: unknown }[]
  /** Skip the typing reveal for already-completed turns (e.g. on history rehydrate). */
  instant?: boolean
}

const CATEGORY_ICONS: Record<string, string> = {
  food: '🛒', transport: '🚆', rent: '🏠',
  entertainment: '🎬', utilities: '💡', other: '📦',
}
export function categoryIcon(cat: string) {
  return CATEGORY_ICONS[cat] ?? '📦'
}

/* ── Markdown components — tuned for the dark glass surface. ───────── */
const md = {
  p: ({ children }: any) => <p style={{ margin: '0 0 8px' }}>{children}</p>,
  h1: ({ children }: any) => <h3 style={{ margin: '6px 0 6px', fontSize: '1.02rem', fontWeight: 700 }}>{children}</h3>,
  h2: ({ children }: any) => <h4 style={{ margin: '6px 0 6px', fontSize: '0.96rem', fontWeight: 700 }}>{children}</h4>,
  h3: ({ children }: any) => <h5 style={{ margin: '6px 0 4px', fontSize: '0.9rem',  fontWeight: 600, color: 'var(--green)' }}>{children}</h5>,
  ul: ({ children }: any) => <ul style={{ margin: '4px 0 8px', paddingLeft: 18 }}>{children}</ul>,
  ol: ({ children }: any) => <ol style={{ margin: '4px 0 8px', paddingLeft: 20 }}>{children}</ol>,
  li: ({ children }: any) => <li style={{ margin: '2px 0' }}>{children}</li>,
  strong: ({ children }: any) => <strong style={{ color: 'var(--green)', fontWeight: 700 }}>{children}</strong>,
  em: ({ children }: any) => <em style={{ color: 'var(--text-2)' }}>{children}</em>,
  hr: () => <hr style={{ border: 'none', borderTop: '1px solid var(--glass-border)', margin: '10px 0' }} />,
  code: ({ children }: any) => (
    <code style={{
      background: 'rgba(255,255,255,0.08)', borderRadius: 4,
      padding: '1px 6px', fontSize: '0.82em', fontFamily: 'ui-monospace, monospace',
    }}>{children}</code>
  ),
  a: ({ href, children }: any) => (
    <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--green)' }}>{children}</a>
  ),
  table: ({ children }: any) => (
    <div style={{ overflowX: 'auto', margin: '6px 0 10px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>{children}</table>
    </div>
  ),
  thead: ({ children }: any) => <thead style={{ background: 'var(--green-soft)' }}>{children}</thead>,
  th: ({ children }: any) => (
    <th style={{
      textAlign: 'left', padding: '8px 10px',
      fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.04em',
      textTransform: 'uppercase', color: 'var(--green)',
      borderBottom: '1px solid var(--glass-border)',
    }}>{children}</th>
  ),
  td: ({ children }: any) => (
    <td style={{ padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>{children}</td>
  ),
  blockquote: ({ children }: any) => (
    <blockquote style={{
      margin: '6px 0', padding: '4px 10px',
      borderLeft: '3px solid var(--green)',
      background: 'var(--green-soft)', color: 'var(--text-2)',
    }}>{children}</blockquote>
  ),
}

function MarkdownMessage({ text }: { text: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={md}>{text}</ReactMarkdown>
}

/* ── Typing reveal — characters fade in over ~14ms each, capped. ───── */
function useTypingReveal(text: string, enabled: boolean) {
  const [shown, setShown] = useState(enabled ? '' : text)
  useEffect(() => {
    if (!enabled) { setShown(text); return }
    let i = 0
    setShown('')
    // Frame-based reveal so long messages don't hammer setState 1000x.
    const total = text.length
    const perChar = total > 400 ? 6 : total > 160 ? 10 : 14
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const target = Math.min(total, Math.floor((now - start) / perChar))
      if (target !== i) { i = target; setShown(text.slice(0, i)) }
      if (i < total) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [text, enabled])
  return shown
}

/* ── Thinking indicator: three soft dots ───────────────────────────── */
function ThinkingDots() {
  const dot = (delay: number): React.CSSProperties => ({
    width: 7, height: 7, borderRadius: '50%', background: 'var(--green)',
    animation: `dot-bounce 1.1s ${delay}s infinite ease-in-out`,
  })
  return (
    <div style={{ display: 'inline-flex', gap: 5, alignItems: 'center', padding: '4px 2px' }}>
      <span style={dot(0)} /><span style={dot(0.15)} /><span style={dot(0.3)} />
    </div>
  )
}

interface BubbleProps { m: Message; isLast: boolean }
function Bubble({ m, isLast }: BubbleProps) {
  const isUser = m.role === 'user'
  const reveal = useTypingReveal(m.text, !isUser && isLast && !m.instant)

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 4,
      alignSelf: isUser ? 'flex-end' : 'flex-start',
      maxWidth: '82%',
      animation: 'bubble-in 0.32s ease both',
    }}>
      {!isUser && (
        <div style={{ fontSize: '0.68rem', color: 'var(--muted)', padding: '0 14px', fontWeight: 600, letterSpacing: '0.04em' }}>
          FINN
        </div>
      )}
      <div style={{
        padding: '11px 15px',
        fontSize: '0.92rem', lineHeight: 1.55,
        borderRadius: 18,
        background: isUser
          ? 'linear-gradient(135deg, #00DC84 0%, #00B870 100%)'
          : 'linear-gradient(180deg, var(--glass-2), var(--glass-1))',
        color: isUser ? '#0A1A12' : 'var(--text)',
        fontWeight: isUser ? 500 : 400,
        border: isUser ? 'none' : '1px solid var(--glass-border)',
        backdropFilter: isUser ? 'none' : 'blur(14px)',
        WebkitBackdropFilter: isUser ? 'none' : 'blur(14px)',
        boxShadow: isUser
          ? '0 6px 24px rgba(0,220,132,0.28)'
          : '0 6px 22px rgba(0,0,0,0.35)',
        borderBottomRightRadius: isUser ? 6 : 18,
        borderBottomLeftRadius:  isUser ? 18 : 6,
        wordBreak: 'break-word',
      }}>
        {isUser ? m.text : <MarkdownMessage text={reveal || m.text /* fallback for empty reveal frame */} />}
      </div>
      <div style={{
        fontSize: '0.62rem', color: 'var(--muted)', padding: '0 14px',
        textAlign: isUser ? 'right' : 'left',
      }}>
        {m.timestamp}
      </div>
      {m.toolCalls?.map((tc, j) => (
        <details key={j} style={{
          background: 'var(--green-soft)', border: '1px solid rgba(0,220,132,0.18)',
          borderRadius: 10, padding: '8px 12px', fontSize: '0.74rem', marginTop: 2,
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
  )
}

interface Props {
  messages: Message[]
  loading: boolean
  onSend: (text: string) => void
  /** Externally injected text — e.g. transaction deep-link. Updates trigger prefill. */
  prefill?: { text: string; nonce: number } | null
  onPrefillConsumed?: () => void
}

export default function ChatPanel({ messages, loading, onSend, prefill, onPrefillConsumed }: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, loading])

  /* Deep-link: when prefill changes, populate input and focus. */
  useEffect(() => {
    if (!prefill) return
    setDraft(prefill.text)
    requestAnimationFrame(() => {
      const el = inputRef.current
      if (!el) return
      el.focus()
      el.setSelectionRange(prefill.text.length, prefill.text.length)
    })
    onPrefillConsumed?.()
  }, [prefill, onPrefillConsumed])

  /* Auto-grow textarea up to ~5 lines. */
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 130)}px`
  }, [draft])

  function handleSend() {
    const val = draft.trim()
    if (!val || loading) return
    onSend(val)
    setDraft('')
  }

  return (
    <div className="glass" style={{
      display: 'flex', flexDirection: 'column', padding: 18, height: '100%',
      borderRadius: 'var(--radius-lg)',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
        <div className="eyebrow">Conversation</div>
        <div style={{ fontSize: '0.66rem', color: 'var(--muted)' }}>
          {messages.length} {messages.length === 1 ? 'message' : 'messages'}
        </div>
      </div>

      <div style={{
        flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14,
        paddingRight: 4, paddingBottom: 4, scrollBehavior: 'smooth',
      }}>
        {messages.map((m, i) => (
          <Bubble key={m.id ?? i} m={m} isLast={i === messages.length - 1} />
        ))}

        {loading && (
          <div style={{ alignSelf: 'flex-start', maxWidth: '82%', animation: 'bubble-in 0.32s ease both' }}>
            <div style={{ fontSize: '0.68rem', color: 'var(--muted)', padding: '0 14px', fontWeight: 600, letterSpacing: '0.04em' }}>
              FINN
            </div>
            <div style={{
              padding: '12px 16px',
              borderRadius: 18, borderBottomLeftRadius: 6,
              background: 'linear-gradient(180deg, var(--glass-2), var(--glass-1))',
              border: '1px solid var(--glass-border)',
              backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)',
              boxShadow: '0 6px 22px rgba(0,0,0,0.35)',
            }}>
              <ThinkingDots />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div style={{
        marginTop: 14,
        display: 'flex', alignItems: 'flex-end', gap: 10,
        background: 'var(--glass-1)',
        border: '1px solid var(--glass-border)',
        borderRadius: 'var(--radius)',
        padding: 8,
        transition: 'border-color 0.18s, box-shadow 0.18s',
      }}>
        <textarea
          ref={inputRef}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          rows={1}
          placeholder="Ask Finn anything…"
          disabled={loading}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
          }}
          style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none',
            color: 'var(--text)', fontSize: '0.92rem', lineHeight: 1.45,
            padding: '8px 10px', resize: 'none', maxHeight: 130,
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !draft.trim()}
          aria-label="Send message"
          style={{
            background: draft.trim() ? 'linear-gradient(135deg, #00DC84, #00B870)' : 'rgba(255,255,255,0.06)',
            color: draft.trim() ? '#0A1A12' : 'var(--muted)',
            padding: '10px 14px',
            borderRadius: 12,
            fontSize: '0.85rem',
            opacity: (loading || !draft.trim()) ? 0.6 : 1,
            boxShadow: draft.trim() ? 'var(--shadow-green)' : 'none',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}
        >
          <span>Send</span>
          <span aria-hidden>↑</span>
        </button>
      </div>
    </div>
  )
}
