import { useState } from 'react'
import { useParams, Link } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  Activity,
  BarChart3,
  ArrowLeft,
  Trophy,
  Clock,
  Heart,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from '@/lib/axios-instance'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { format, isSameDay } from 'date-fns'
import { motion } from 'framer-motion'
import { useMetricToggle, type MetricType } from '@/hooks/useMetricToggle'
import { useAuth } from '@/contexts/AuthContext'
import { hasFlameWarAccess } from '@/lib/flame-war-access'
import { LeaderboardDatePicker } from '@/components/LeaderboardDatePicker'
import { MetricToggle } from '@/components/MetricToggle'

interface PeriodStats {
  tokens: number
  tokensInput: number
  tokensOutput: number
  costUsd: number
  comparisonTokens: number
  comparisonTokensInput: number
  comparisonTokensOutput: number
  comparisonCostUsd: number
  changePercent: number | null
  // GitHub metrics
  githubCommits: number
  githubAdditions: number
  githubDeletions: number
  githubPrsMerged: number
  comparisonGithubCommits: number
  comparisonGithubAdditions: number
  comparisonGithubDeletions: number
  comparisonGithubPrsMerged: number
  // Activity metrics
  activeMinutes: number
  comparisonActiveMinutes: number
}

interface EngineerStats {
  engineerId: string
  displayName: string
  date: string
  today: PeriodStats
  thisWeek: PeriodStats
  thisMonth: PeriodStats
}

interface HistoricalRank {
  periodStart: string
  periodEnd: string
  rank: number | null
  tokens: number
  tokensInput: number
  tokensOutput: number
  costUsd: number
  // GitHub metrics
  githubCommits: number
  githubAdditions: number
  githubDeletions: number
  githubPrsMerged: number
  // Activity metrics
  activeMinutes: number
}

interface HistoricalRankingsResponse {
  engineerId: string
  periodType: string
  rankings: HistoricalRank[]
}

interface TimeSeriesDataPoint {
  timestamp: string
  tokens: number
  tokensInput: number
  tokensOutput: number
  costUsd: number
  // GitHub metrics
  githubCommits: number
  githubAdditions: number
  githubDeletions: number
  githubPrsMerged: number
  // Activity metrics
  activeMinutes: number
}

interface TimeSeriesResponse {
  engineerId: string
  period: string
  data: TimeSeriesDataPoint[]
}

interface EngineerMedalEntry {
  medalCategory: string
  medalType: string
  metricType: string
  periodType: string | null
  periodStart: string | null
  value: number
  createdAt: string
  citation: string | null
  awardedByDisplayName: string | null
}

interface EngineerCrown {
  crownType: string
  value: number
  recordDate: string
}

interface EngineerMedalsData {
  engineerId: string
  medals: EngineerMedalEntry[]
  crowns: EngineerCrown[]
  medalCounts: Record<string, number>
}

type TimeSeriesPeriod = 'hourly' | 'daily' | 'weekly' | 'monthly'

function getMetricValue(
  data: {
    tokens: number
    tokensInput: number
    tokensOutput: number
    costUsd?: number
    githubCommits?: number
    githubAdditions?: number
    githubDeletions?: number
    githubPrsMerged?: number
    activeMinutes?: number
  },
  metric: MetricType
): number {
  switch (metric) {
    case 'input':
      return data.tokensInput
    case 'output':
      return data.tokensOutput
    case 'cost':
      return data.costUsd || 0
    case 'commits':
      return data.githubCommits ?? 0
    case 'additions':
      return data.githubAdditions ?? 0
    case 'deletions':
      return data.githubDeletions ?? 0
    case 'lines':
      return (data.githubAdditions ?? 0) + (data.githubDeletions ?? 0)
    case 'prs':
      return data.githubPrsMerged ?? 0
    case 'time':
      return data.activeMinutes ?? 0
    default:
      return data.tokens
  }
}

function getComparisonValue(data: PeriodStats, metric: MetricType): number {
  switch (metric) {
    case 'input':
      return data.comparisonTokensInput
    case 'output':
      return data.comparisonTokensOutput
    case 'cost':
      return data.comparisonCostUsd || 0
    case 'commits':
      return data.comparisonGithubCommits ?? 0
    case 'additions':
      return data.comparisonGithubAdditions ?? 0
    case 'deletions':
      return data.comparisonGithubDeletions ?? 0
    case 'lines':
      return (data.comparisonGithubAdditions ?? 0) + (data.comparisonGithubDeletions ?? 0)
    case 'prs':
      return data.comparisonGithubPrsMerged ?? 0
    case 'time':
      return data.comparisonActiveMinutes ?? 0
    default:
      return data.comparisonTokens
  }
}

