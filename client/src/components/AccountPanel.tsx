import { categoryIcon } from './ChatPanel'

interface Transaction {
  id: string
  date: string
  merchant: string
  amount_eur: number
  category: string
}

interface Props {
  balance: number | null
  accountName: string
  transactions: Transaction[]
  onTransactionClick?: (t: Transaction) => void
}

export default function AccountPanel({ balance, accountName, transactions, onTransactionClick }: Props) {
  return (
    <div className="glass" style={{ padding: 18, borderRadius: 'var(--radius)' }}>
      <div className="eyebrow" style={{ marginBottom: 12 }}>Account</div>

      <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginBottom: 4, fontWeight: 500 }}>
        Current balance
      </div>
      <div style={{
        font: 'var(--display)',
        background: 'linear-gradient(135deg, #00DC84 0%, #6FFFC0 100%)',
        WebkitBackgroundClip: 'text', backgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        letterSpacing: '-0.02em',
      }}>
        {balance !== null ? `€${balance.toFixed(2)}` : '€—'}
      </div>
      <div style={{ fontSize: '0.78rem', color: 'var(--text-2)', marginTop: 2 }}>{accountName || '—'}</div>

      <div style={{
        marginTop: 16, display: 'flex', flexDirection: 'column', gap: 2,
        borderTop: '1px solid var(--glass-border)', paddingTop: 12,
      }}>
        <div className="eyebrow" style={{ marginBottom: 8, fontSize: '0.6rem' }}>Recent activity</div>
        {transactions.map(t => {
          const pos = t.amount_eur >= 0
          const clickable = !!onTransactionClick
          return (
            <button
              key={t.id}
              onClick={clickable ? () => onTransactionClick(t) : undefined}
              disabled={!clickable}
              title={clickable ? `Ask Finn about ${t.merchant}` : undefined}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px',
                margin: '0 -10px',
                borderRadius: 10,
                background: 'transparent',
                cursor: clickable ? 'pointer' : 'default',
                textAlign: 'left',
                color: 'var(--text)',
              }}
              onMouseEnter={e => { if (clickable) (e.currentTarget as HTMLElement).style.background = 'var(--glass-2)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
            >
              <div style={{
                width: 32, height: 32, borderRadius: 10,
                background: 'var(--glass-2)',
                border: '1px solid var(--glass-border)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.85rem', flexShrink: 0,
              }}>
                {categoryIcon(t.category)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: '0.85rem', fontWeight: 600,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {t.merchant}
                </div>
                <div style={{ fontSize: '0.66rem', color: 'var(--muted)' }}>{t.date}</div>
              </div>
              <div style={{
                fontSize: '0.88rem', fontWeight: 700, flexShrink: 0,
                color: pos ? 'var(--green)' : 'var(--text)',
              }}>
                {pos ? '+' : '−'}€{Math.abs(t.amount_eur).toFixed(2)}
              </div>
            </button>
          )
        })}
        {transactions.length === 0 && (
          <div style={{ fontSize: '0.78rem', color: 'var(--muted)', padding: '8px 0', fontStyle: 'italic' }}>
            No transactions yet
          </div>
        )}
      </div>
    </div>
  )
}
