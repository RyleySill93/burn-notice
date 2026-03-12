import { useMemo } from 'react'

const FLAME_STYLE = `
@keyframes flame-flicker {
  0%, 100% { transform: scaleY(1) scaleX(1) translateY(0); opacity: var(--f-op); }
  25% { transform: scaleY(1.15) scaleX(0.9) translateY(-8px); opacity: calc(var(--f-op) * 1.1); }
  50% { transform: scaleY(0.85) scaleX(1.1) translateY(4px); opacity: calc(var(--f-op) * 0.8); }
  75% { transform: scaleY(1.1) scaleX(0.95) translateY(-12px); opacity: var(--f-op); }
}
@keyframes flame-sway {
  0%, 100% { transform: translateX(0) rotate(0deg); }
  33% { transform: translateX(6px) rotate(2deg); }
  66% { transform: translateX(-4px) rotate(-1.5deg); }
}
`

interface FlameConfig {
  left: number
  width: number
  height: number
  hue: number
  opacity: number
  flickerDuration: number
  flickerDelay: number
  swayDuration: number
  swayDelay: number
}

export function AnimatedFlames({ intensity = 'medium' }: { intensity?: 'low' | 'medium' | 'high' }) {
  const count = intensity === 'high' ? 18 : intensity === 'medium' ? 12 : 8
  const maxHeight = intensity === 'high' ? 160 : intensity === 'medium' ? 120 : 80

  const flames = useMemo<FlameConfig[]>(
    () =>
      Array.from({ length: count }, (_, i) => ({
        left: (i / count) * 100 + (Math.random() - 0.5) * (100 / count) * 0.6,
        width: 30 + Math.random() * 50,
        height: 40 + Math.random() * maxHeight,
        hue: 15 + Math.random() * 30,
        opacity: 0.15 + Math.random() * 0.25,
        flickerDuration: 1.5 + Math.random() * 2,
        flickerDelay: Math.random() * 3,
        swayDuration: 3 + Math.random() * 4,
        swayDelay: Math.random() * 4,
      })),
    [count, maxHeight],
  )

  return (
    <div className="fixed bottom-0 left-0 right-0 pointer-events-none z-0" style={{ height: maxHeight + 40 }}>
      <style dangerouslySetInnerHTML={{ __html: FLAME_STYLE }} />
      {flames.map((f, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            bottom: -8,
            left: `${f.left}%`,
            width: f.width,
            height: f.height,
            transformOrigin: 'bottom center',
            animation: `flame-sway ${f.swayDuration}s ease-in-out ${f.swayDelay}s infinite`,
          }}
        >
          <div
            style={{
              width: '100%',
              height: '100%',
              borderRadius: '50% 50% 50% 50% / 60% 60% 40% 40%',
              background: `radial-gradient(ellipse at 50% 85%, hsla(${f.hue}, 100%, 55%, ${f.opacity}), hsla(${f.hue + 10}, 95%, 45%, ${f.opacity * 0.5}), transparent 70%)`,
              filter: 'blur(6px)',
              ['--f-op' as string]: f.opacity,
              animation: `flame-flicker ${f.flickerDuration}s ease-in-out ${f.flickerDelay}s infinite`,
            }}
          />
        </div>
      ))}
      <div
        className="absolute bottom-0 left-0 right-0"
        style={{
          height: 40,
          background: 'linear-gradient(to top, rgba(249,115,22,0.12), rgba(234,88,12,0.04), transparent)',
        }}
      />
    </div>
  )
}
