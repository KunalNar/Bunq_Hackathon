import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import Avatar from './Avatar'

/* ─────────────────────────────────────────────────────────────────────
   ConversationView — Voice-Hero layout for Finn by bunq.

   Architecture:
     - One state machine: idle | listening | thinking | speaking
     - Centered Avatar wrapped in a radial WaveformRing driven by a
       Web Audio analyser (mic stream while listening, TTS element
       while speaking).
     - Live subtitle stack at the bottom third — newest at the bottom,
       each subtitle self-destructs ~5s after it lands.
     - Single hero "Pulse" button drives the entire turn.
     - The middle of the screen is a tap target: while speaking, a tap
       kills TTS, fires a haptic-style white flash, and re-opens the mic.
   ───────────────────────────────────────────────────────────────────── */

export type AiState = 'idle' | 'listening' | 'thinking' | 'speaking'

export interface Subtitle {
  id: number
  role: 'user' | 'assistant'
  text: string
}

interface Props {
  apiUrl: (path: string) => string
  /** Optional callback if the parent wants to mirror utterances elsewhere. */
  onUtterance?: (s: Subtitle) => void
  /** Optional slot rendered in the top-right corner — e.g. balance pill / drawer toggle. */
  topRightSlot?: React.ReactNode
  /** Inject a subtitle from outside (e.g. receipt-scan agent response). Nonce gates the push. */
  injected?: { nonce: number; role: 'user' | 'assistant'; text: string } | null
}

const SUBTITLE_TTL_MS = 5000

/* ── Audio plumbing ─────────────────────────────────────────────────── */

function pickRecordingMime() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
  return candidates.find(t => window.MediaRecorder?.isTypeSupported?.(t)) ?? ''
}
function recordingExt(mime: string) {
  if (mime.includes('mp4')) return 'm4a'
  if (mime.includes('ogg')) return 'ogg'
  return 'webm'
}

/**
 * Single shared analyser. Whichever source is active (mic or audio
 * element) connects into it; the same RAF samples the bins so the
 * WaveformRing has one continuous data stream, not two competing ones.
 */
function useAnalyser() {
  const ctxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const sourceRef = useRef<AudioNode | null>(null)
  const [bins, setBins] = useState<Float32Array>(() => new Float32Array(48))
  const rafRef = useRef<number>(0)

  const ensureCtx = () => {
    if (!ctxRef.current) {
      ctxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
      const a = ctxRef.current.createAnalyser()
      a.fftSize = 128
      a.smoothingTimeConstant = 0.78
      analyserRef.current = a
    }
    return { ctx: ctxRef.current!, analyser: analyserRef.current! }
  }

  const startSampling = () => {
    if (rafRef.current) return
    const buf = new Uint8Array(analyserRef.current!.frequencyBinCount)
    const tick = () => {
      analyserRef.current!.getByteFrequencyData(buf)
      // Compress 64 bins → 48 bars (matches WaveformRing).
      const out = new Float32Array(48)
      const slice = buf.length / 48
      for (let i = 0; i < 48; i++) {
        let sum = 0
        const start = Math.floor(i * slice), end = Math.floor((i + 1) * slice)
        for (let k = start; k < end; k++) sum += buf[k]
        out[i] = Math.min(1, (sum / (end - start)) / 200)
      }
      setBins(out)
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
  }
  const stopSampling = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = 0
    setBins(new Float32Array(48))
  }

  const connectStream = (stream: MediaStream) => {
    const { ctx, analyser } = ensureCtx()
    if (sourceRef.current) try { sourceRef.current.disconnect() } catch {}
    const src = ctx.createMediaStreamSource(stream)
    src.connect(analyser)
    sourceRef.current = src
    startSampling()
  }
  const connectAudio = (audio: HTMLAudioElement) => {
    const { ctx, analyser } = ensureCtx()
    if (sourceRef.current) try { sourceRef.current.disconnect() } catch {}
    const src = ctx.createMediaElementSource(audio)
    src.connect(analyser)
    src.connect(ctx.destination) // keep audible
    sourceRef.current = src
    if (ctx.state === 'suspended') void ctx.resume()
    startSampling()
  }
  const disconnect = () => {
    if (sourceRef.current) try { sourceRef.current.disconnect() } catch {}
    sourceRef.current = null
    stopSampling()
  }

  useEffect(() => () => {
    disconnect()
    if (ctxRef.current) try { ctxRef.current.close() } catch {}
  }, [])

  return { bins, connectStream, connectAudio, disconnect }
}

