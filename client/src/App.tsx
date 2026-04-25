import { useCallback, useEffect, useState } from 'react'
import './index.css'
import Avatar from './components/Avatar'
import ChatPanel, { type Message } from './components/ChatPanel'
import AccountPanel from './components/AccountPanel'
import VoicePanel from './components/VoicePanel'
import ReceiptPanel from './components/ReceiptPanel'

interface AccountState {
  balance_eur: number
  account_name: string
}

interface Transaction {
  id: string; date: string; merchant: string; amount_eur: number; category: string
}

function nowStr() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const urlMock = new URLSearchParams(window.location.search).get('mock')
let globalMock: boolean | null = urlMock === null ? null : ['true', '1', 'yes'].includes(urlMock.toLowerCase())

function apiUrl(path: string) {
  return globalMock === null ? path : `${path}?mock=${globalMock}`
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([{
    role: 'assistant',
    text: "Hey! I'm Finn, your bunq AI assistant. Ask me about your balance, spending, or snap a receipt to split a bill. 🏦",
    timestamp: nowStr(),
  }])
  const [loading, setLoading] = useState(false)
  const [isMock, setIsMock] = useState(true)
  const [account, setAccount] = useState<AccountState | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [speaking, setSpeaking] = useState(false)
  const [listening, setListening] = useState(false)

  const addMessage = useCallback((role: 'user' | 'assistant', text: string, toolCalls?: Message['toolCalls']) => {
    setMessages(prev => [...prev, { role, text, timestamp: nowStr(), toolCalls }])
  }, [])

  const refreshState = useCallback(async () => {
    try {
      const r = await fetch(apiUrl('/state'))
      const data = await r.json()
      globalMock = data.mock_mode
      setIsMock(data.mock_mode)
      setAccount(data.account)
      setTransactions(data.recent_transactions ?? [])
    } catch { /* silent */ }
  }, [])

  useEffect(() => { refreshState() }, [refreshState])
  useEffect(() => {
    const id = setInterval(refreshState, 5000)
    return () => clearInterval(id)
  }, [refreshState])

  async function sendMessage(text: string) {
    addMessage('user', text)
    setLoading(true)
    try {
      const r = await fetch(apiUrl('/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await r.json()
      addMessage('assistant', data.response ?? '(no response)', data.tool_calls ?? [])
      await refreshState()
    } catch {
      addMessage('assistant', '⚠️ Connection error. Is the server running?')
    }
    setLoading(false)
  }

  function playAudio(b64: string, mime = 'audio/mpeg') {
    setSpeaking(true)
    const audio = new Audio(`data:${mime};base64,${b64}`)
    audio.onended = () => setSpeaking(false)
    audio.onerror = () => setSpeaking(false)
    audio.play().catch(() => setSpeaking(false))
  }

  function handleVoiceResponse(text: string, audioB64?: string, audioMime?: string) {
    addMessage('assistant', text)
    if (audioB64) playAudio(audioB64, audioMime)
    refreshState()
  }

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateColumns: '1fr 380px', gridTemplateRows: 'auto 1fr', gap: 12, padding: 12, overflow: 'hidden' }}>

      {/* Header */}
      <header style={{ gridColumn: '1/-1', display: 'flex', alignItems: 'center', gap: 12, padding: '8px 4px' }}>
        <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--green)' }}>
          Finn <span style={{ color: 'var(--text)', fontWeight: 300 }}>by bunq</span>
        </div>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: '0.65rem', fontWeight: 700, padding: '3px 8px',
          borderRadius: 20, textTransform: 'uppercase',
          background: isMock ? 'rgba(255,214,10,0.15)' : 'rgba(0,220,132,0.15)',
          color: isMock ? 'var(--yellow)' : 'var(--green)',
          border: `1px solid ${isMock ? 'rgba(255,214,10,0.3)' : 'rgba(0,220,132,0.3)'}`,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor', animation: isMock ? 'pulse 1.5s infinite' : 'none' }} />
          {isMock ? 'MOCK' : 'LIVE'}
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>bunq Hackathon 7.0</div>
      </header>

      {/* Left: Chat */}
      <div style={{ minHeight: 0, overflow: 'hidden' }}>
        <ChatPanel messages={messages} loading={loading} onSend={sendMessage} />
      </div>

      {/* Right column — scrolls as a whole so the stacked panels are always reachable */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 12,
        minHeight: 0, overflowY: 'auto', paddingRight: 4,
      }}>

        {/* Avatar card */}
        <div style={{ background: 'var(--card)', borderRadius: 'var(--radius)', padding: 20, display: 'flex', justifyContent: 'center' }}>
          <Avatar speaking={speaking} listening={listening} />
        </div>

        <AccountPanel
          balance={account?.balance_eur ?? null}
          accountName={account?.account_name ?? ''}
          transactions={transactions}
        />

        <VoicePanel
          apiUrl={apiUrl}
          onTranscript={text => addMessage('user', text)}
          onResponse={handleVoiceResponse}
          onListeningChange={setListening}
        />

        <ReceiptPanel
          apiUrl={apiUrl}
          onAgentResponse={text => addMessage('assistant', text)}
        />
      </div>

      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>
    </div>
  )
}
