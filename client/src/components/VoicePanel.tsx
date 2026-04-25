import { useEffect, useRef, useState } from 'react'

/**
 * VoiceController — push-to-talk + barge-in.
 *
 * State machine (driven by parent via `aiState`):
 *   idle      → press-and-hold to record. Release sends to backend.
 *   listening → mic is live. Release to stop & transcribe.
 *   thinking  → backend is reasoning. Tap to abort.
 *   speaking  → TTS is playing. Tap to interrupt and re-open the mic
 *               (kills audio immediately, switches to listening).
 *
 * The barge-in path is the headline interaction: the user can speak
 * over Finn the moment they want to take the floor.
 */

export type AiState = 'idle' | 'listening' | 'thinking' | 'speaking'

interface Props {
  apiUrl: (path: string) => string
  aiState: AiState
  onTranscript: (text: string) => void
  onResponse: (text: string, audioB64?: string, audioMime?: string) => void
  onListeningChange: (v: boolean) => void
  onThinkingChange: (v: boolean) => void
  /** Kill any in-flight TTS audio (App owns the element) and reset state. */
  onInterrupt: () => void
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

/* ── Live waveform — Web Audio analyser ─────────────────────────────── */
function useMicLevels(stream: MediaStream | null, active: boolean, bars = 5) {
  const [levels, setLevels] = useState<number[]>(() => Array(bars).fill(0.2))
  useEffect(() => {
    if (!stream || !active) { setLevels(Array(bars).fill(0.2)); return }
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const src = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 64
    src.connect(analyser)
    const data = new Uint8Array(analyser.frequencyBinCount)
    let raf = 0
    const tick = () => {
      analyser.getByteFrequencyData(data)
      const slice = Math.floor(data.length / bars)
      const next: number[] = []
      for (let b = 0; b < bars; b++) {
        let sum = 0
        for (let k = 0; k < slice; k++) sum += data[b * slice + k]
        next.push(Math.min(1, (sum / slice) / 180 + 0.15))
      }
      setLevels(next)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(raf); src.disconnect(); ctx.close() }
  }, [stream, active, bars])
  return levels
}

export default function VoicePanel({
  apiUrl, aiState, onTranscript, onResponse, onListeningChange, onThinkingChange, onInterrupt,
}: Props) {
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [transcript, setTranscript] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const recording = aiState === 'listening'
  const levels = useMicLevels(stream, recording, 5)

  /* ── Recording lifecycle ─────────────────────────────────────────── */

  async function startRecording() {
    if (recorderRef.current) return
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const mime = preferredMime()
      const mr = mime ? new MediaRecorder(s, { mimeType: mime }) : new MediaRecorder(s)
      mr.ondataavailable = e => chunksRef.current.push(e.data)
      mr.start()
      recorderRef.current = mr
      setStream(s)
      setError(null)
      onListeningChange(true)
    } catch {
      setError('Microphone access denied')
    }
  }

  async function stopRecording() {
    const mr = recorderRef.current
    if (!mr || mr.state === 'inactive') return
    mr.stop()
    onListeningChange(false)
    onThinkingChange(true)

    mr.onstop = async () => {
      const mime = mr.mimeType || preferredMime()
      const blob = new Blob(chunksRef.current, { type: mime })
      mr.stream.getTracks().forEach(t => t.stop())
      recorderRef.current = null
      setStream(null)

      const fd = new FormData()
      fd.append('audio', blob, `recording.${ext(mime)}`)
      const ac = new AbortController()
      abortRef.current = ac
      try {
        const r = await fetch(apiUrl('/voice'), { method: 'POST', body: fd, signal: ac.signal })
        const data = await r.json().catch(async () => ({ error: await r.text() }))
        if (!r.ok) throw new Error(data.error ?? 'Voice processing failed')
        setTranscript(data.transcript ?? '')
        onTranscript(data.transcript ?? '')
        onResponse(data.response ?? '', data.audio_b64, data.audio_mime)
      } catch (e: unknown) {
        if ((e as Error).name === 'AbortError') return // user cancelled
        setError('Voice processing failed: ' + (e instanceof Error ? e.message : String(e)))
      } finally {
        abortRef.current = null
        onThinkingChange(false)
      }
    }
  }

  /* ── Single tap target — behaviour depends on aiState. ───────────── */