/* ── Radial waveform — 48 bars in a ring around the avatar ─────────── */

interface RingProps {
  bins: Float32Array
  state: AiState
  size: number
}
function WaveformRing({ bins, state, size }: RingProps) {
  const N = 48
  const cx = size / 2
  const cy = size / 2
  const innerR = size * 0.34
  const baseLen = size * 0.025
  const dynLen  = size * 0.18

  // Idle gets a slow sine wave so the ring is never frozen.
  const tRef = useRef(0)
  const [, force] = useState(0)
  useEffect(() => {
    if (state !== 'idle' && state !== 'thinking') return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      tRef.current += (now - last) / 1000
      last = now
      force(x => (x + 1) % 1024)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [state])

  const color =
    state === 'listening' ? 'rgba(255,77,109,0.95)'
    : state === 'speaking'  ? 'rgba(0,220,132,0.95)'
    : state === 'thinking'  ? 'rgba(255,214,10,0.85)'
    : 'rgba(0,220,132,0.55)'

  const bars = useMemo(() => {
    const t = tRef.current
    return Array.from({ length: N }, (_, i) => {
      const angle = (i / N) * Math.PI * 2 - Math.PI / 2
      const live  = bins[i] ?? 0
      const idleWave = (state === 'idle' || state === 'thinking')
        ? 0.18 + 0.16 * Math.sin(t * 1.6 + i * 0.42) + 0.08 * Math.sin(t * 3.1 + i * 0.21)
        : 0
      const amp = Math.max(live, idleWave)
      const len = baseLen + amp * dynLen
      const x1 = cx + Math.cos(angle) * innerR
      const y1 = cy + Math.sin(angle) * innerR
      const x2 = cx + Math.cos(angle) * (innerR + len)
      const y2 = cy + Math.sin(angle) * (innerR + len)
      const opacity = 0.35 + amp * 0.65
      return (
        <line
          key={i}
          x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={color} strokeLinecap="round" strokeWidth={3}
          opacity={opacity}
        />
      )
    })
  }, [bins, state, color, cx, cy, innerR, baseLen, dynLen])

  return (
    <svg
      width={size} height={size} viewBox={`0 0 ${size} ${size}`}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      aria-hidden
    >
      {/* Soft halo ring under the bars */}
      <circle
        cx={cx} cy={cy} r={innerR - 6}
        fill="none" stroke={color} strokeWidth={1.5} opacity={0.18}
      />
      {bars}
    </svg>
  )
}

/* ── The big "Pulse" button ────────────────────────────────────────── */

interface PulseProps {
  state: AiState
  onPointerDown: (e: React.PointerEvent) => void
  onPointerUp:   (e: React.PointerEvent) => void
}
function PulseButton({ state, onPointerDown, onPointerUp }: PulseProps) {
  const label =
    state === 'listening' ? 'Listening — release to send'
    : state === 'thinking' ? 'Thinking…'
    : state === 'speaking' ? 'Tap anywhere to interrupt'
    : 'Hold to talk'

  const bg =
    state === 'listening' ? 'linear-gradient(135deg, #FF4D6D 0%, #C9304B 100%)'
    : state === 'speaking'  ? 'linear-gradient(135deg, #00DC84 0%, #00B870 100%)'
    : state === 'thinking'  ? 'linear-gradient(135deg, #FFD60A 0%, #E0B400 100%)'
    : 'linear-gradient(135deg, #00DC84 0%, #00B870 100%)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <motion.button
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        aria-label={label}
        layout
        whileTap={{ scale: 0.94 }}
        animate={{ scale: state === 'listening' ? 1.06 : 1 }}
        transition={{ type: 'spring', stiffness: 320, damping: 22 }}
        style={{
          width: 96, height: 96, borderRadius: '50%',
          background: bg, color: '#0A1A12',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          touchAction: 'none',
          animation: state === 'idle'
            ? 'button-breathe 2.6s ease-in-out infinite'
            : state === 'listening'
            ? 'ring-pulse 1.2s infinite'
            : state === 'speaking'
            ? 'ring-pulse-green 1.2s infinite'
            : 'none',
          border: '1px solid rgba(255,255,255,0.18)',
        }}
      >
        {state === 'thinking' ? (
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            border: '3px solid rgba(0,0,0,0.25)', borderTopColor: '#0A1A12',
            animation: 'thinking-orbit 0.9s linear infinite',
          }} />
        ) : state === 'speaking' ? (
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden>
            <rect x="7" y="7" width="14" height="14" rx="2.5" fill="currentColor" />
          </svg>
        ) : state === 'listening' ? (
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden>
            <rect x="6" y="6" width="12" height="12" rx="3" fill="currentColor" />
          </svg>
        ) : (
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z" fill="currentColor" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        )}
      </motion.button>

      <AnimatePresence mode="wait">
        <motion.div
          key={state}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18 }}
          style={{
            fontSize: '0.82rem', color: 'var(--text-2)',
            fontWeight: 500, letterSpacing: '0.01em',
          }}
        >
          {label}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