function calculateChangePercent(current: number, comparison: number): number | null {
  if (comparison === 0) return null
  return ((current - comparison) / comparison) * 100
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`
  }
  if (n >= 1_000) {
    return `${Math.floor(n / 1_000)}K`
  }
  return n.toString()
}

function formatCost(n: number): string {
  return `$${n.toFixed(2)}`
}

function formatMinutes(n: number): string {
  const rounded = Math.round(n)
  if (rounded >= 60) {
    const hours = Math.floor(rounded / 60)
    const mins = rounded % 60
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  }
  return `${rounded}m`
}

function formatValue(n: number, metric: MetricType): string {
  if (metric === 'cost') {
    return formatCost(n)
  }
  if (metric === 'time') {
    return formatMinutes(n)
  }
  return formatTokens(n)
}

function getMetricUnit(metric: MetricType): string {
  switch (metric) {
    case 'cost':
      return ''
    case 'time':
      return ''
    case 'commits':
      return ' commits'
    case 'additions':
    case 'deletions':
    case 'lines':
      return ' lines'
    case 'prs':
      return ' PRs'
    default:
      return ' tokens'
  }
}

function ChangeIndicator({ change, delta, metric }: { change: number | null; delta: number; metric: MetricType }) {
  if (change === null) {
    return <span className="text-sm text-muted-foreground">No prior data</span>
  }
  const deltaStr = delta >= 0 ? `+${formatValue(delta, metric)}` : `-${formatValue(Math.abs(delta), metric)}`
  if (change > 0) {
    return (
      <span className="flex items-center gap-1 text-sm text-green-600">
        <TrendingUp className="h-4 w-4" />
        {deltaStr} ({change.toFixed(0)}%)
      </span>
    )
  }
  if (change < 0) {
    return (
      <span className="flex items-center gap-1 text-sm text-red-600">
        <TrendingDown className="h-4 w-4" />
        {deltaStr} ({change.toFixed(0)}%)
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1 text-sm text-muted-foreground">
      <Minus className="h-4 w-4" />
      No change
    </span>
  )
}

function StatCard({
  title,
  value,
  comparisonValue,
  change,
  comparison,
  icon: Icon,
  metric,
}: {
  title: string
  value: number
  comparisonValue: number
  change: number | null
  comparison: string
  icon: React.ElementType
  metric: MetricType
}) {
  const delta = value - comparisonValue
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{formatValue(value, metric)}</div>
        <div className="flex items-center justify-between mt-1">
          <ChangeIndicator change={change} delta={delta} metric={metric} />
          <span className="text-xs text-muted-foreground">{comparison}</span>
        </div>
      </CardContent>
    </Card>
  )
}

// --- Skeuomorphic Medal Ribbon Bar ---

// SVG icon paths (inline, no emoji)
const BOLT_PATH = 'M13 2L3 14h9l-1 10 10-12h-9l1-10z'
const CLOCK_PATH = 'M12 2a10 10 0 100 20 10 10 0 000-20zm0 18a8 8 0 110-16 8 8 0 010 16zm.5-13H11v6l5.2 3.1.8-1.3-4.5-2.7V7z'
const CROWN_PATH = 'M2 20h20l-2-8-4 4-4-6-4 6-4-4-2 8zm3-10l1-4 4 3 2-5 2 5 4-3 1 4'
const HEART_PATH = 'M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z'
const FIRE_PATH = 'M12 23c-3.6 0-8-2.4-8-8.5C4 9.3 9.6 1 12 1c0 4 4 6 4 6s-1.2 2-1.2 3c0 1 .8 2 2.2 2 2.7 0 3-2.5 3-4 0 0 2 2.2 2 6.5 0 6.1-4.4 8.5-10 8.5z'

// Metallic color palettes for ranking medals
const MEDAL_PALETTES = {
  gold: {
    face: ['#fde047', '#f59e0b', '#d97706'],
    ring: ['#fbbf24', '#b45309', '#fbbf24'],
    shine: '#fef9c3',
    shadow: 'rgba(217, 119, 6, 0.5)',
    text: '#78350f',
  },
  silver: {
    face: ['#e2e8f0', '#94a3b8', '#64748b'],
    ring: ['#cbd5e1', '#475569', '#cbd5e1'],
    shine: '#f1f5f9',
    shadow: 'rgba(100, 116, 139, 0.5)',
    text: '#1e293b',
  },
  bronze: {
    face: ['#fdba74', '#c2410c', '#9a3412'],
    ring: ['#fb923c', '#7c2d12', '#fb923c'],
    shine: '#fed7aa',
    shadow: 'rgba(194, 65, 12, 0.5)',
    text: '#431407',
  },
} as const

type RankColor = keyof typeof MEDAL_PALETTES

// Shared shimmer keyframes (injected once via style tag)
const shimmerStyle = `
@keyframes badge-shimmer {
  0%, 40% { opacity: 0; }
  50% { opacity: 0.35; }
  60%, 100% { opacity: 0; }
}
@keyframes badge-pulse {
  0%, 100% { filter: drop-shadow(0 0 3px var(--badge-glow)); }
  50% { filter: drop-shadow(0 0 8px var(--badge-glow)); }
}
`

function ShimmerStyles() {
  return <style dangerouslySetInnerHTML={{ __html: shimmerStyle }} />
}

// --- Ranking Medal: circular coin with embossed ring, metric icon, count ---
function RankingMedalBadge({
  color,
  metricType,
  periodType,
  count,
  description,
  index,
}: {
  color: RankColor
  metricType: string
  periodType: string
  count: number
  description: string
  index: number
}) {
  const p = MEDAL_PALETTES[color]
  const isTokens = metricType === 'tokens'
  const isMonthly = periodType === 'monthly'
  const id = `rank-${color}-${metricType}-${periodType}-${index}`

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.div
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 20, delay: index * 0.05 }}
          whileHover={{ scale: 1.2, transition: { type: 'spring', stiffness: 400, damping: 12 } }}
          whileTap={{ scale: 0.9 }}
          className="relative cursor-pointer select-none"
          style={{ '--badge-glow': p.shadow } as React.CSSProperties}
        >
          <svg width="60" height="60" viewBox="0 0 60 60" className="drop-shadow-lg" style={{ animation: 'badge-pulse 3s ease-in-out infinite' }}>
            <defs>
              <radialGradient id={`${id}-face`} cx="40%" cy="35%" r="60%">
                <stop offset="0%" stopColor={p.face[0]} />
                <stop offset="60%" stopColor={p.face[1]} />
                <stop offset="100%" stopColor={p.face[2]} />
              </radialGradient>
              <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={p.ring[0]} />
                <stop offset="50%" stopColor={p.ring[1]} />
                <stop offset="100%" stopColor={p.ring[2]} />
              </linearGradient>
              <radialGradient id={`${id}-inner`} cx="35%" cy="30%" r="50%">
                <stop offset="0%" stopColor={p.shine} stopOpacity="0.4" />
                <stop offset="100%" stopColor={p.face[1]} stopOpacity="0" />
              </radialGradient>
              <clipPath id={`${id}-clip`}><circle cx="30" cy="30" r="27" /></clipPath>
            </defs>
            {/* Outer ring */}
            <circle cx="30" cy="30" r="28" fill={`url(#${id}-ring)`} />
            {/* Face */}
            <circle cx="30" cy="30" r="24" fill={`url(#${id}-face)`} />
            {/* Inner highlight */}
            <circle cx="30" cy="30" r="24" fill={`url(#${id}-inner)`} />
            {/* Inner bevel ring */}
            <circle cx="30" cy="30" r="21" fill="none" stroke={p.ring[0]} strokeWidth="0.5" strokeOpacity="0.5" />
            {/* Metric icon (small, top-right) */}
            <g transform="translate(38, 8) scale(0.55)" fill={p.text} opacity="0.7">
              <path d={isTokens ? BOLT_PATH : CLOCK_PATH} />
            </g>
            {/* Period dot: monthly = double ring at bottom */}
            {isMonthly && (
              <circle cx="30" cy="51" r="2.5" fill={p.ring[0]} stroke={p.ring[1]} strokeWidth="0.8" />
            )}
            {/* Count */}
            <text
              x="30"
              y="34"
              textAnchor="middle"
              fontFamily="Bangers, cursive"
              fontSize={count >= 10 ? '18' : '22'}
              fill={p.text}
              style={{ paintOrder: 'stroke', stroke: p.shine, strokeWidth: 1, strokeLinecap: 'round', strokeLinejoin: 'round' }}
            >
              {count}
            </text>
            {/* Shimmer overlay */}
            <line x1="15" y1="-5" x2="45" y2="65" stroke="white" strokeWidth="8" strokeOpacity="0" clipPath={`url(#${id}-clip)`} style={{ animation: 'badge-shimmer 4s ease-in-out infinite', animationDelay: `${index * 0.3}s` }} />
          </svg>
        </motion.div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-72 text-center">
        <p className="text-sm font-medium">{description}</p>
      </TooltipContent>
    </Tooltip>
  )
}

