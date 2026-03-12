import type { BaseBadgeProps } from './badge-types'
import { BadgeFrame, ShineSweep, useBadgeId } from './badge-primitives'

const HEART_PATH =
  'M28 38.5c-.4 0-.7-.1-1-.4C20.8 32.6 16 28.6 16 24c0-3.5 2.6-6 6-6 1.8 0 3.5.9 4.7 2.3l1.3 1.6 1.3-1.6C30.5 18.9 32.2 18 34 18c3.4 0 6 2.5 6 6 0 4.6-4.8 8.6-11 14.1-.3.3-.6.4-1 .4Z'

const GLOW = 'radial-gradient(circle, rgba(147,51,234,0.32) 0%, rgba(88,28,135,0.1) 45%, transparent 72%)'

export function PurpleHeartBadge({
  size = 56,
  className,
}: BaseBadgeProps) {
  const id = useBadgeId('ph')

  return (
    <BadgeFrame size={size} className={className} glowColor={GLOW}>
      <svg width={size} height={size} viewBox="0 0 56 56" className="overflow-visible">
        <defs>
          <radialGradient id={`${id}-face`} cx="40%" cy="30%" r="65%">
            <stop offset="0%" stopColor="#c084fc" />
            <stop offset="50%" stopColor="#7c3aed" />
            <stop offset="100%" stopColor="#3b0764" />
          </radialGradient>
          <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#d8b4fe" />
            <stop offset="100%" stopColor="#581c87" />
          </linearGradient>
          <radialGradient id={`${id}-shine`} cx="30%" cy="25%" r="40%">
            <stop offset="0%" stopColor="white" stopOpacity="0.25" />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </radialGradient>
          <clipPath id={`${id}-clip`}>
            <circle cx="28" cy="28" r="22" />
          </clipPath>
        </defs>

        {/* Outer ring */}
        <circle cx="28" cy="28" r="24" fill={`url(#${id}-ring)`} />
        {/* Face */}
        <circle cx="28" cy="28" r="21" fill={`url(#${id}-face)`} />
        {/* Shine */}
        <circle cx="28" cy="28" r="21" fill={`url(#${id}-shine)`} />
        {/* Inner bevel */}
        <circle cx="28" cy="28" r="18" fill="none" stroke="#d8b4fe" strokeWidth="0.5" strokeOpacity="0.3" />

        {/* Heart glyph */}
        <path d={HEART_PATH} fill="#e9d5ff" opacity="0.95" />

        {/* Ribbon tails */}
        <g opacity="0.85">
          <path d="M16.5 39.2L12.6 49.4 18.6 46.9 22 52 24.1 40.7Z" fill="#7c3aed" />
          <path d="M39.5 39.2L43.4 49.4 37.4 46.9 34 52 31.9 40.7Z" fill="#7c3aed" />
        </g>

        {/* Shimmer */}
        <g clipPath={`url(#${id}-clip)`}>
          <ShineSweep id={id} delay={0.3} />
        </g>
      </svg>
    </BadgeFrame>
  )
}
