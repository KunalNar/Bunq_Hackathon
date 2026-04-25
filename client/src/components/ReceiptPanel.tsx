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
    <div className="glass" style={{ padding: 18, borderRadius: 'var(--radius)' }}>
      <div className="eyebrow" style={{ marginBottom: 12 }}>Receipt Scanner</div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onFileChange} />
        <button
          onClick={() => fileRef.current?.click()}
          style={{
            background: 'var(--glass-2)', color: 'var(--text)',
            padding: '9px 14px', fontSize: '0.82rem',
            border: '1px solid var(--glass-border)',
          }}
        >
          📷 Upload
        </button>
        <button
          onClick={process}
          disabled={!preview || processing}
          style={{
            background: (!preview || processing) ? 'rgba(255,255,255,0.06)' : 'linear-gradient(135deg, #00DC84, #00B870)',
            color: (!preview || processing) ? 'var(--muted)' : '#0A1A12',
            padding: '9px 14px', fontSize: '0.82rem',
            opacity: (!preview || processing) ? 0.6 : 1,
            boxShadow: (!preview || processing) ? 'none' : 'var(--shadow-green)',
          }}
        >
          {processing ? 'Parsing…' : 'Process'}
        </button>
      </div>
      {preview && (
        <img
          src={preview}
          alt="Receipt preview"
          style={{
            marginTop: 10, maxHeight: 110, borderRadius: 10, objectFit: 'cover',
            width: '100%', border: '1px solid var(--glass-border)',
          }}
        />
      )}
      <div style={{ marginTop: 10, fontSize: '0.74rem', color: 'var(--muted)', minHeight: 18 }}>{result}</div>
    </div>
  )
}