// --- Crown Badge: shield shape with crown icon ---
function CrownBadge({
  crownType,
  value,
  index,
}: {
  crownType: string
  value: number
  index: number
}) {
  const isTokens = crownType.includes('tokens')
  const isDaily = crownType.includes('daily')
  const periodLabel = isDaily ? 'Daily' : 'Weekly'
  const metricLabel = isTokens ? 'Tokens' : 'Time'
  const valueStr = isTokens ? formatTokens(value) : formatMinutes(value)
  const id = `crown-${crownType}-${index}`

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.div
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 20, delay: index * 0.05 }}
          whileHover={{ scale: 1.2, transition: { type: 'spring', stiffness: 400, damping: 12 } }}
          whileTap={{ scale: 0.9 }}
          className="relative cursor-pointer select-none"
          style={{ '--badge-glow': 'rgba(250, 204, 21, 0.6)' } as React.CSSProperties}
        >
          <svg width="60" height="60" viewBox="0 0 60 60" className="drop-shadow-lg" style={{ animation: 'badge-pulse 2.5s ease-in-out infinite' }}>
            <defs>
              <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="0.3" y2="1">
                <stop offset="0%" stopColor="#fde047" />
                <stop offset="40%" stopColor="#f59e0b" />
                <stop offset="100%" stopColor="#b45309" />
              </linearGradient>
              <radialGradient id={`${id}-shine`} cx="35%" cy="25%" r="50%">
                <stop offset="0%" stopColor="#fef9c3" stopOpacity="0.5" />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
              </radialGradient>
              <clipPath id={`${id}-clip`}>
                <path d="M30 2 L55 15 L55 40 Q55 55 30 58 Q5 55 5 40 L5 15 Z" />
              </clipPath>
            </defs>
            {/* Shield shape */}
            <path d="M30 2 L55 15 L55 40 Q55 55 30 58 Q5 55 5 40 L5 15 Z" fill={`url(#${id}-bg)`} stroke="#b45309" strokeWidth="1.5" />
            <path d="M30 2 L55 15 L55 40 Q55 55 30 58 Q5 55 5 40 L5 15 Z" fill={`url(#${id}-shine)`} />
            {/* Inner border */}
            <path d="M30 6 L51 17 L51 39 Q51 51 30 54 Q9 51 9 39 L9 17 Z" fill="none" stroke="#fde047" strokeWidth="0.5" strokeOpacity="0.4" />
            {/* Crown icon */}
            <g transform="translate(17, 14) scale(1.1)" fill="#78350f" opacity="0.8">
              <path d={CROWN_PATH} />
            </g>
            {/* Label */}
            <text x="30" y="46" textAnchor="middle" fontFamily="Bangers, cursive" fontSize="7" fill="#78350f" letterSpacing="0.5">
              {periodLabel.toUpperCase()}
            </text>
            {/* Metric icon (tiny, bottom corner) */}
            <g transform="translate(40, 36) scale(0.4)" fill="#78350f" opacity="0.6">
              <path d={isTokens ? BOLT_PATH : CLOCK_PATH} />
            </g>
            {/* Shimmer */}
            <line x1="15" y1="-5" x2="45" y2="65" stroke="white" strokeWidth="8" strokeOpacity="0" clipPath={`url(#${id}-clip)`} style={{ animation: 'badge-shimmer 3.5s ease-in-out infinite', animationDelay: `${index * 0.2}s` }} />
          </svg>
        </motion.div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-72 text-center">
        <p className="text-sm font-medium">Company Record — {periodLabel} {metricLabel} ({valueStr})</p>
      </TooltipContent>
    </Tooltip>
  )
}

