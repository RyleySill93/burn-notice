import React, { useMemo } from 'react'

type Intensity = 'low' | 'medium' | 'high'

interface FlameTongue {
  id: number
  left: number
  width: number
  height: number
  swayDuration: number
  bounceDuration: number
  delay: number
  sway: number
  tilt: number
  layer: 'back' | 'mid' | 'front'
}

const INTENSITY_CONFIG: Record<
  Intensity,
  {
    backCount: number
    midCount: number
    frontCount: number
    backHeight: [number, number]
    midHeight: [number, number]
    frontHeight: [number, number]
  }
> = {
  low: {
    backCount: 8,
    midCount: 10,
    frontCount: 12,
    backHeight: [90, 150],
    midHeight: [65, 115],
    frontHeight: [38, 78],
  },
  medium: {
    backCount: 11,
    midCount: 14,
    frontCount: 17,
    backHeight: [120, 190],
    midHeight: [82, 135],
    frontHeight: [48, 92],
  },
  high: {
    backCount: 14,
    midCount: 18,
    frontCount: 22,
    backHeight: [145, 230],
    midHeight: [96, 155],
    frontHeight: [58, 108],
  },
}

function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function createLayer(
  count: number,
  heightRange: [number, number],
  widthRange: [number, number],
  layer: 'back' | 'mid' | 'front',
  rand: () => number,
  jitter: number,
): FlameTongue[] {
  return Array.from({ length: count }, (_, i) => {
    const lane = i / Math.max(1, count - 1)
    const height = heightRange[0] + rand() * (heightRange[1] - heightRange[0])
    const width = widthRange[0] + rand() * (widthRange[1] - widthRange[0])

    return {
      id: i,
      left: lane * 100 + (rand() - 0.5) * jitter,
      width,
      height,
      swayDuration: 2.2 + rand() * 2.1,
      bounceDuration: 0.9 + rand() * 1.1,
      delay: -rand() * 4,
      sway: 4 + rand() * (layer === 'back' ? 10 : 7),
      tilt: -7 + rand() * 14,
      layer,
    }
  })
}

function buildFlames(intensity: Intensity) {
  const cfg = INTENSITY_CONFIG[intensity]
  const rand = mulberry32(intensity === 'low' ? 101 : intensity === 'medium' ? 202 : 303)

  return {
    back: createLayer(cfg.backCount, cfg.backHeight, [48, 92], 'back', rand, 6),
    mid: createLayer(cfg.midCount, cfg.midHeight, [34, 70], 'mid', rand, 5),
    front: createLayer(cfg.frontCount, cfg.frontHeight, [18, 42], 'front', rand, 4),
  }
}

function FlameLayer({ tongues, className }: { tongues: FlameTongue[]; className: string }) {
  return (
    <div className={className}>
      {tongues.map((tongue) => (
        <div
          key={`${tongue.layer}-${tongue.id}`}
          className="af-tongue-wrap"
          style={
            {
              left: `${tongue.left}%`,
              ['--w' as string]: `${tongue.width}px`,
              ['--h' as string]: `${tongue.height}px`,
              ['--sway' as string]: `${tongue.sway}px`,
              ['--tilt-a' as string]: `${tongue.tilt}deg`,
              ['--tilt-b' as string]: `${-tongue.tilt * 0.6}deg`,
              ['--sway-duration' as string]: `${tongue.swayDuration}s`,
              ['--bounce-duration' as string]: `${tongue.bounceDuration}s`,
              animationDelay: `${tongue.delay}s`,
            } as React.CSSProperties
          }
        >
          <div className="af-tongue" />
        </div>
      ))}
    </div>
  )
}

