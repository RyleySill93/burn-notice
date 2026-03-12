import { motion } from 'framer-motion'
import type { BaseBadgeProps, Metric, Rank } from './badge-types'
import { BadgeFrame, CountChip, FlameGlyph, ShineSweep, TimeGlyph, WeeklyMark, useBadgeId } from './badge-primitives'

const RANK_PALETTES = {
  gold: {
    stops: [
      { offset: '0%', color: '#fff2a8' },
      { offset: '18%', color: '#ffd95a' },
      { offset: '48%', color: '#f59e0b' },
      { offset: '75%', color: '#b45309' },
      { offset: '100%', color: '#fde68a' },
    ],
    rim: '#fef3c7',
    glow: 'radial-gradient(circle, rgba(251,191,36,0.32) 0%, rgba(251,191,36,0.08) 40%, transparent 72%)',
    accent: '#fbbf24',
  },
  silver: {
    stops: [
      { offset: '0%', color: '#f8fafc' },
      { offset: '18%', color: '#cbd5e1' },
      { offset: '48%', color: '#94a3b8' },
      { offset: '75%', color: '#475569' },
      { offset: '100%', color: '#e2e8f0' },
    ],
    rim: '#e2e8f0',
    glow: 'radial-gradient(circle, rgba(203,213,225,0.3) 0%, rgba(203,213,225,0.08) 40%, transparent 72%)',
    accent: '#cbd5e1',
  },
  bronze: {
    stops: [
      { offset: '0%', color: '#ffd3a8' },
      { offset: '18%', color: '#fb923c' },
      { offset: '48%', color: '#c2410c' },
      { offset: '75%', color: '#7c2d12' },
      { offset: '100%', color: '#fdba74' },
    ],
    rim: '#fdba74',
    glow: 'radial-gradient(circle, rgba(249,115,22,0.3) 0%, rgba(249,115,22,0.08) 40%, transparent 72%)',
    accent: '#fb923c',
  },
} as const

export function RankingMedal({
  rank,
  metric,
  count,
  size = 56,
  className,
}: BaseBadgeProps & {
  rank: Rank
  metric: Metric
  count: number
}) {
  const id = useBadgeId(`rank-${rank}-${metric}`)
  const palette = RANK_PALETTES[rank]

  return (
    <BadgeFrame size={size} className={className} glowColor={palette.glow}>
      <svg width={size} height={size} viewBox="0 0 56 56" className="overflow-visible">
        <defs>
          <linearGradient id={`${id}-metal`} x1="0%" y1="0%" x2="100%" y2="100%">
            {palette.stops.map((s, i) => (
              <stop key={i} offset={s.offset} stopColor={s.color} />
            ))}
          </linearGradient>
          <linearGradient id={`${id}-rim`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.9)" />
            <stop offset="35%" stopColor="rgba(255,255,255,0.25)" />
            <stop offset="100%" stopColor="rgba(0,0,0,0.35)" />
          </linearGradient>
          <radialGradient id={`${id}-core`} cx="35%" cy="28%" r="70%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.95)" />
            <stop offset="20%" stopColor="rgba(255,255,255,0.35)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
        </defs>

        <motion.g
          animate={{ rotate: [0, 1.4, 0, -1.4, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
          style={{ originX: '50%', originY: '50%' }}
        >
          {/* Outer disc */}
          <circle cx="28" cy="28" r="21.5" fill={`url(#${id}-metal)`} stroke={palette.rim} strokeWidth="1.2" />
          {/* Inner ring */}
          <circle cx="28" cy="28" r="18.2" fill="rgba(10,10,10,0.14)" stroke="rgba(255,255,255,0.18)" strokeWidth="0.8" />
          {/* Specular highlight */}
          <circle cx="23" cy="18" r="12" fill={`url(#${id}-core)`} opacity="0.7" />
          {/* Rim bevel */}
          <circle cx="28" cy="28" r="22.4" fill="none" stroke={`url(#${id}-rim)`} strokeWidth="1.1" opacity="0.65" />

          {/* Tick marks */}
          {Array.from({ length: 12 }).map((_, i) => (
            <line
              key={i}
              x1="28"
              y1="8.4"
              x2="28"
              y2="12.1"
              stroke="rgba(255,255,255,0.23)"
              strokeWidth="1"
              transform={`rotate(${i * 30} 28 28)`}
            />
          ))}

          <WeeklyMark />
          {metric === 'tokens' ? <FlameGlyph /> : <TimeGlyph />}
          <CountChip count={count} />

          {/* Ribbon tails */}
          <g opacity="0.95">
            <path d="M16.5 39.2L12.6 49.4 18.6 46.9 22 52 24.1 40.7Z" fill={palette.accent} />
            <path d="M39.5 39.2L43.4 49.4 37.4 46.9 34 52 31.9 40.7Z" fill={palette.accent} />
          </g>
        </motion.g>

        <ShineSweep id={id} />
      </svg>
    </BadgeFrame>
  )
}