// --- Milestone Badge: circular badge with unique gradient per tier + icon ---
const MILESTONE_CONFIGS: Record<string, {
  colors: [string, string, string]
  ring: [string, string]
  icon: string
  label: string
  name: string
  glow: string
  descFn: (d: string) => string
}> = {
  // --- Token milestones (escalating warm → hot → cosmic) ---
  token_1m: {
    colors: ['#fde68a', '#f59e0b', '#b45309'],
    ring: ['#fef3c7', '#92400e'],
    icon: BOLT_PATH,
    label: '1M',
    name: 'Spark',
    glow: 'rgba(245, 158, 11, 0.4)',
    descFn: (d) => `Spark — Burned 1 million tokens — ${d}`,
  },
  token_10m: {
    colors: ['#fb923c', '#ea580c', '#9a3412'],
    ring: ['#fdba74', '#7c2d12'],
    icon: BOLT_PATH,
    label: '10M',
    name: 'Ember',
    glow: 'rgba(234, 88, 12, 0.5)',
    descFn: (d) => `Ember — Burned 10 million tokens — ${d}`,
  },
  token_50m: {
    colors: ['#f97316', '#dc2626', '#991b1b'],
    ring: ['#fb923c', '#7f1d1d'],
    icon: FIRE_PATH,
    label: '50M',
    name: 'Blaze',
    glow: 'rgba(220, 38, 38, 0.5)',
    descFn: (d) => `Blaze — Burned 50 million tokens — ${d}`,
  },
  token_100m: {
    colors: ['#f87171', '#dc2626', '#7f1d1d'],
    ring: ['#fca5a5', '#991b1b'],
    icon: FIRE_PATH,
    label: '100M',
    name: 'Inferno',
    glow: 'rgba(220, 38, 38, 0.6)',
    descFn: (d) => `Inferno — Burned 100 million tokens — ${d}`,
  },
  token_250m: {
    colors: ['#fb7185', '#e11d48', '#881337'],
    ring: ['#fda4af', '#9f1239'],
    icon: FIRE_PATH,
    label: '250M',
    name: 'Firestorm',
    glow: 'rgba(225, 29, 72, 0.6)',
    descFn: (d) => `Firestorm — Burned 250 million tokens — ${d}`,
  },
  token_500m: {
    colors: ['#f472b6', '#db2777', '#831843'],
    ring: ['#f9a8d4', '#9d174d'],
    icon: FIRE_PATH,
    label: '500M',
    name: 'Supernova',
    glow: 'rgba(219, 39, 119, 0.6)',
    descFn: (d) => `Supernova — Burned 500 million tokens — ${d}`,
  },
  token_1b: {
    colors: ['#c084fc', '#7c3aed', '#3b0764'],
    ring: ['#d8b4fe', '#581c87'],
    icon: FIRE_PATH,
    label: '1B',
    name: 'Solar Flare',
    glow: 'rgba(124, 58, 237, 0.7)',
    descFn: (d) => `Solar Flare — Burned ONE BILLION tokens — ${d}`,
  },
  token_10b: {
    colors: ['#e879f9', '#a21caf', '#3b0764'],
    ring: ['#f0abfc', '#581c87'],
    icon: FIRE_PATH,
    label: '10B',
    name: 'Big Bang',
    glow: 'rgba(162, 28, 175, 0.8)',
    descFn: (d) => `Big Bang — Burned TEN BILLION tokens — ${d}`,
  },
  // --- Time milestones (escalating cool → deep → cosmic) ---
  time_10h: {
    colors: ['#a5f3fc', '#06b6d4', '#0e7490'],
    ring: ['#cffafe', '#155e75'],
    icon: CLOCK_PATH,
    label: '10h',
    name: 'Clocked In',
    glow: 'rgba(6, 182, 212, 0.4)',
    descFn: (d) => `Clocked In — 10 hours of active coding time — ${d}`,
  },
  time_100h: {
    colors: ['#22d3ee', '#0891b2', '#164e63'],
    ring: ['#67e8f9', '#155e75'],
    icon: CLOCK_PATH,
    label: '100h',
    name: 'Grinder',
    glow: 'rgba(8, 145, 178, 0.5)',
    descFn: (d) => `Grinder — 100 hours of active coding time — ${d}`,
  },
  time_500h: {
    colors: ['#38bdf8', '#0284c7', '#0c4a6e'],
    ring: ['#7dd3fc', '#075985'],
    icon: CLOCK_PATH,
    label: '500h',
    name: 'Marathoner',
    glow: 'rgba(2, 132, 199, 0.5)',
    descFn: (d) => `Marathoner — 500 hours of active coding time — ${d}`,
  },
  time_1000h: {
    colors: ['#818cf8', '#4338ca', '#1e1b4b'],
    ring: ['#a5b4fc', '#312e81'],
    icon: CLOCK_PATH,
    label: '1Kh',
    name: 'Ironman',
    glow: 'rgba(67, 56, 202, 0.5)',
    descFn: (d) => `Ironman — 1,000 hours of active coding time — ${d}`,
  },
  time_2500h: {
    colors: ['#a78bfa', '#6d28d9', '#2e1065'],
    ring: ['#c4b5fd', '#4c1d95'],
    icon: CLOCK_PATH,
    label: '2.5K',
    name: 'Centurion',
    glow: 'rgba(109, 40, 217, 0.6)',
    descFn: (d) => `Centurion — 2,500 hours of active coding time — ${d}`,
  },
  time_5000h: {
    colors: ['#c084fc', '#9333ea', '#3b0764'],
    ring: ['#d8b4fe', '#581c87'],
    icon: CLOCK_PATH,
    label: '5Kh',
    name: 'Titan',
    glow: 'rgba(147, 51, 234, 0.6)',
    descFn: (d) => `Titan — 5,000 hours of active coding time — ${d}`,
  },
  time_10000h: {
    colors: ['#e879f9', '#a21caf', '#4a044e'],
    ring: ['#f0abfc', '#701a75'],
    icon: CLOCK_PATH,
    label: '10K',
    name: 'Eternal',
    glow: 'rgba(162, 28, 175, 0.7)',
    descFn: (d) => `Eternal — 10,000 hours of active coding time — ${d}`,
  },
  time_25000h: {
    colors: ['#f0abfc', '#c026d3', '#4a044e'],
    ring: ['#f5d0fe', '#86198f'],
    icon: CLOCK_PATH,
    label: '25K',
    name: 'Transcendent',
    glow: 'rgba(192, 38, 211, 0.8)',
    descFn: (d) => `Transcendent — 25,000 hours — You have ascended — ${d}`,
  },
}

