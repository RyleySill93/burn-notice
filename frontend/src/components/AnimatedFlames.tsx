import { useMemo } from 'react'

const FLAME_STYLE = `
@keyframes flame-dance {
  0%, 100% { transform: scaleY(1) scaleX(1) translateY(0); }
  15% { transform: scaleY(1.3) scaleX(0.8) translateY(-18px); }
  30% { transform: scaleY(0.7) scaleX(1.2) translateY(6px); }
  50% { transform: scaleY(1.25) scaleX(0.85) translateY(-24px); }
  65% { transform: scaleY(0.9) scaleX(1.1) translateY(-4px); }
  80% { transform: scaleY(1.15) scaleX(0.9) translateY(-14px); }
}
@keyframes flame-sway {
  0%, 100% { transform: translateX(0) rotate(0deg); }
  20% { transform: translateX(10px) rotate(4deg); }
  40% { transform: translateX(-6px) rotate(-3deg); }
  60% { transform: translateX(8px) rotate(3deg); }
  80% { transform: translateX(-10px) rotate(-4deg); }
}
@keyframes flame-pulse {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 1; }
}
@keyframes spark-rise {
  0% { transform: translateY(0) scale(1); opacity: 1; }
  100% { transform: translateY(-60px) scale(0); opacity: 0; }
}
`

interface FlameConfig {
  left: number
  width: number
  height: number
  hue: number
  danceDuration: number
  danceDelay: number
  swayDuration: number
  swayDelay: number
  sparkDelay: number
}

export function AnimatedFlames({ intensity = 'medium' }: { intensity?: 'low' | 'medium' | 'high' }) {
  const count = intensity === 'high' ? 22 : intensity === 'medium' ? 15 : 10
  const maxHeight = intensity === 'high' ? 180 : intensity === 'medium' ? 140 : 100

  const flames = useMemo<FlameConfig[]>(
    () =>
      Array.from({ length: count }, (_, i) => ({
        left: (i / count) * 100 + (Math.random() - 0.5) * (100 / count) * 0.7,
        width: 40 + Math.random() * 40,
        height: 50 + Math.random() * maxHeight,
        hue: 10 + Math.random() * 35,
        danceDuration: 0.6 + Math.random() * 1.0,
        danceDelay: Math.random() * 2,
        swayDuration: 1.5 + Math.random() * 2,
        swayDelay: Math.random() * 3,
        sparkDelay: Math.random() * 4,
      })),
    [count, maxHeight],
  )

  return (
    <div className="fixed bottom-0 left-0 right-0 pointer-events-none z-0" style={{ height: maxHeight + 60 }}>
      <style dangerouslySetInnerHTML={{ __html: FLAME_STYLE }} />
      {flames.map((f, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            bottom: -4,
            left: `${f.left}%`,
            width: f.width,
            height: f.height,
            transformOrigin: 'bottom center',
            animation: `flame-sway ${f.swayDuration}s ease-in-out ${f.swayDelay}s infinite`,
          }}
        >
          {/* Outer glow layer */}
          <div
            style={{
              position: 'absolute',
              inset: '-20%',
              borderRadius: '50% 50% 50% 50% / 60% 60% 40% 40%',
              background: `radial-gradient(ellipse at 50% 80%, hsla(${f.hue}, 100%, 50%, 0.35), transparent 70%)`,
              filter: 'blur(8px)',
              animation: `flame-pulse 1.5s ease-in-out ${f.danceDelay}s infinite`,
            }}
          />
          {/* Main flame body */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50% 50% 50% 50% / 60% 60% 40% 40%',
              background: `
                radial-gradient(ellipse at 50% 90%, hsla(50, 100%, 70%, 0.9) 0%, transparent 30%),
                radial-gradient(ellipse at 50% 70%, hsla(${f.hue}, 100%, 55%, 0.85) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, hsla(${f.hue + 10}, 100%, 45%, 0.7) 0%, transparent 65%)
              `,
              animation: `flame-dance ${f.danceDuration}s ease-in-out ${f.danceDelay}s infinite`,
              transformOrigin: 'bottom center',
            }}
          />
          {/* Bright inner core */}
          <div
            style={{
              position: 'absolute',
              bottom: '5%',
              left: '25%',
              width: '50%',
              height: '40%',
              borderRadius: '50% 50% 50% 50% / 60% 60% 40% 40%',
              background: 'radial-gradient(ellipse at 50% 80%, hsla(55, 100%, 85%, 0.9), hsla(45, 100%, 65%, 0.5) 50%, transparent 80%)',
              animation: `flame-dance ${f.danceDuration * 0.8}s ease-in-out ${f.danceDelay + 0.1}s infinite`,
              transformOrigin: 'bottom center',
            }}
          />
          {/* Spark particle */}
          <div
            style={{
              position: 'absolute',
              top: '10%',
              left: '45%',
              width: 4,
              height: 4,
              borderRadius: '50%',
              background: 'hsla(40, 100%, 75%, 0.9)',
              animation: `spark-rise 1.8s ease-out ${f.sparkDelay}s infinite`,
            }}
          />
        </div>
      ))}
      {/* Hot base glow */}
      <div
        className="absolute bottom-0 left-0 right-0"
        style={{
          height: 50,
          background: 'linear-gradient(to top, rgba(249,115,22,0.25), rgba(239,68,68,0.1), transparent)',
        }}
      />
    </div>
  )
}
