import { useEffect, useRef } from 'react'

interface Props {
  speaking: boolean
  listening: boolean
}

export default function Avatar({ speaking, listening }: Props) {
  const glowRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!glowRef.current) return
    glowRef.current.style.boxShadow = speaking
      ? '0 0 40px 12px rgba(0,220,132,0.45)'
      : listening
      ? '0 0 40px 12px rgba(255,77,109,0.4)'
      : '0 0 24px 4px rgba(0,220,132,0.1)'
  }, [speaking, listening])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <div
        ref={glowRef}
        style={{
          width: 160,
          height: 160,
          borderRadius: '50%',
          overflow: 'hidden',
          border: '3px solid rgba(0,220,132,0.35)',
          transition: 'box-shadow 0.3s ease',
          position: 'relative',
        }}
      >
        <img
          src="/avatar.png"
          alt="Finn avatar"
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
        {speaking && (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'rgba(0,220,132,0.08)',
            animation: 'avatarPulse 0.7s ease-in-out infinite alternate',
          }} />
        )}
      </div>

      <div style={{ textAlign: 'center' }}>
        <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text)' }}>Finn</div>
        <div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginTop: 2 }}>
          {speaking ? '🔊 Speaking…' : listening ? '🎙️ Listening…' : 'by bunq'}
        </div>
      </div>

      <style>{`
        @keyframes avatarPulse {
          from { opacity: 0.3; }
          to   { opacity: 0.8; }
        }
      `}</style>
    </div>
  )
}