function MilestoneBadge({
  medalType,
  createdAt,
  index,
}: {
  medalType: string
  createdAt: string
  index: number
}) {
  const dateStr = format(new Date(createdAt), 'MMM d, yyyy')
  const cfg = MILESTONE_CONFIGS[medalType]
  if (!cfg) return null
  const id = `ms-${medalType}-${index}`

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.div
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 20, delay: index * 0.05 }}
          whileHover={{ scale: 1.2, transition: { type: 'spring', stiffness: 400, damping: 12 } }}
          whileTap={{ scale: 0.9 }}
          className="relative cursor-pointer select-none"
          style={{ '--badge-glow': cfg.glow } as React.CSSProperties}
        >
          <svg width="60" height="60" viewBox="0 0 60 60" className="drop-shadow-lg" style={{ animation: 'badge-pulse 3s ease-in-out infinite', animationDelay: `${index * 0.4}s` }}>
            <defs>
              <radialGradient id={`${id}-face`} cx="40%" cy="30%" r="65%">
                <stop offset="0%" stopColor={cfg.colors[0]} />
                <stop offset="60%" stopColor={cfg.colors[1]} />
                <stop offset="100%" stopColor={cfg.colors[2]} />
              </radialGradient>
              <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={cfg.ring[0]} />
                <stop offset="100%" stopColor={cfg.ring[1]} />
              </linearGradient>
              <radialGradient id={`${id}-shine`} cx="30%" cy="25%" r="40%">
                <stop offset="0%" stopColor="white" stopOpacity="0.3" />
                <stop offset="100%" stopColor="white" stopOpacity="0" />
              </radialGradient>
              <clipPath id={`${id}-clip`}><circle cx="30" cy="30" r="27" /></clipPath>
            </defs>
            {/* Outer ring */}
            <circle cx="30" cy="30" r="28" fill={`url(#${id}-ring)`} />
            {/* Face */}
            <circle cx="30" cy="30" r="24" fill={`url(#${id}-face)`} />
            <circle cx="30" cy="30" r="24" fill={`url(#${id}-shine)`} />
            {/* Inner bevel */}
            <circle cx="30" cy="30" r="21" fill="none" stroke={cfg.ring[0]} strokeWidth="0.5" strokeOpacity="0.3" />
            {/* Icon */}
            <g transform="translate(18, 14) scale(1)" fill="white" opacity="0.9">
              <path d={cfg.icon} />
            </g>
            {/* Label */}
            <text x="30" y="48" textAnchor="middle" fontFamily="Bangers, cursive" fontSize="10" fill="white" style={{ paintOrder: 'stroke', stroke: cfg.colors[2], strokeWidth: 1.5 }}>
              {cfg.label}
            </text>
            {/* Shimmer */}
            <line x1="15" y1="-5" x2="45" y2="65" stroke="white" strokeWidth="8" strokeOpacity="0" clipPath={`url(#${id}-clip)`} style={{ animation: 'badge-shimmer 5s ease-in-out infinite', animationDelay: `${index * 0.5}s` }} />
          </svg>
        </motion.div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-72 text-center">
        <p className="text-sm font-medium">{cfg.descFn(dateStr)}</p>
      </TooltipContent>
    </Tooltip>
  )
}

// --- Purple Heart Badge ---
function PurpleHeartBadge({
  citation,
  awardedBy,
  createdAt,
  index,
}: {
  citation: string | null
  awardedBy: string | null
  createdAt: string
  index: number
}) {
  const dateStr = format(new Date(createdAt), 'MMM d, yyyy')
  const id = `ph-${index}`

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.div
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 500, damping: 20, delay: index * 0.05 }}
          whileHover={{ scale: 1.2, transition: { type: 'spring', stiffness: 400, damping: 12 } }}
          whileTap={{ scale: 0.9 }}
          className="relative cursor-pointer select-none"
          style={{ '--badge-glow': 'rgba(147, 51, 234, 0.6)' } as React.CSSProperties}
        >
          <svg width="60" height="60" viewBox="0 0 60 60" className="drop-shadow-lg" style={{ animation: 'badge-pulse 3s ease-in-out infinite', animationDelay: `${index * 0.3}s` }}>
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
              <clipPath id={`${id}-clip`}><circle cx="30" cy="30" r="27" /></clipPath>
            </defs>
            <circle cx="30" cy="30" r="28" fill={`url(#${id}-ring)`} />
            <circle cx="30" cy="30" r="24" fill={`url(#${id}-face)`} />
            <circle cx="30" cy="30" r="24" fill={`url(#${id}-shine)`} />
            <circle cx="30" cy="30" r="21" fill="none" stroke="#d8b4fe" strokeWidth="0.5" strokeOpacity="0.3" />
            {/* Heart */}
            <g transform="translate(17.5, 16) scale(1.05)" fill="#e9d5ff" opacity="0.95">
              <path d={HEART_PATH} />
            </g>
            {/* Shimmer */}
            <line x1="15" y1="-5" x2="45" y2="65" stroke="white" strokeWidth="8" strokeOpacity="0" clipPath={`url(#${id}-clip)`} style={{ animation: 'badge-shimmer 4.5s ease-in-out infinite', animationDelay: `${index * 0.3}s` }} />
          </svg>
        </motion.div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-72 text-center">
        <p className="text-sm font-medium">Purple Heart — Awarded {dateStr}</p>
        {citation && (
          <p className="text-xs italic text-muted-foreground mt-1">"{citation}"</p>
        )}
        {awardedBy && (
          <p className="text-[10px] text-muted-foreground mt-0.5">— awarded by {awardedBy}</p>
        )}
      </TooltipContent>
    </Tooltip>
  )
}

// --- Ribbon: composes all badge types ---

interface RankingGroup {
  color: RankColor
  metricType: string
  periodType: string
  count: number
  description: string
}

