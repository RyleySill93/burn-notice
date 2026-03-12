import { useState } from 'react'
import { useParams, Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  Activity,
  BarChart3,
  ArrowLeft,
  Trophy,
  Crown,
  Medal,
  Award,
  Clock,
  Star,
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

// --- Medal Ribbon Bar (Apple Fitness / Military Ribbon style) ---

interface MedalBadgeConfig {
  emoji: string
  label: string
  description: string
  bg: string
  border: string
  glow: string
  textColor: string
}

function getRankingBadgeConfig(medal: EngineerMedalEntry): MedalBadgeConfig {
  const isTokens = medal.metricType === 'tokens'
  const metricEmoji = isTokens ? '⚡' : '⏱️'
  const periodLabel = medal.periodType === 'weekly' ? 'Weekly' : 'Monthly'
  const metricLabel = isTokens ? 'Tokens' : 'Time'
  const valueStr = isTokens ? formatTokens(medal.value) : formatMinutes(medal.value)
  const dateStr = medal.periodStart ? format(new Date(medal.periodStart), 'MMM d, yyyy') : ''

  if (medal.medalType === 'gold') {
    return {
      emoji: `🥇${metricEmoji}`,
      label: `${periodLabel} Gold`,
      description: `1st Place — ${periodLabel} ${metricLabel} (${valueStr}) — ${dateStr}`,
      bg: 'bg-gradient-to-br from-yellow-300 via-amber-400 to-yellow-500',
      border: 'border-yellow-500/50',
      glow: 'shadow-yellow-400/40',
      textColor: 'text-yellow-950',
    }
  }
  if (medal.medalType === 'silver') {
    return {
      emoji: `🥈${metricEmoji}`,
      label: `${periodLabel} Silver`,
      description: `2nd Place — ${periodLabel} ${metricLabel} (${valueStr}) — ${dateStr}`,
      bg: 'bg-gradient-to-br from-gray-200 via-slate-300 to-gray-400',
      border: 'border-gray-400/50',
      glow: 'shadow-gray-300/40',
      textColor: 'text-gray-900',
    }
  }
  // bronze
  return {
    emoji: `🥉${metricEmoji}`,
    label: `${periodLabel} Bronze`,
    description: `3rd Place — ${periodLabel} ${metricLabel} (${valueStr}) — ${dateStr}`,
    bg: 'bg-gradient-to-br from-orange-300 via-amber-600 to-orange-700',
    border: 'border-orange-600/50',
    glow: 'shadow-orange-400/40',
    textColor: 'text-orange-950',
  }
}

function getMilestoneBadgeConfig(medal: EngineerMedalEntry): MedalBadgeConfig {
  const dateStr = format(new Date(medal.createdAt), 'MMM d, yyyy')
  const configs: Record<string, MedalBadgeConfig> = {
    token_10m: {
      emoji: '⚡',
      label: '10M Tokens',
      description: `Burned 10 million tokens — ${dateStr}`,
      bg: 'bg-gradient-to-br from-orange-400 via-red-500 to-orange-600',
      border: 'border-orange-500/50',
      glow: 'shadow-orange-400/40',
      textColor: 'text-white',
    },
    token_100m: {
      emoji: '🔥',
      label: '100M Tokens',
      description: `Burned 100 million tokens — ${dateStr}`,
      bg: 'bg-gradient-to-br from-red-500 via-rose-600 to-red-700',
      border: 'border-red-500/50',
      glow: 'shadow-red-500/40',
      textColor: 'text-white',
    },
    token_1b: {
      emoji: '☄️',
      label: '1B Tokens',
      description: `Burned ONE BILLION tokens — ${dateStr}`,
      bg: 'bg-gradient-to-br from-fuchsia-500 via-purple-600 to-violet-700',
      border: 'border-purple-500/50',
      glow: 'shadow-purple-500/50',
      textColor: 'text-white',
    },
    time_100h: {
      emoji: '⏰',
      label: '100 Hours',
      description: `100 hours of active coding time — ${dateStr}`,
      bg: 'bg-gradient-to-br from-cyan-400 via-blue-500 to-cyan-600',
      border: 'border-cyan-500/50',
      glow: 'shadow-cyan-400/40',
      textColor: 'text-white',
    },
    time_1000h: {
      emoji: '🕐',
      label: '1,000 Hours',
      description: `1,000 hours of active coding time — ${dateStr}`,
      bg: 'bg-gradient-to-br from-blue-500 via-indigo-600 to-blue-700',
      border: 'border-indigo-500/50',
      glow: 'shadow-indigo-500/40',
      textColor: 'text-white',
    },
    time_10000h: {
      emoji: '🧙',
      label: '10,000 Hours',
      description: `10,000 hours — You are the master now — ${dateStr}`,
      bg: 'bg-gradient-to-br from-violet-500 via-purple-700 to-fuchsia-800',
      border: 'border-violet-500/50',
      glow: 'shadow-violet-500/50',
      textColor: 'text-white',
    },
  }
  return configs[medal.medalType] || {
    emoji: '🏅',
    label: medal.medalType,
    description: medal.medalType,
    bg: 'bg-gradient-to-br from-gray-300 to-gray-500',
    border: 'border-gray-400/50',
    glow: 'shadow-gray-400/40',
    textColor: 'text-white',
  }
}

function getCrownBadgeConfig(crown: EngineerCrown): MedalBadgeConfig {
  const isTokens = crown.crownType.includes('tokens')
  const isDaily = crown.crownType.includes('daily')
  const periodLabel = isDaily ? 'Daily' : 'Weekly'
  const metricLabel = isTokens ? 'Tokens' : 'Time'
  const valueStr = isTokens ? formatTokens(crown.value) : formatMinutes(crown.value)

  return {
    emoji: '👑',
    label: `${periodLabel} ${metricLabel}`,
    description: `Company Record — ${periodLabel} ${metricLabel} (${valueStr})`,
    bg: isTokens
      ? 'bg-gradient-to-br from-yellow-400 via-orange-500 to-red-500'
      : 'bg-gradient-to-br from-yellow-400 via-amber-500 to-orange-500',
    border: 'border-yellow-400/60',
    glow: 'shadow-yellow-400/50',
    textColor: 'text-white',
  }
}

function MedalBadge({ config, index }: { config: MedalBadgeConfig; index: number }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <motion.div
          initial={{ opacity: 0, scale: 0, rotate: -20 }}
          animate={{ opacity: 1, scale: 1, rotate: 0 }}
          transition={{
            type: 'spring',
            stiffness: 400,
            damping: 15,
            delay: index * 0.04,
          }}
          whileHover={{
            scale: 1.25,
            rotate: [0, -6, 6, -3, 0],
            transition: { duration: 0.4 },
          }}
          whileTap={{ scale: 0.9 }}
          className={cn(
            'relative flex flex-col items-center justify-center',
            'w-14 h-14 rounded-2xl border-2 cursor-pointer select-none',
            'transition-shadow duration-200',
            config.bg,
            config.border,
            `hover:shadow-lg hover:${config.glow}`,
          )}
        >
          <span className="text-lg leading-none">{config.emoji}</span>
          <span className={cn('text-[8px] font-black leading-tight mt-0.5 text-center px-0.5', config.textColor)}>
            {config.label}
          </span>
        </motion.div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-64 text-center text-sm font-medium">
        {config.description}
      </TooltipContent>
    </Tooltip>
  )
}

