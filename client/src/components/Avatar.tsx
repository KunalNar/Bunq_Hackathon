import { useEffect, useRef } from 'react'

interface Props {
  speaking: boolean
  listening: boolean
  thinking?: boolean
  /** Pixel size of the avatar's bounding box. Default 200 (50% bigger ≈ 300). */
  size?: number
  /** Hide the "Finn / by bunq" caption when the surrounding hero owns its own copy. */
  showCaption?: boolean
}

export default function Avatar({
  speaking, listening, thinking = false, size = 200, showCaption = true,
}: Props) {
  const mouthOuterRef = useRef<SVGEllipseElement>(null)
  const mouthInnerRef = useRef<SVGEllipseElement>(null)
  const mouthTeethRef = useRef<SVGEllipseElement>(null)
  const leftEyeRef    = useRef<SVGEllipseElement>(null)
  const rightEyeRef   = useRef<SVGEllipseElement>(null)
  const leftPupilRef  = useRef<SVGCircleElement>(null)
  const rightPupilRef = useRef<SVGCircleElement>(null)
  const leftShineRef  = useRef<SVGCircleElement>(null)
  const rightShineRef = useRef<SVGCircleElement>(null)
  const rafRef        = useRef<number | undefined>(undefined)
  const startRef      = useRef(0)

  // Mouth speaking animation — direct DOM updates, zero React re-renders
  useEffect(() => {
    if (!speaking) {
      if (rafRef.current !== undefined) cancelAnimationFrame(rafRef.current)
      mouthOuterRef.current?.setAttribute('ry', '2.5')
      mouthInnerRef.current?.setAttribute('ry', '0')
      mouthTeethRef.current?.setAttribute('ry', '0')
      return
    }

    startRef.current = performance.now()

    function tick(now: number) {
      const t = (now - startRef.current) / 1000
      // Mix of frequencies for a natural talking cadence
      const raw = Math.sin(t * 9) * 0.45 + Math.sin(t * 14) * 0.25 + Math.sin(t * 5.5) * 0.2 + 0.35
      const o = Math.max(0, Math.min(1, raw))
      mouthOuterRef.current?.setAttribute('ry', String(2.5 + o * 11))
      mouthInnerRef.current?.setAttribute('ry', String(o > 0.05 ? o * 10 : 0))
      mouthTeethRef.current?.setAttribute('ry', String(o > 0.25 ? o * 5.5 : 0))
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current !== undefined) cancelAnimationFrame(rafRef.current) }
  }, [speaking])

  // Natural blink loop — direct DOM updates
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>

    function closeLids() {
      leftEyeRef.current?.setAttribute('ry', '1')
      rightEyeRef.current?.setAttribute('ry', '1')
      leftPupilRef.current?.setAttribute('display', 'none')
      rightPupilRef.current?.setAttribute('display', 'none')
      leftShineRef.current?.setAttribute('display', 'none')
      rightShineRef.current?.setAttribute('display', 'none')
      timer = setTimeout(openLids, 130)
    }
    function openLids() {
      leftEyeRef.current?.setAttribute('ry', '11')
      rightEyeRef.current?.setAttribute('ry', '11')
      leftPupilRef.current?.setAttribute('display', '')
      rightPupilRef.current?.setAttribute('display', '')
      leftShineRef.current?.setAttribute('display', '')
      rightShineRef.current?.setAttribute('display', '')
      timer = setTimeout(closeLids, 2600 + Math.random() * 3000)
    }

    timer = setTimeout(closeLids, 1500 + Math.random() * 2000)
    return () => clearTimeout(timer)
  }, [])

  const glow = speaking
    ? 'drop-shadow(0 0 24px rgba(0,220,132,0.75))'
    : listening
    ? 'drop-shadow(0 0 24px rgba(255,77,109,0.65))'
    : thinking
    ? 'drop-shadow(0 0 22px rgba(255,214,10,0.55))'
    : 'drop-shadow(0 0 12px rgba(0,220,132,0.2))'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>

      {/* Outer wrapper: listening tilt, thinking tilt-up */}
      <div style={{
        transform: listening ? 'rotate(-4deg)' : thinking ? 'rotate(3deg) translateY(-2px)' : 'rotate(0deg)',
        transition: 'transform 0.4s ease',
      }}>
        {/* Inner wrapper: idle float or speaking bob */}
        <div style={{
          position: 'relative',
          width: size,
          height: Math.round(size * 1.10),
          animation: speaking
            ? 'avatarBob 0.42s ease-in-out infinite alternate'
            : 'avatarFloat 3.5s ease-in-out infinite',
          filter: glow,
          transition: 'filter 0.35s ease',
        }}>
          {/* Thinking orbit — only visible while thinking */}
          {thinking && (
            <div style={{
              position: 'absolute', inset: -8,
              borderRadius: '50%',
              border: '2px dashed rgba(255,214,10,0.55)',
              animation: 'thinking-orbit 4s linear infinite',
              pointerEvents: 'none',
            }} />
          )}
          <svg viewBox="0 0 200 220" xmlns="http://www.w3.org/2000/svg"
               style={{ width: '100%', height: '100%' }}>

            {/* ── Neck ── */}
            <rect x="83" y="176" width="34" height="28" rx="6" fill="#E8A880" />

            {/* ── Shirt / collar ── */}
            <ellipse cx="100" cy="216" rx="64" ry="18" fill="#00DC84" />
            <path d="M 66 204 L 100 220 L 134 204 Z" fill="white" opacity="0.88" />

            {/* ── Face ── */}
            <ellipse cx="100" cy="104" rx="70" ry="80" fill="#F0C090" />

            {/* ── Hair ── */}
            <ellipse cx="100" cy="41"  rx="71" ry="47" fill="#2C1810" />
            <ellipse cx="31"  cy="87"  rx="13" ry="38" fill="#2C1810" />
            <ellipse cx="169" cy="87"  rx="13" ry="38" fill="#2C1810" />

            {/* ── Ears ── */}
            <ellipse cx="30"  cy="110" rx="10" ry="14" fill="#E8A880" />
            <ellipse cx="170" cy="110" rx="10" ry="14" fill="#E8A880" />
            <ellipse cx="30"  cy="110" rx="6"  ry="8"  fill="#D48060" />
            <ellipse cx="170" cy="110" rx="6"  ry="8"  fill="#D48060" />

            {/* ── Eyebrows ── */}
            <path d="M 58 78 Q 75 70 92 75"  stroke="#2C1810" strokeWidth="3.5" strokeLinecap="round" fill="none" />
            <path d="M 108 75 Q 125 70 142 78" stroke="#2C1810" strokeWidth="3.5" strokeLinecap="round" fill="none" />

            {/* ── Eye whites ── */}
            <ellipse ref={leftEyeRef}  cx="75"  cy="102" rx="14" ry="11" fill="white" />
            <ellipse ref={rightEyeRef} cx="125" cy="102" rx="14" ry="11" fill="white" />

            {/* ── Pupils ── */}
            <circle ref={leftPupilRef}  cx="77"  cy="104" r="8" fill="#1A0A06" />
            <circle ref={rightPupilRef} cx="127" cy="104" r="8" fill="#1A0A06" />

            {/* ── Eye shine ── */}
            <circle ref={leftShineRef}  cx="80"  cy="101" r="3" fill="white" opacity="0.9" />
            <circle ref={rightShineRef} cx="130" cy="101" r="3" fill="white" opacity="0.9" />

            {/* ── Nose ── */}
            <ellipse cx="95"  cy="126" rx="4" ry="3" fill="#C07850" opacity="0.4" />
            <ellipse cx="105" cy="126" rx="4" ry="3" fill="#C07850" opacity="0.4" />

            {/* ── Cheeks — brighten when listening ── */}
            <ellipse cx="54"  cy="128" rx="14" ry="9" fill="#FFB0A0"
              opacity={listening ? 0.45 : 0.18}
              style={{ transition: 'opacity 0.4s' }} />
            <ellipse cx="146" cy="128" rx="14" ry="9" fill="#FFB0A0"
              opacity={listening ? 0.45 : 0.18}
              style={{ transition: 'opacity 0.4s' }} />

            {/* ── Mouth ──
                mouthOuter: the visible lip shape, ry grows when speaking
                upper-lip path: Cupid's bow, stays fixed
                mouthInner: dark cavity that appears as mouth opens
                mouthTeeth: white teeth that appear at moderate open              */}
            <ellipse ref={mouthOuterRef} cx="100" cy="151" rx="20" ry="2.5" fill="#C07060" />
            <path d="M 80 151 Q 90 147 100 149 Q 110 147 120 151" fill="#A05848" />
            <ellipse ref={mouthInnerRef} cx="100" cy="154" rx="16" ry="0" fill="#2A0808" />
            <ellipse ref={mouthTeethRef} cx="100" cy="150" rx="13" ry="0" fill="white" />

          </svg>
        </div>
      </div>

      {/* ── Name tag ── */}
      {showCaption && (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text)' }}>Finn</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginTop: 2 }}>
            {speaking ? '🔊 Speaking…'
              : listening ? '🎙️ Listening…'
              : thinking ? '💭 Thinking…'
              : 'by bunq'}
          </div>
        </div>
      )}

      <style>{`
        @keyframes avatarFloat {
          0%, 100% { transform: translateY(0px)  rotate(0deg); }
          50%       { transform: translateY(-7px) rotate(0.4deg); }
        }
        @keyframes avatarBob {
          from { transform: translateY(0px)  rotate(-1.5deg); }
          to   { transform: translateY(-5px) rotate(1.5deg); }
        }
      `}</style>
    </div>
  )
}