function MedalsRibbon({ medalsData }: { medalsData: EngineerMedalsData }) {
  const { crowns, medals } = medalsData

  // Group ranking medals by (medalType, metricType, periodType) → count
  const rankingMedals = medals.filter((m) => m.medalCategory === 'ranking')
  const groupKey = (m: EngineerMedalEntry) => `${m.medalType}|${m.metricType}|${m.periodType}`
  const groupMap = new Map<string, EngineerMedalEntry[]>()
  for (const m of rankingMedals) {
    const key = groupKey(m)
    if (!groupMap.has(key)) groupMap.set(key, [])
    groupMap.get(key)!.push(m)
  }

  const rankOrder: Record<string, number> = { gold: 0, silver: 1, bronze: 2 }
  const metricOrder: Record<string, number> = { tokens: 0, time: 1 }
  const periodOrder: Record<string, number> = { weekly: 0, monthly: 1 }

  const rankingGroups: RankingGroup[] = Array.from(groupMap.entries())
    .map(([, group]) => {
      const first = group[0]
      const isTokens = first.metricType === 'tokens'
      const periodLabel = first.periodType === 'weekly' ? 'Weekly' : 'Monthly'
      const metricLabel = isTokens ? 'Tokens' : 'Time'
      const rankLabel = first.medalType === 'gold' ? '1st' : first.medalType === 'silver' ? '2nd' : '3rd'
      return {
        color: first.medalType as RankColor,
        metricType: first.metricType,
        periodType: first.periodType ?? 'weekly',
        count: group.length,
        description: `${rankLabel} Place ${periodLabel} ${metricLabel} — Won ${group.length}×`,
      }
    })
    .sort((a, b) => {
      const r = (rankOrder[a.color] ?? 9) - (rankOrder[b.color] ?? 9)
      if (r !== 0) return r
      const m = (metricOrder[a.metricType] ?? 9) - (metricOrder[b.metricType] ?? 9)
      if (m !== 0) return m
      return (periodOrder[a.periodType] ?? 9) - (periodOrder[b.periodType] ?? 9)
    })

  const actionMedals = medals.filter((m) => m.medalCategory === 'action')
  const milestoneMedals = medals.filter((m) => m.medalCategory === 'milestone')

  const totalBadges = crowns.length + rankingGroups.length + actionMedals.length + milestoneMedals.length
  if (totalBadges === 0) return null

  let badgeIndex = 0

  return (
    <>
      <ShimmerStyles />
      <div className="flex flex-wrap gap-2 items-center">
        {crowns.map((crown) => (
          <CrownBadge
            key={`crown-${crown.crownType}`}
            crownType={crown.crownType}
            value={crown.value}
            index={badgeIndex++}
          />
        ))}
        {rankingGroups.map((g) => (
          <RankingMedalBadge
            key={`rank-${g.color}-${g.metricType}-${g.periodType}`}
            color={g.color}
            metricType={g.metricType}
            periodType={g.periodType}
            count={g.count}
            description={g.description}
            index={badgeIndex++}
          />
        ))}
        {actionMedals.map((m, i) => (
          <PurpleHeartBadge
            key={`action-${i}`}
            citation={m.citation}
            awardedBy={m.awardedByDisplayName}
            createdAt={m.createdAt}
            index={badgeIndex++}
          />
        ))}
        {milestoneMedals.map((m, i) => (
          <MilestoneBadge
            key={`ms-${m.medalType}-${i}`}
            medalType={m.medalType}
            createdAt={m.createdAt}
            index={badgeIndex++}
          />
        ))}
      </div>
    </>
  )
}

