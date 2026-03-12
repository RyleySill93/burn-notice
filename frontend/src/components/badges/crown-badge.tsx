import type { BaseBadgeProps, CrownKind } from './badge-types'
import { BadgeFrame, FlameGlyph, ShineSweep, useBadgeId } from './badge-primitives'

const CROWN_GLOW = {
  tokens: 'radial-gradient(circle, rgba(251,191,36,0.34) 0%, rgba(249,115,22,0.1) 45%, transparent 72%)',
  time: 'radial-gradient(circle, rgba(125,211,252,0.3) 0%, rgba(59,130,246,0.1) 45%, transparent 72%)',
} as const

export function CrownBadge({
  kind,
  size = 56,
  className,
}: BaseBadgeProps & { kind: CrownKind }) {
  const id = useBadgeId(`crown-${kind}`)

  return (
    <BadgeFrame size={size} className={className} glowColor={CROWN_GLOW[kind]}>
      <svg width={size} height={size} viewBox="0 0 56 56" className="overflow-visible">
        <defs>
          <linearGradient id={`${id}-metal`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#fff7d6" />
            <stop offset="30%" stopColor={kind === 'tokens' ? '#fbbf24' : '#93c5fd'} />
            <stop offset="68%" stopColor={kind === 'tokens' ? '#f97316' : '#2563eb'} />
            <stop offset="100%" stopColor="#4c1d95" />
          </linearGradient>
          <radialGradient id={`${id}-shine`} cx="34%" cy="20%" r="70%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.9)" />
            <stop offset="30%" stopColor="rgba(255,255,255,0.22)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
          <clipPath id={`${id}-clip`}>
            <path d="M10 39.5V23.5l7.2 5.3 10.8-15 10.8 15 7.2-5.3v16c0 2.6-1.5 4.4-4.4 5.2l-10.4 3c-2 .6-4.4.6-6.4 0l-10.4-3c-2.9-.8-4.4-2.6-4.4-5.2Z" />
          </clipPath>
        </defs>

        {/* Crown outer */}
        <path
          d="M10 39.5V23.5l7.2 5.3 10.8-15 10.8 15 7.2-5.3v16c0 2.6-1.5 4.4-4.4 5.2l-10.4 3c-2 .6-4.4.6-6.4 0l-10.4-3c-2.9-.8-4.4-2.6-4.4-5.2Z"
          fill={`url(#${id}-metal)`}
          stroke="rgba(255,255,255,0.24)"
          strokeWidth="1"
        />
        {/* Inner crown */}
        <path
          d="M13.5 38.3V27.5l4.3 3.2L28 16.8l10.2 13.9 4.3-3.2v10.8c0 1.5-.8 2.5-2.3 3l-9.3 2.7c-1.8.5-4 .5-5.8 0l-9.3-2.7c-1.5-.5-2.3-1.5-2.3-3Z"
          fill="rgba(10,10,10,0.18)"
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="0.8"
        />
        {/* Shine highlight */}
        <ellipse cx="22" cy="15.6" rx="10.5" ry="6.8" fill={`url(#${id}-shine)`} opacity="0.8" />

        {/* Crown tip jewels */}
        <circle cx="17.2" cy="22.6" r="2.2" fill="rgba(255,255,255,0.95)" />
        <circle cx="28" cy="13.4" r="2.6" fill="rgba(255,255,255,0.98)" />
        <circle cx="38.8" cy="22.6" r="2.2" fill="rgba(255,255,255,0.95)" />

        {/* Center glyph */}
        {kind === 'tokens' ? (
          <g transform="translate(0 3) scale(0.62)" style={{ transformOrigin: '28px 31px' }}>
            <FlameGlyph />
          </g>
        ) : (
          <g>
            <circle cx="28" cy="31" r="6.2" fill="none" stroke="rgba(255,255,255,0.96)" strokeWidth="2" />
            <path
              d="M28 31v-3.4M28 31l3 1.9"
              stroke="rgba(255,255,255,0.96)"
              strokeWidth="1.9"
              strokeLinecap="round"
            />
          </g>
        )}

        {/* Base line */}
        <path d="M16 40.8H40" stroke="rgba(255,255,255,0.2)" strokeWidth="1.2" strokeLinecap="round" />

        {/* Shimmer */}
        <g clipPath={`url(#${id}-clip)`}>
          <ShineSweep id={id} delay={0.4} />
        </g>
      </svg>
    </BadgeFrame>
  )
}
