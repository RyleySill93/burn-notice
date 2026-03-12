import type { BaseBadgeProps, MilestoneKind } from './badge-types'
import { BadgeFrame, FlameGlyph, ShineSweep, TimeGlyph, useBadgeId } from './badge-primitives'

interface MilestoneConfig {
  gradient: [string, string, string, string]
  glow: string
  icon: 'flame' | 'clock'
  label: string
  name: string
}

const MILESTONE_CONFIGS: Record<MilestoneKind, MilestoneConfig> = {
  // Token milestones (warm → hot → cosmic)
  token_1m: {
    gradient: ['#fed7aa', '#fb923c', '#c2410c', '#7c2d12'],
    glow: 'radial-gradient(circle, rgba(251,146,60,0.26) 0%, transparent 70%)',
    icon: 'flame',
    label: '1M',
    name: 'Spark',
  },
  token_10m: {
    gradient: ['#fde68a', '#f97316', '#c2410c', '#7c2d12'],
    glow: 'radial-gradient(circle, rgba(249,115,22,0.28) 0%, transparent 70%)',
    icon: 'flame',
    label: '10M',
    name: 'Ember',
  },
  token_50m: {
    gradient: ['#fdba74', '#ef4444', '#b91c1c', '#7f1d1d'],
    glow: 'radial-gradient(circle, rgba(239,68,68,0.28) 0%, transparent 70%)',
    icon: 'flame',
    label: '50M',
    name: 'Blaze',
  },
  token_100m: {
    gradient: ['#fca5a5', '#dc2626', '#991b1b', '#7f1d1d'],
    glow: 'radial-gradient(circle, rgba(220,38,38,0.3) 0%, transparent 70%)',
    icon: 'flame',
    label: '100M',
    name: 'Inferno',
  },
  token_250m: {
    gradient: ['#fda4af', '#e11d48', '#9f1239', '#881337'],
    glow: 'radial-gradient(circle, rgba(225,29,72,0.3) 0%, transparent 70%)',
    icon: 'flame',
    label: '250M',
    name: 'Firestorm',
  },
  token_500m: {
    gradient: ['#f9a8d4', '#db2777', '#9d174d', '#831843'],
    glow: 'radial-gradient(circle, rgba(219,39,119,0.3) 0%, transparent 70%)',
    icon: 'flame',
    label: '500M',
    name: 'Supernova',
  },
  token_1b: {
    gradient: ['#d8b4fe', '#7c3aed', '#5b21b6', '#3b0764'],
    glow: 'radial-gradient(circle, rgba(124,58,237,0.32) 0%, transparent 70%)',
    icon: 'flame',
    label: '1B',
    name: 'Solar Flare',
  },
  token_10b: {
    gradient: ['#f0abfc', '#a21caf', '#701a75', '#3b0764'],
    glow: 'radial-gradient(circle, rgba(162,28,175,0.35) 0%, transparent 70%)',
    icon: 'flame',
    label: '10B',
    name: 'Big Bang',
  },
  // Time milestones (cool → deep → cosmic)
  time_10h: {
    gradient: ['#cffafe', '#06b6d4', '#0e7490', '#155e75'],
    glow: 'radial-gradient(circle, rgba(6,182,212,0.26) 0%, transparent 70%)',
    icon: 'clock',
    label: '10h',
    name: 'Clocked In',
  },
  time_100h: {
    gradient: ['#a5f3fc', '#0891b2', '#0e7490', '#164e63'],
    glow: 'radial-gradient(circle, rgba(8,145,178,0.28) 0%, transparent 70%)',
    icon: 'clock',
    label: '100h',
    name: 'Grinder',
  },
  time_500h: {
    gradient: ['#bae6fd', '#0284c7', '#075985', '#0c4a6e'],
    glow: 'radial-gradient(circle, rgba(2,132,199,0.28) 0%, transparent 70%)',
    icon: 'clock',
    label: '500h',
    name: 'Marathoner',
  },
  time_1000h: {
    gradient: ['#c7d2fe', '#4338ca', '#3730a3', '#1e1b4b'],
    glow: 'radial-gradient(circle, rgba(67,56,202,0.3) 0%, transparent 70%)',
    icon: 'clock',
    label: '1Kh',
    name: 'Ironman',
  },
  time_2500h: {
    gradient: ['#c4b5fd', '#6d28d9', '#4c1d95', '#2e1065'],
    glow: 'radial-gradient(circle, rgba(109,40,217,0.3) 0%, transparent 70%)',
    icon: 'clock',
    label: '2.5K',
    name: 'Centurion',
  },
  time_5000h: {
    gradient: ['#d8b4fe', '#9333ea', '#7e22ce', '#3b0764'],
    glow: 'radial-gradient(circle, rgba(147,51,234,0.32) 0%, transparent 70%)',
    icon: 'clock',
    label: '5Kh',
    name: 'Titan',
  },
  time_10000h: {
    gradient: ['#f0abfc', '#a21caf', '#86198f', '#4a044e'],
    glow: 'radial-gradient(circle, rgba(162,28,175,0.35) 0%, transparent 70%)',
    icon: 'clock',
    label: '10K',
    name: 'Eternal',
  },
  time_25000h: {
    gradient: ['#f5d0fe', '#c026d3', '#a21caf', '#4a044e'],
    glow: 'radial-gradient(circle, rgba(192,38,211,0.38) 0%, transparent 70%)',
    icon: 'clock',
    label: '25K',
    name: 'Transcendent',
  },
}