function MedalsRibbon({ medalsData }: { medalsData: EngineerMedalsData }) {
  const { crowns, medals } = medalsData

  // Build ordered badge list: crowns first, then ranking medals (gold → silver → bronze), then milestones
  const badges: MedalBadgeConfig[] = []

  // Crowns
  for (const crown of crowns) {
    badges.push(getCrownBadgeConfig(crown))
  }

  // Ranking medals sorted: gold, silver, bronze — then by tokens before time
  const rankOrder: Record<string, number> = { gold: 0, silver: 1, bronze: 2 }
  const metricOrder: Record<string, number> = { tokens: 0, time: 1 }
  const rankingMedals = medals
    .filter((m) => m.medalCategory === 'ranking')
    .sort((a, b) => {
      const rankDiff = (rankOrder[a.medalType] ?? 9) - (rankOrder[b.medalType] ?? 9)
      if (rankDiff !== 0) return rankDiff
      const metricDiff = (metricOrder[a.metricType] ?? 9) - (metricOrder[b.metricType] ?? 9)
      if (metricDiff !== 0) return metricDiff
      return (a.periodStart ?? '').localeCompare(b.periodStart ?? '')
    })
  for (const medal of rankingMedals) {
    badges.push(getRankingBadgeConfig(medal))
  }

  // Milestones
  const milestoneMedals = medals.filter((m) => m.medalCategory === 'milestone')
  for (const medal of milestoneMedals) {
    badges.push(getMilestoneBadgeConfig(medal))
  }

  if (badges.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {badges.map((config, i) => (
        <MedalBadge key={i} config={config} index={i} />
      ))}
    </div>
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
      {showFlameWar && medalsData && (medalsData.crowns.length > 0 || medalsData.medals.length > 0) && (
        <MedalsRibbon medalsData={medalsData} />
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
