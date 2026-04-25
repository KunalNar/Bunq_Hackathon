import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import './index.css'
import ConversationView from './components/ConversationView'
import AccountPanel from './components/AccountPanel'
import ReceiptPanel from './components/ReceiptPanel'

interface AccountState {
  balance_eur: number
  account_name: string
}
interface Transaction {
  id: string; date: string; merchant: string; amount_eur: number; category: string
}

const urlMock = new URLSearchParams(window.location.search).get('mock')
let globalMock: boolean | null = urlMock === null ? null : ['true', '1', 'yes'].includes(urlMock.toLowerCase())

function apiUrl(path: string) {
  return globalMock === null ? path : `${path}?mock=${globalMock}`
}

export default function App() {
  const [account, setAccount] = useState<AccountState | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isMock, setIsMock] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [injected, setInjected] = useState<{ nonce: number; role: 'user' | 'assistant'; text: string } | null>(null)

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

  /* ── Top-right slot: balance pill + mock/live + drawer toggle ───── */

  const topRight = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        fontSize: '0.62rem', fontWeight: 700, padding: '4px 10px',
        borderRadius: 'var(--radius-pill)', textTransform: 'uppercase',
        letterSpacing: '0.08em',
        background: isMock ? 'rgba(255,214,10,0.10)' : 'rgba(0,220,132,0.12)',
        color: isMock ? 'var(--yellow)' : 'var(--green)',
        border: `1px solid ${isMock ? 'rgba(255,214,10,0.28)' : 'rgba(0,220,132,0.30)'}`,
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%', background: 'currentColor',
          animation: isMock ? 'pulse 1.5s infinite' : 'none',
        }} />
        {isMock ? 'Mock' : 'Live'}
      </div>

      {account && (
        <div className="glass" style={{
          padding: '6px 14px', borderRadius: 'var(--radius-pill)',
          display: 'flex', alignItems: 'baseline', gap: 8,
          fontSize: '0.78rem',
        }}>
          <span style={{ color: 'var(--muted)' }}>Balance</span>
          <span style={{
            fontWeight: 700, fontSize: '0.95rem',
            background: 'linear-gradient(135deg, #00DC84, #6FFFC0)',
            WebkitBackgroundClip: 'text', backgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            €{account.balance_eur.toFixed(2)}
          </span>
        </div>
      )}

      <button
        onClick={(e) => { e.stopPropagation(); setDrawerOpen(o => !o) }}
        onPointerDown={(e) => e.stopPropagation()}
        aria-label="Open account drawer"
        className="glass"
        style={{
          width: 38, height: 38, borderRadius: 12,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text)',
        }}
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
          <path d="M3 5h12M3 9h12M3 13h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  )

  return (
    <>
      <ConversationView
        apiUrl={apiUrl}
        topRightSlot={topRight}
        injected={injected}
      />

      {/* ── Slide-in drawer (Framer Motion) ─────────────────────── */}
      <AnimatePresence>
        {drawerOpen && (
          <>
            <motion.div
              key="scrim"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              onClick={() => setDrawerOpen(false)}
              style={{
                position: 'fixed', inset: 0, zIndex: 90,
                background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(2px)',
              }}
            />
            <motion.aside
              key="drawer"
              initial={{ x: 420, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 420, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 260, damping: 28 }}
              onPointerDown={e => e.stopPropagation()}
              style={{
                position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(420px, 96vw)',
                zIndex: 91,
                padding: 18, paddingTop: 70,
                display: 'flex', flexDirection: 'column', gap: 14,
                background: 'linear-gradient(180deg, rgba(22,22,40,0.95), rgba(15,15,26,0.95))',
                borderLeft: '1px solid var(--glass-border)',
                backdropFilter: 'blur(22px) saturate(140%)',
                WebkitBackdropFilter: 'blur(22px) saturate(140%)',
                boxShadow: '-30px 0 80px rgba(0,0,0,0.55)',
                overflowY: 'auto',
              }}
            >
              <button
                onClick={() => setDrawerOpen(false)}
                style={{
                  position: 'absolute', top: 14, right: 14,
                  width: 32, height: 32, borderRadius: 10,
                  background: 'var(--glass-2)', border: '1px solid var(--glass-border)',
                  color: 'var(--text)',
                }}
                aria-label="Close drawer"
              >✕</button>

              <AccountPanel
                balance={account?.balance_eur ?? null}
                accountName={account?.account_name ?? ''}
                transactions={transactions}
                onTransactionClick={(t) => {
                  const verb = t.amount_eur >= 0 ? 'income' : 'payment'
                  setInjected({
                    nonce: Date.now(),
                    role: 'user',
                    text: `Tell me more about this ${t.merchant} ${verb} (€${Math.abs(t.amount_eur).toFixed(2)} on ${t.date}).`,
                  })
                  setDrawerOpen(false)
                }}
              />

              <ReceiptPanel
                apiUrl={apiUrl}
                onAgentResponse={(text) => {
                  setInjected({ nonce: Date.now(), role: 'assistant', text })
                  refreshState()
                }}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
