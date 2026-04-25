import { useRef, useState } from 'react'

interface Props {
  apiUrl: (path: string) => string
  onAgentResponse: (text: string) => void
}

export default function ReceiptPanel({ apiUrl, onAgentResponse }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [result, setResult] = useState('Upload a receipt to parse it…')
  const [processing, setProcessing] = useState(false)

  function onFileChange() {
    const file = fileRef.current?.files?.[0]
    if (!file) return
    setPreview(URL.createObjectURL(file))
    setResult('Ready to process…')
  }

  async function process() {
    const file = fileRef.current?.files?.[0]
    if (!file) return
    setProcessing(true)
    setResult('🔍 Parsing receipt…')
    const fd = new FormData()
    fd.append('image', file)
    fd.append('num_people', '1')
    fd.append('run_agent_flag', 'true')
    try {
      const r = await fetch(apiUrl('/receipt'), { method: 'POST', body: fd })
      const data = await r.json()
      const rec = data.parsed_receipt
      setResult(`${rec.merchant ?? 'Unknown'} — €${rec.total ?? '?'} · ${rec.date ?? 'no date'}`)
      if (data.agent_response) onAgentResponse(data.agent_response)
    } catch (e: unknown) {
      setResult('⚠️ Receipt processing failed: ' + (e instanceof Error ? e.message : String(e)))
    }
    setProcessing(false)
  }

  return (
    <div style={{ background: 'var(--card)', borderRadius: 'var(--radius)', padding: 16 }}>
      <h3 style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 10 }}>
        Receipt Scanner
      </h3>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onFileChange} />
        <button onClick={() => fileRef.current?.click()} style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text)', padding: '8px 14px', fontSize: '0.8rem' }}>
          📷 Upload Receipt
        </button>
        <button onClick={process} disabled={!preview || processing} style={{ background: 'var(--green)', color: 'var(--dark)', padding: '8px 14px', fontSize: '0.8rem', opacity: (!preview || processing) ? 0.3 : 1 }}>
          Process
        </button>
      </div>
      {preview && <img src={preview} alt="Receipt preview" style={{ marginTop: 8, maxHeight: 100, borderRadius: 6, objectFit: 'cover', width: '100%' }} />}
      <div style={{ marginTop: 8, fontSize: '0.72rem', color: 'var(--muted)', minHeight: 20 }}>{result}</div>
    </div>
  )
}