const FLAME_STYLES = `
  @keyframes af-sway {
    0% { transform: translateX(0px) rotate(var(--tilt-a)); }
    25% { transform: translateX(calc(var(--sway) * 0.35)) rotate(calc(var(--tilt-a) + 2deg)); }
    50% { transform: translateX(var(--sway)) rotate(var(--tilt-b)); }
    75% { transform: translateX(calc(var(--sway) * -0.25)) rotate(calc(var(--tilt-a) - 1deg)); }
    100% { transform: translateX(0px) rotate(var(--tilt-a)); }
  }

  @keyframes af-bounce {
    0% { transform: scaleY(0.92) scaleX(0.98); }
    25% { transform: scaleY(1.05) scaleX(1.02); }
    50% { transform: scaleY(0.96) scaleX(0.99); }
    75% { transform: scaleY(1.08) scaleX(1.03); }
    100% { transform: scaleY(0.94) scaleX(1); }
  }

  .af-root {
    position: fixed;
    inset: auto 0 0 0;
    height: 320px;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
    filter: blur(6px);
    opacity: 0.45;
  }

  .af-strip {
    position: absolute;
    inset: auto 0 0 0;
  }

  .af-strip--orange {
    height: 112px;
    background: #ff8a00;
    clip-path: polygon(
      0% 100%, 0% 52%, 4% 58%, 7% 34%, 11% 62%, 15% 28%, 19% 60%, 24% 18%,
      29% 56%, 33% 30%, 37% 64%, 41% 23%, 45% 58%, 49% 20%, 53% 62%, 57% 29%,
      61% 58%, 65% 17%, 69% 64%, 73% 32%, 77% 54%, 81% 24%, 85% 60%, 89% 35%,
      93% 57%, 96% 40%, 100% 54%, 100% 100%
    );
  }

  .af-layer {
    position: absolute;
    inset: auto 0 0 0;
    overflow: visible;
  }

  .af-layer--back { height: 238px; }
  .af-layer--mid { height: 170px; }
  .af-layer--front { height: 112px; }

  .af-tongue-wrap {
    position: absolute;
    bottom: 0;
    width: var(--w);
    height: var(--h);
    margin-left: calc(var(--w) * -0.5);
    transform-origin: center bottom;
    animation: af-sway var(--sway-duration) ease-in-out infinite;
    will-change: transform;
  }

  .af-tongue {
    position: absolute;
    inset: 0;
    transform-origin: center bottom;
    animation: af-bounce var(--bounce-duration) ease-in-out infinite;
  }

  .af-layer--back .af-tongue {
    background: #ff3b00;
    clip-path: polygon(
      50% 0%, 58% 6%, 66% 16%, 74% 31%, 83% 54%, 91% 77%, 100% 100%,
      80% 94%, 73% 73%, 66% 61%, 61% 46%, 55% 29%, 49% 38%, 42% 58%,
      36% 79%, 27% 92%, 0% 100%, 10% 74%, 19% 53%, 29% 34%, 39% 17%
    );
  }

  .af-layer--mid .af-tongue {
    background: #ff8a00;
    clip-path: polygon(
      50% 0%, 60% 10%, 70% 28%, 80% 54%, 90% 82%, 100% 100%,
      82% 92%, 75% 70%, 68% 56%, 61% 38%, 54% 20%, 47% 33%, 39% 58%,
      31% 80%, 22% 93%, 0% 100%, 10% 80%, 20% 56%, 30% 33%, 40% 14%
    );
  }

  .af-layer--front .af-tongue {
    background: #ffd400;
    clip-path: polygon(
      50% 0%, 61% 16%, 72% 42%, 84% 74%, 100% 100%, 78% 91%, 69% 67%,
      60% 44%, 51% 24%, 43% 46%, 34% 72%, 23% 91%, 0% 100%, 15% 72%,
      28% 40%, 40% 14%
    );
  }

  .af-embers {
    position: absolute;
    inset: auto 0 132px 0;
    height: 90px;
  }

  .af-embers span {
    position: absolute;
    display: block;
    width: 14px;
    height: 22px;
    background: #ff5a00;
    clip-path: polygon(50% 0%, 67% 18%, 82% 44%, 76% 73%, 58% 100%, 42% 90%, 24% 64%, 20% 36%, 33% 12%);
    opacity: 0.95;
    animation: af-sway 2.8s ease-in-out infinite, af-bounce 1.4s ease-in-out infinite;
  }
`

export function AnimatedFlames({ intensity = 'medium' }: { intensity?: Intensity }) {
  const flames = useMemo(() => buildFlames(intensity), [intensity])

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: FLAME_STYLES }} />
      <div className="af-root" aria-hidden="true">
        <div className="af-strip af-strip--orange" />

        <FlameLayer tongues={flames.back} className="af-layer af-layer--back" />
        <FlameLayer tongues={flames.mid} className="af-layer af-layer--mid" />
        <FlameLayer tongues={flames.front} className="af-layer af-layer--front" />

        <div className="af-embers">
          <span style={{ left: '12%', animationDelay: '-1.1s' }} />
          <span style={{ left: '27%', bottom: '18px', animationDelay: '-2.4s' }} />
          <span style={{ left: '46%', bottom: '10px', animationDelay: '-0.8s' }} />
          <span style={{ left: '71%', bottom: '26px', animationDelay: '-1.9s' }} />
          <span style={{ left: '88%', bottom: '6px', animationDelay: '-2.9s' }} />
        </div>
      </div>
    </>
  )
}