/* ── Main component ─────────────────────────────────────────────────── */

export default function ConversationView({ apiUrl, onUtterance, topRightSlot, injected }: Props) {
  const [aiState, setAiState] = useState<AiState>('idle')
  const [subtitles, setSubtitles] = useState<Subtitle[]>([])
  const [flashKey, setFlashKey] = useState(0)
  const idCounterRef = useRef(0)

  const audioRef     = useRef<HTMLAudioElement | null>(null)
  const recorderRef  = useRef<MediaRecorder | null>(null)
  const chunksRef    = useRef<Blob[]>([])
  const abortRef     = useRef<AbortController | null>(null)

  const { bins, connectStream, connectAudio, disconnect } = useAnalyser()

  /* ── Subtitle lifecycle: 5s TTL, animated exit via AnimatePresence ── */

  const pushSubtitle = useCallback((role: Subtitle['role'], text: string) => {
    if (!text?.trim()) return
    const id = ++idCounterRef.current
    const sub: Subtitle = { id, role, text }
    setSubtitles(prev => [...prev.slice(-3), sub]) // keep at most 4
    onUtterance?.(sub)
    window.setTimeout(() => {
      setSubtitles(prev => prev.filter(s => s.id !== id))
    }, SUBTITLE_TTL_MS)
  }, [onUtterance])

  /* ── External subtitle injection (e.g. receipt scan) ───────────── */

  const lastInjectedRef = useRef<number | null>(null)
  useEffect(() => {
    if (!injected) return
    if (lastInjectedRef.current === injected.nonce) return
    lastInjectedRef.current = injected.nonce
    pushSubtitle(injected.role, injected.text)
  }, [injected, pushSubtitle])

  /* ── Haptic-style flash ─────────────────────────────────────────── */

  const flash = useCallback(() => setFlashKey(k => k + 1), [])

  /* ── TTS playback + interrupt ───────────────────────────────────── */

  const interruptTTS = useCallback(() => {
    const a = audioRef.current
    if (a) {
      a.pause()
      a.src = ''
      audioRef.current = null
    }
    disconnect()
    setAiState(prev => (prev === 'speaking' ? 'idle' : prev))
  }, [disconnect])

  const playAudio = useCallback((b64: string, mime = 'audio/mpeg') => {
    interruptTTS()
    const audio = new Audio(`data:${mime};base64,${b64}`)
    audio.crossOrigin = 'anonymous'
    audioRef.current = audio
    setAiState('speaking')

    // Hook the analyser to the TTS element so the ring matches Finn's voice.
    try { connectAudio(audio) } catch { /* ignored — fall back to silent ring */ }

    const finish = () => {
      if (audioRef.current === audio) {
        audioRef.current = null
        disconnect()
        setAiState('idle')
      }
    }
    audio.onended = finish
    audio.onerror = finish
    audio.play().catch(finish)
  }, [interruptTTS, connectAudio, disconnect])

  /* ── Recording lifecycle ────────────────────────────────────────── */

  const startListening = useCallback(async () => {
    if (recorderRef.current) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const mime = pickRecordingMime()
      const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
      mr.ondataavailable = e => chunksRef.current.push(e.data)
      mr.start()
      recorderRef.current = mr
      connectStream(stream)
      setAiState('listening')
    } catch {
      pushSubtitle('assistant', '⚠️ Microphone access denied.')
    }
  }, [connectStream, pushSubtitle])

  const stopAndSend = useCallback(async () => {
    const mr = recorderRef.current
    if (!mr || mr.state === 'inactive') return
    mr.stop()
    disconnect()
    setAiState('thinking')

    mr.onstop = async () => {
      const mime = mr.mimeType || pickRecordingMime()
      const blob = new Blob(chunksRef.current, { type: mime })
      mr.stream.getTracks().forEach(t => t.stop())
      recorderRef.current = null

      const fd = new FormData()
      fd.append('audio', blob, `recording.${recordingExt(mime)}`)
      const ac = new AbortController()
      abortRef.current = ac
      try {
        const r = await fetch(apiUrl('/voice'), { method: 'POST', body: fd, signal: ac.signal })
        const data = await r.json().catch(async () => ({ error: await r.text() }))
        if (!r.ok) throw new Error(data.error ?? 'Voice processing failed')
        if (data.transcript) pushSubtitle('user', data.transcript)
        if (data.response)   pushSubtitle('assistant', data.response)
        if (data.audio_b64)  playAudio(data.audio_b64, data.audio_mime)
        else setAiState('idle')
      } catch (e: unknown) {
        if ((e as Error).name === 'AbortError') { setAiState('idle'); return }
        pushSubtitle('assistant', '⚠️ ' + (e instanceof Error ? e.message : 'Voice processing failed'))
        setAiState('idle')
      } finally {
        abortRef.current = null
      }
    }
  }, [apiUrl, disconnect, pushSubtitle, playAudio])

  /* ── Pulse-button gestures ──────────────────────────────────────── */

  const onPulseDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault()
    if (aiState === 'speaking') {
      // Barge-in via the button itself: kill TTS, flash, start recording.
      interruptTTS(); flash(); void startListening(); return
    }
    if (aiState === 'thinking') {
      abortRef.current?.abort(); setAiState('idle'); return
    }
    if (aiState === 'idle') void startListening()
  }, [aiState, interruptTTS, flash, startListening])

  const onPulseUp = useCallback(() => {
    if (aiState === 'listening') void stopAndSend()
  }, [aiState, stopAndSend])

  /* ── Tap-anywhere on the stage = barge-in (only while speaking) ── */

  const onStageTap = useCallback(() => {
    if (aiState !== 'speaking') return
    interruptTTS()
    flash()
    void startListening()
  }, [aiState, interruptTTS, flash, startListening])

  /* ── Cleanup ────────────────────────────────────────────────────── */

  useEffect(() => () => {
    recorderRef.current?.stream.getTracks().forEach(t => t.stop())
    abortRef.current?.abort()
    audioRef.current?.pause()
  }, [])

  /* ── Render ─────────────────────────────────────────────────────── */

  const isListening = aiState === 'listening'

  return (
    <div
      onPointerDown={onStageTap}
      style={{
        position: 'fixed', inset: 0, overflow: 'hidden',
        display: 'grid',
        gridTemplateRows: 'auto 1fr auto',
        userSelect: 'none',
      }}
    >
      {/* ── Ambient radial pulse layer ─────────────────────────────── */}
      <div
        aria-hidden
        style={{
          position: 'absolute', inset: -80, pointerEvents: 'none', zIndex: 0,
          background: isListening
            ? 'radial-gradient(700px 700px at 50% 60%, rgba(255,77,109,0.22), transparent 70%)'
            : aiState === 'speaking'
            ? 'radial-gradient(720px 720px at 50% 55%, rgba(0,220,132,0.22), transparent 70%)'
            : aiState === 'thinking'
            ? 'radial-gradient(620px 620px at 50% 60%, rgba(255,214,10,0.14), transparent 70%)'
            : 'radial-gradient(560px 560px at 50% 60%, rgba(0,220,132,0.10), transparent 70%)',
          animation: isListening ? 'radial-listen 2.4s ease-in-out infinite' : 'none',
          transition: 'background 0.5s ease',
        }}
      />

      {/* ── Haptic-style flash (re-mounts on flashKey change) ──────── */}
      <AnimatePresence>
        <motion.div
          key={flashKey}
          aria-hidden
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.32, 0] }}
          transition={{ duration: 0.32, times: [0, 0.18, 1] }}
          style={{
            position: 'absolute', inset: 0, pointerEvents: 'none',
            background: 'rgba(255,255,255,1)', mixBlendMode: 'screen', zIndex: 50,
          }}
        />
      </AnimatePresence>

      {/* ── Top bar ───────────────────────────────────────────────── */}
      <header style={{
        position: 'relative', zIndex: 2,
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '14px 22px',
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 9,
          background: 'linear-gradient(135deg, #00DC84, #00B870)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#0A1A12', fontWeight: 800, fontSize: '0.95rem',
          boxShadow: 'var(--shadow-green)',
        }}>F</div>
        <div style={{ fontSize: '1rem', fontWeight: 700, letterSpacing: '-0.01em' }}>
          Finn <span style={{ color: 'var(--muted)', fontWeight: 400 }}>by bunq</span>
        </div>
        <div style={{ flex: 1 }} />
        {topRightSlot}
      </header>

      {/* ── Center stage: avatar + waveform ring ─────────────────── */}
      <main style={{
        position: 'relative', zIndex: 1,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{
          position: 'relative',
          width: 460, height: 460,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <WaveformRing bins={bins} state={aiState} size={460} />
          <motion.div
            layout
            animate={{ scale: aiState === 'speaking' ? 1.04 : 1 }}
            transition={{ type: 'spring', stiffness: 220, damping: 18 }}
            style={{ position: 'relative', zIndex: 2 }}
          >
            {/* 50% larger than the previous 200 baseline. */}
            <Avatar
              speaking={aiState === 'speaking'}
              listening={aiState === 'listening'}
              thinking={aiState === 'thinking'}
              size={300}
              showCaption={false}
            />
          </motion.div>
        </div>
      </main>

      {/* ── Bottom third: subtitles + pulse button ──────────────── */}
      <section style={{
        position: 'relative', zIndex: 2,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26,
        padding: '0 24px 36px',
      }}>
        {/* Live subtitles */}
        <div style={{
          width: 'min(820px, 92vw)', minHeight: 140,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
          textAlign: 'center', justifyContent: 'flex-end',
        }}>
          <AnimatePresence initial={false}>
            {subtitles.map(s => (
              <motion.div
                key={s.id}
                initial={{ opacity: 0, y: 18, filter: 'blur(6px)' }}
                animate={{ opacity: 1, y: 0,  filter: 'blur(0px)' }}
                exit={{    opacity: 0, y: -10, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.2, 0.7, 0.2, 1] }}
                style={{
                  fontSize: 'clamp(1.2rem, 2.4vw, 1.85rem)',
                  fontWeight: s.role === 'user' ? 700 : 500,
                  lineHeight: 1.3, letterSpacing: '-0.01em',
                  color: s.role === 'user' ? '#FFFFFF' : '#00DC84',
                  textShadow: s.role === 'user'
                    ? '0 2px 18px rgba(0,0,0,0.45)'
                    : '0 2px 24px rgba(0,220,132,0.25)',
                  maxWidth: '100%',
                }}
              >
                {s.role === 'user' ? '“' + s.text + '”' : s.text}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* The Pulse */}
        <PulseButton state={aiState} onPointerDown={onPulseDown} onPointerUp={onPulseUp} />
      </section>
    </div>
  )
}