  function handlePointerDown(e: React.PointerEvent) {
    e.preventDefault()
    if (aiState === 'speaking') {
      // Barge-in: kill TTS instantly, then open the mic.
      onInterrupt()
      void startRecording()
      return
    }
    if (aiState === 'thinking') {
      // Cancel in-flight request.
      abortRef.current?.abort()
      onThinkingChange(false)
      return
    }
    if (aiState === 'idle') {
      void startRecording()
    }
  }

  function handlePointerUp() {
    // Only the press-to-talk gesture releases. Barge-in uses a tap; the user
    // has to tap-and-hold a fresh second press to actually record over Finn —
    // but most users instinctively hold from the first contact, so we honour
    // either: if they're already listening, release stops and submits.
    if (recording) void stopRecording()
  }

  // Cleanup on unmount.
  useEffect(() => () => {
    recorderRef.current?.stream.getTracks().forEach(t => t.stop())
    abortRef.current?.abort()
  }, [])

  /* ── Render ──────────────────────────────────────────────────────── */

  const label = (() => {
    switch (aiState) {
      case 'listening': return 'Listening… release to send'
      case 'thinking':  return 'Finn is thinking… tap to cancel'
      case 'speaking':  return 'Finn is speaking — tap to interrupt'
      default:          return 'Hold to talk to Finn'
    }
  })()

  const ring = aiState === 'listening' ? 'rgba(255,77,109,0.55)'
    : aiState === 'speaking' ? 'rgba(0,220,132,0.55)'
    : 'transparent'

  return (
    <div className="glass" style={{ padding: 18, borderRadius: 'var(--radius)' }}>
      <div className="eyebrow" style={{ marginBottom: 14 }}>Voice</div>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <button
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerLeave={() => { if (recording) void stopRecording() }}
          aria-label={label}
          style={{
            position: 'relative',
            width: 76, height: 76, borderRadius: '50%',
            background: aiState === 'speaking'
              ? 'linear-gradient(135deg, #FF4D6D 0%, #C9304B 100%)'
              : aiState === 'listening'
              ? 'linear-gradient(135deg, #FF4D6D 0%, #C9304B 100%)'
              : aiState === 'thinking'
              ? 'linear-gradient(135deg, #FFD60A 0%, #E0B400 100%)'
              : 'linear-gradient(135deg, #00DC84 0%, #00B870 100%)',
            color: '#0A1A12',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 12px 30px ${ring}, var(--shadow-soft)`,
            animation: aiState === 'listening'
              ? 'ring-pulse 1.4s infinite'
              : aiState === 'speaking'
              ? 'ring-pulse-green 1.4s infinite'
              : 'none',
            transition: 'background 0.25s ease',
            touchAction: 'none',
          }}
        >
          {aiState === 'speaking' ? (
            // Stop square — universally read as "interrupt"
            <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
              <rect x="5" y="5" width="12" height="12" rx="2.5" fill="currentColor" />
            </svg>
          ) : aiState === 'thinking' ? (
            <div style={{
              width: 26, height: 26, borderRadius: '50%',
              border: '3px solid rgba(0,0,0,0.25)', borderTopColor: '#0A1A12',
              animation: 'thinking-orbit 0.9s linear infinite',
            }} />
          ) : aiState === 'listening' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 22 }}>
              {levels.map((l, i) => (
                <span key={i} style={{
                  width: 3, borderRadius: 2, background: '#0A1A12',
                  height: `${Math.max(4, l * 22)}px`,
                  transition: 'height 60ms linear',
                }} />
              ))}
            </div>
          ) : (
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z" fill="currentColor" />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          )}
        </button>

        <div style={{ textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-2)', minHeight: 18, fontWeight: 500 }}>
          {label}
        </div>
      </div>

      {(transcript || error) && (
        <div style={{
          marginTop: 12, padding: 10,
          background: error ? 'rgba(255,77,109,0.08)' : 'var(--green-soft)',
          border: `1px solid ${error ? 'rgba(255,77,109,0.25)' : 'rgba(0,220,132,0.18)'}`,
          borderRadius: 10, fontSize: '0.74rem', color: 'var(--text-2)', fontStyle: 'italic',
        }}>
          {error ?? `“${transcript}”`}
        </div>
      )}
    </div>
  )
}