export { MILESTONE_CONFIGS }

const HEX_OUTER = 'M28 4 L49 16 L49 40 L28 52 L7 40 L7 16 Z'
const HEX_INNER = 'M28 8.5 L45 18 L45 38 L28 47.5 L11 38 L11 18 Z'

export function MilestoneBadge({
  kind,
  size = 56,
  className,
}: BaseBadgeProps & {
  kind: MilestoneKind
}) {
  const cfg = MILESTONE_CONFIGS[kind]
  if (!cfg) return null

  const id = useBadgeId(`ms-${kind}`)

  return (
    <BadgeFrame size={size} className={className} glowColor={cfg.glow} glowShape="rounded-xl">
      <svg width={size} height={size} viewBox="0 0 56 56" className="overflow-visible">
        <defs>
          <linearGradient id={`${id}-fill`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={cfg.gradient[0]} />
            <stop offset="35%" stopColor={cfg.gradient[1]} />
            <stop offset="70%" stopColor={cfg.gradient[2]} />
            <stop offset="100%" stopColor={cfg.gradient[3]} />
          </linearGradient>
          <radialGradient id={`${id}-shine`} cx="34%" cy="20%" r="60%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.7)" />
            <stop offset="30%" stopColor="rgba(255,255,255,0.2)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
          <clipPath id={`${id}-clip`}>
            <path d={HEX_OUTER} />
          </clipPath>
        </defs>

        {/* Outer hex */}
        <path d={HEX_OUTER} fill={`url(#${id}-fill)`} stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
        {/* Inner hex border */}
        <path d={HEX_INNER} fill="rgba(10,10,10,0.15)" stroke="rgba(255,255,255,0.12)" strokeWidth="0.8" />
        {/* Shine */}
        <ellipse cx="22" cy="14" rx="14" ry="8" fill={`url(#${id}-shine)`} opacity="0.7" />

        {/* Glyph — shifted up to make room for label */}
        <g transform="translate(0 -4)">
          {cfg.icon === 'flame' ? <FlameGlyph /> : <TimeGlyph />}
        </g>

        {/* Label */}
        <text
          x="28"
          y="46"
          textAnchor="middle"
          fontSize="8"
          fontWeight="800"
          fill="white"
          style={{ paintOrder: 'stroke', stroke: cfg.gradient[3], strokeWidth: 1.5 }}
        >
          {cfg.label}
        </text>

        {/* Shimmer */}
        <g clipPath={`url(#${id}-clip)`}>
          <ShineSweep id={id} delay={0.8} />
        </g>
      </svg>
    </BadgeFrame>
  )
}