function AwardMedalButton({ engineerId }: { engineerId: string }) {
  const [open, setOpen] = useState(false)
  const [citation, setCitation] = useState('')
  const [isAwarding, setIsAwarding] = useState(false)
  const queryClient = useQueryClient()

  const handleAward = async () => {
    if (!citation.trim()) return
    setIsAwarding(true)
    try {
      await axios.post('/api/leaderboard/medals/award', {
        engineer_id: engineerId,
        medal_type: 'purple_heart',
        citation: citation.trim(),
      })
      queryClient.invalidateQueries({ queryKey: ['engineer-medals', engineerId] })
      setCitation('')
      setOpen(false)
    } finally {
      setIsAwarding(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className={cn(
            'flex flex-col items-center justify-center',
            'w-14 h-14 rounded-2xl border-2 border-dashed cursor-pointer select-none',
            'border-purple-400/40 hover:border-purple-400/80',
            'bg-purple-500/5 hover:bg-purple-500/10',
            'transition-colors duration-200',
          )}
        >
          <Heart className="h-4 w-4 text-purple-400" />
          <span className="text-[7px] font-bold text-purple-400 mt-0.5">Award</span>
        </motion.button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="text-2xl">💜</span>
            Award Purple Heart
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <Label className="text-sm font-medium">Citation</Label>
            <Textarea
              value={citation}
              onChange={(e) => setCitation(e.target.value)}
              placeholder="For extraordinary valor in the face of impossible deadlines..."
              className="mt-1.5 min-h-[100px]"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Describe the heroic act that earned this medal.
            </p>
          </div>
          <Button
            onClick={handleAward}
            disabled={!citation.trim() || isAwarding}
            className="w-full bg-purple-600 hover:bg-purple-700"
          >
            {isAwarding ? 'Awarding...' : 'Award Purple Heart'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function RankBadge({ rank }: { rank: number | null }) {
  if (rank === null) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        —
      </Badge>
    )
  }
  return (
    <Badge
      variant="outline"
      className={cn(
        rank === 1 && 'bg-amber-50 text-amber-700 border-amber-200',
        rank === 2 && 'bg-gray-50 text-gray-700 border-gray-200',
        rank === 3 && 'bg-orange-50 text-orange-700 border-orange-200',
        rank > 3 && 'text-muted-foreground'
      )}
    >
      #{rank}
    </Badge>
  )
}

function formatPeriodLabel(periodStart: string, periodEnd: string, periodType: string): string {
  const start = new Date(periodStart)
  const end = new Date(periodEnd)

  if (periodType === 'daily') {
    return format(start, 'MMM d')
  }
  if (periodType === 'weekly') {
    return `${format(start, 'MMM d')} - ${format(end, 'MMM d')}`
  }
  // monthly
  return format(start, 'MMM yyyy')
}

function HistoricalRankingsTable({
  rankings,
  periodType,
  metric,
}: {
  rankings: HistoricalRank[]
  periodType: string
  metric: MetricType
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const INITIAL_COUNT = 5

  if (rankings.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Trophy className="h-8 w-8 mx-auto mb-2 opacity-20" />
        <p className="text-sm">No ranking history</p>
      </div>
    )
  }

  const displayedRankings = isExpanded ? rankings : rankings.slice(0, INITIAL_COUNT)
  const hasMore = rankings.length > INITIAL_COUNT

  return (
    <div className="space-y-1.5">
      {displayedRankings.map((entry, index) => (
        <div
          key={index}
          className={cn(
            'flex items-center justify-between p-2.5 rounded-lg border',
            entry.rank === 1 && 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200',
            entry.rank === 2 && 'bg-gradient-to-r from-gray-50 to-slate-50 border-gray-200',
            entry.rank === 3 && 'bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200',
            (entry.rank === null || entry.rank > 3) && 'bg-card'
          )}
        >
          <div className="flex items-center gap-3">
            <RankBadge rank={entry.rank} />
            <div>
              <p className={cn(
                'font-medium text-sm',
                entry.rank !== null && entry.rank <= 3 && 'text-gray-900'
              )}>
                {formatPeriodLabel(entry.periodStart, entry.periodEnd, periodType)}
              </p>
              <p className={cn(
                'text-xs',
                entry.rank !== null && entry.rank <= 3 ? 'text-gray-600' : 'text-muted-foreground'
              )}>{formatValue(getMetricValue(entry, metric), metric)}{getMetricUnit(metric)}</p>
            </div>
          </div>
        </div>
      ))}
      {hasMore && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full text-center text-sm text-muted-foreground hover:text-foreground py-2 transition-colors"
        >
          {isExpanded ? 'Show less' : `Show more (${rankings.length - INITIAL_COUNT} more)`}
        </button>
      )}
    </div>
  )
}

type RankingsPeriod = 'daily' | 'weekly' | 'monthly'

export function EngineerPage() {
  const { engineerId } = useParams<{ engineerId: string }>()
  const { user } = useAuth()
  const showFlameWar = hasFlameWarAccess(user?.id)
  const [rankingsPeriod, setRankingsPeriod] = useState<RankingsPeriod>('daily')
  const [rankingsDate, setRankingsDate] = useState<Date>(new Date())
  const [timeSeriesPeriod, setTimeSeriesPeriod] = useState<TimeSeriesPeriod>('hourly')
  const [timeSeriesDate, setTimeSeriesDate] = useState<Date>(new Date())
  const [isCumulative, setIsCumulative] = useState(false)
  const { metric, setMetric } = useMetricToggle()

  const rankingsIsToday = isSameDay(rankingsDate, new Date())
  const timeSeriesIsToday = isSameDay(timeSeriesDate, new Date())

  const { data: stats, isLoading: statsLoading } = useQuery<EngineerStats>({
    queryKey: ['engineer-stats', engineerId],
    queryFn: async () => {
      const response = await axios.get<EngineerStats>(`/api/leaderboard/engineers/${engineerId}/stats`)
      return response.data
    },
    enabled: !!engineerId,
    refetchInterval: 10_000,
  })

  const { data: rankings, isLoading: rankingsLoading } = useQuery<HistoricalRankingsResponse>({
    queryKey: ['engineer-rankings', engineerId, rankingsPeriod, format(rankingsDate, 'yyyy-MM-dd')],
    queryFn: async () => {
      const response = await axios.get<HistoricalRankingsResponse>(
        `/api/leaderboard/engineers/${engineerId}/historical-rankings`,
        {
          params: {
            period_type: rankingsPeriod,
            num_periods: 20,
            as_of: format(rankingsDate, 'yyyy-MM-dd'),
          },
        }
      )
      return response.data
    },
    enabled: !!engineerId,
    refetchInterval: rankingsIsToday ? 10_000 : false,
  })

  const { data: timeSeries, isLoading: timeSeriesLoading } = useQuery<TimeSeriesResponse>({
    queryKey: ['engineer-time-series', engineerId, timeSeriesPeriod, format(timeSeriesDate, 'yyyy-MM-dd')],
    queryFn: async () => {
      const response = await axios.get<TimeSeriesResponse>(
        `/api/leaderboard/engineers/${engineerId}/time-series`,
        {
          params: {
            period: timeSeriesPeriod,
            as_of: format(timeSeriesDate, 'yyyy-MM-dd'),
          },
        }
      )
      return response.data
    },
    enabled: !!engineerId,
    // Poll for live data when viewing today's data
    refetchInterval: timeSeriesIsToday ? 10_000 : false,
  })

  const { data: medalsData } = useQuery<EngineerMedalsData>({
    queryKey: ['engineer-medals', engineerId],
    queryFn: async () => {
      const response = await axios.get<EngineerMedalsData>(`/api/leaderboard/engineers/${engineerId}/medals`)
      return response.data
    },
    enabled: !!engineerId && showFlameWar,
  })

  // Build time series chart data
  const timeSeriesChartData = (() => {
    if (!timeSeries) return []
    let cumulative = 0

    const allData = timeSeries.data.map((t) => {
      const value = getMetricValue(t, metric)
      cumulative += value

      // Format label based on period
      let label: string
      const timestamp = new Date(t.timestamp)
      if (timeSeriesPeriod === 'hourly') {
        label = format(timestamp, 'h:mm a')
      } else if (timeSeriesPeriod === 'daily') {
        label = format(timestamp, 'MMM d')
      } else if (timeSeriesPeriod === 'weekly') {
        label = format(timestamp, 'MMM d')
      } else {
        // monthly
        label = format(timestamp, 'MMM yyyy')
      }

      return {
        label,
        value: isCumulative ? cumulative : value,
        // Include input/output for stacked bar charts
        tokensInput: t.tokensInput,
        tokensOutput: t.tokensOutput,
      }
    })

    // Filter out leading zeros (only for hourly view)
    if (timeSeriesPeriod === 'hourly') {
      const firstNonZeroIndex = allData.findIndex(d => d.value > 0)
      if (firstNonZeroIndex > 0) {
        return allData.slice(firstNonZeroIndex)
      }
    }
    return allData
  })()

  // Only block page render on initial stats load
  if (statsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  const todayTokens = stats ? getMetricValue(stats.today, metric) : 0
  const todayComparison = stats ? getComparisonValue(stats.today, metric) : 0
  const weekTokens = stats ? getMetricValue(stats.thisWeek, metric) : 0
  const weekComparison = stats ? getComparisonValue(stats.thisWeek, metric) : 0
  const monthTokens = stats ? getMetricValue(stats.thisMonth, metric) : 0
  const monthComparison = stats ? getComparisonValue(stats.thisMonth, metric) : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/dashboard">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{stats?.displayName}</h1>
            <p className="text-muted-foreground text-sm">Individual token usage</p>
          </div>
        </div>
        <MetricToggle metric={metric} setMetric={setMetric} />
      </div>

      {/* Medals Ribbon (Flame War users only) */}
      {showFlameWar && (
        <div className="flex flex-wrap gap-2 items-center">
          {medalsData && (medalsData.crowns.length > 0 || medalsData.medals.length > 0) && (
            <MedalsRibbon medalsData={medalsData} />
          )}
          {engineerId && <AwardMedalButton engineerId={engineerId} />}
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Today"
          value={todayTokens}
          comparisonValue={todayComparison}
          change={calculateChangePercent(todayTokens, todayComparison)}
          comparison="vs yesterday at this point"
          icon={Zap}
          metric={metric}
        />
        <StatCard
          title="This Week"
          value={weekTokens}
          comparisonValue={weekComparison}
          change={calculateChangePercent(weekTokens, weekComparison)}
          comparison="vs last week at this point"
          icon={Activity}
          metric={metric}
        />
        <StatCard
          title="This Month"
          value={monthTokens}
          comparisonValue={monthComparison}
          change={calculateChangePercent(monthTokens, monthComparison)}
          comparison="vs last month at this point"
          icon={BarChart3}
          metric={metric}
        />
      </div>

      {/* Time Series Chart and Historical Rankings */}
      <div className="grid gap-6 lg:grid-cols-2 items-start">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">
            {metric === 'cost' ? 'Cost Over Time' : metric === 'time' ? 'Time Burned' : 'Token Usage Over Time'}
            {isCumulative && ' (Cumulative)'}
          </CardTitle>
          <div className="flex items-center gap-4">
            {/* Cumulative Toggle */}
            <div className="flex items-center gap-2">
              <Switch
                id="cumulative"
                checked={isCumulative}
                onCheckedChange={setIsCumulative}
              />
              <Label htmlFor="cumulative" className="text-xs">Cumulative</Label>
            </div>
            <LeaderboardDatePicker
              activeTab={timeSeriesPeriod === 'daily' || timeSeriesPeriod === 'hourly' ? 'today' : timeSeriesPeriod}
              selectedDate={timeSeriesDate}
              onDateChange={setTimeSeriesDate}
            />
          </div>
        </CardHeader>
        <CardContent>
          {/* Period Tabs */}
          <Tabs value={timeSeriesPeriod} onValueChange={(v) => setTimeSeriesPeriod(v as TimeSeriesPeriod)} className="w-full mb-4">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="hourly" className="text-xs">Hourly</TabsTrigger>
              <TabsTrigger value="daily" className="text-xs">Daily</TabsTrigger>
              <TabsTrigger value="weekly" className="text-xs">Weekly</TabsTrigger>
              <TabsTrigger value="monthly" className="text-xs">Monthly</TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="h-[200px]">
            {timeSeriesLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
              </div>
            ) : timeSeriesChartData.length === 0 || timeSeriesChartData.every(d => d.value === 0) ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                <BarChart3 className="h-12 w-12 mb-2 opacity-20" />
                <p>No data for this period</p>
              </div>
            ) : timeSeriesPeriod === 'hourly' ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeSeriesChartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="label"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    interval={11}
                  />
                  <YAxis
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => formatValue(value, metric)}
                  />
                  <RechartsTooltip
                    formatter={(value: number) => [
                      formatValue(value, metric),
                      metric === 'cost'
                        ? (isCumulative ? 'Cumulative Cost' : 'Cost')
                        : metric === 'time'
                          ? (isCumulative ? 'Cumulative Time' : 'Time Burned')
                          : (isCumulative ? 'Cumulative Tokens' : 'Tokens')
                    ]}
                    labelStyle={{ fontWeight: 'bold', color: '#111827' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#f97316"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={timeSeriesChartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="label"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    interval={timeSeriesPeriod === 'monthly' ? 0 : 'preserveStartEnd'}
                  />
                  <YAxis
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => formatValue(value, metric)}
                  />
                  <RechartsTooltip
                    formatter={(value: number, name: string) => {
                      const label = name === 'tokensInput' ? 'Input' : name === 'tokensOutput' ? 'Output' : metric === 'cost' ? 'Cost' : 'Tokens'
                      return [formatValue(value, metric), label]
                    }}
                    labelStyle={{ fontWeight: 'bold', color: '#111827' }}
                  />
                  {metric === 'cost' || metric === 'time' || isCumulative ? (
                    <Bar dataKey="value" fill="#f97316" radius={[4, 4, 0, 0]} />
                  ) : (
                    <>
                      <Legend />
                      <Bar dataKey="tokensInput" stackId="tokens" fill="#3b82f6" name="Input" />
                      <Bar dataKey="tokensOutput" stackId="tokens" fill="#f97316" name="Output" radius={[4, 4, 0, 0]} />
                    </>
                  )}
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Historical Rankings */}
      <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" />
              Ranking History
            </CardTitle>
            <LeaderboardDatePicker
              activeTab={rankingsPeriod === 'daily' ? 'today' : rankingsPeriod === 'weekly' ? 'weekly' : 'monthly'}
              selectedDate={rankingsDate}
              onDateChange={setRankingsDate}
            />
          </CardHeader>
          <CardContent>
            <Tabs value={rankingsPeriod} onValueChange={(v) => setRankingsPeriod(v as RankingsPeriod)} className="w-full">
              <TabsList className="grid w-full grid-cols-3 mb-4">
                <TabsTrigger value="daily" className="text-xs">
                  Daily
                </TabsTrigger>
                <TabsTrigger value="weekly" className="text-xs">
                  Weekly
                </TabsTrigger>
                <TabsTrigger value="monthly" className="text-xs">
                  Monthly
                </TabsTrigger>
              </TabsList>
              {rankingsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                </div>
              ) : (
                <>
                  <TabsContent value="daily">
                    <HistoricalRankingsTable
                      rankings={rankings?.rankings || []}
                      periodType="daily"
                      metric={metric}
                    />
                  </TabsContent>
                  <TabsContent value="weekly">
                    <HistoricalRankingsTable
                      rankings={rankings?.rankings || []}
                      periodType="weekly"
                      metric={metric}
                    />
                  </TabsContent>
                  <TabsContent value="monthly">
                    <HistoricalRankingsTable
                      rankings={rankings?.rankings || []}
                      periodType="monthly"
                      metric={metric}
                    />
                  </TabsContent>
                </>
              )}
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
