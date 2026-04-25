import { useRef, useState } from 'react'

interface Props {
  apiUrl: (path: string) => string
  onTranscript: (text: string) => void
  onResponse: (text: string, audioB64?: string, audioMime?: string) => void
  onListeningChange: (v: boolean) => void
}

function preferredMime() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
  return candidates.find(t => window.MediaRecorder?.isTypeSupported?.(t)) ?? ''
}

function ext(mime: string) {
  if (mime.includes('mp4')) return 'm4a'
  if (mime.includes('ogg')) return 'ogg'
  return 'webm'
}

export default function VoicePanel({ apiUrl, onTranscript, onResponse, onListeningChange }: Props) {
  const [recording, setRecording] = useState(false)
  const [status, setStatus] = useState('Hold mic to speak')
  const [transcript, setTranscript] = useState('Transcript will appear here…')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  async function startRecording() {
    if (recorderRef.current) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const mime = preferredMime()
      const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
      mr.ondataavailable = e => chunksRef.current.push(e.data)
      mr.start()
      recorderRef.current = mr
      setRecording(true)
      onListeningChange(true)
      setStatus('🔴 Recording… release to send')
    } catch {
      setStatus('⚠️ Microphone access denied')
    }
  }

  async function stopRecording() {
    const mr = recorderRef.current
    if (!mr || mr.state === 'inactive') return
    mr.stop()
    setRecording(false)
    onListeningChange(false)
    setStatus('Processing…')

    mr.onstop = async () => {
      const mime = mr.mimeType || preferredMime()
      const blob = new Blob(chunksRef.current, { type: mime })
      mr.stream.getTracks().forEach(t => t.stop())
      recorderRef.current = null

      const fd = new FormData()
      fd.append('audio', blob, `recording.${ext(mime)}`)
      try {
        const r = await fetch(apiUrl('/voice'), { method: 'POST', body: fd })
        const data = await r.json().catch(async () => ({ error: await r.text() }))
        if (!r.ok) throw new Error(data.error ?? 'Voice processing failed')
        setTranscript(data.transcript ?? '(no transcript)')
        onTranscript(data.transcript ?? '')
        onResponse(data.response ?? '', data.audio_b64, data.audio_mime)
        setStatus('Done. Hold mic to speak again.')
      } catch (e: unknown) {
        setStatus('⚠️ Voice processing failed')
        setTranscript('Error: ' + (e instanceof Error ? e.message : String(e)))
      }
    }
  }

  return (
    <div style={{ background: 'var(--card)', borderRadius: 'var(--radius)', padding: 16 }}>
      <h3 style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 10 }}>
        Voice
      </h3>
      <button
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={stopRecording}
        onTouchStart={e => { e.preventDefault(); startRecording() }}
        onTouchEnd={stopRecording}
        style={{
          width: 64, height: 64, borderRadius: '50%',
          background: recording ? 'var(--red)' : 'var(--card)',
          border: `2px solid ${recording ? 'var(--red)' : 'rgba(255,255,255,0.1)'}`,
          color: 'var(--text)', fontSize: '1.4rem',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 10px',
          animation: recording ? 'pulseMic 0.8s infinite' : 'none',
        }}
      >
        🎙️
      </button>
      <div style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--muted)', minHeight: 18 }}>{status}</div>
      <div style={{ marginTop: 8, background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: 8, fontSize: '0.75rem', color: 'var(--muted)', minHeight: 36, fontStyle: 'italic' }}>
        {transcript}
      </div>
      <style>{`@keyframes pulseMic { 0%,100%{transform:scale(1)} 50%{transform:scale(1.08)} }`}</style>
    </div>
  )
}
