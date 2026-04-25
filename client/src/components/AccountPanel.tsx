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
}

export default function AccountPanel({ balance, accountName, transactions }: Props) {
  return (
    <div style={{ background: 'var(--card)', borderRadius: 'var(--radius)', padding: 16 }}>
      <h3 style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 10 }}>
        Account
      </h3>
      <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginBottom: 4 }}>Current balance</div>
      <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--green)' }}>
        {balance !== null ? `€${balance.toFixed(2)}` : '€—'}
      </div>
      <div style={{ fontSize: '0.8rem', color: 'var(--text)', marginTop: 4 }}>{accountName || '—'}</div>

      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {transactions.map(t => {
          const pos = t.amount_eur >= 0
          return (
            <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', flexShrink: 0 }}>
                {categoryIcon(t.category)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.merchant}</div>
                <div style={{ fontSize: '0.65rem', color: 'var(--muted)' }}>{t.date}</div>
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, flexShrink: 0, color: pos ? 'var(--green)' : 'var(--red)' }}>
                {pos ? '+' : ''}€{Math.abs(t.amount_eur).toFixed(2)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
