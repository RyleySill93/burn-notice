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
import { RankingMedal, MilestoneBadge, CrownBadge as CrownBadgeComponent, PurpleHeartBadge, MILESTONE_CONFIGS } from '@/components/badges'
import type { Rank, Metric as BadgeMetric, MilestoneKind, CrownKind } from '@/components/badges'
import { AnimatedFlames } from '@/components/AnimatedFlames'

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

// --- Medal Ribbon Bar ---

interface RankingGroup {
  rank: Rank
  metric: BadgeMetric
  count: number
  description: string
}

// Milestone tooltip text builder
function buildMilestoneTooltip(medalType: string, dateStr: string): string {
  const cfg = MILESTONE_CONFIGS[medalType as MilestoneKind]
  if (!cfg) return 'Achievement Unlocked'
  const isToken = medalType.startsWith('token_')
  const metricLabel = isToken ? 'tokens burned' : 'coding hours'
  return `${cfg.name} — ${cfg.label} ${metricLabel} — ${dateStr}`
}

function MedalsRibbon({ medalsData }: { medalsData: EngineerMedalsData }) {
  const { crowns, medals } = medalsData

  // Group ranking medals by (medalType, metricType) → count
  const rankingMedals = medals.filter((m) => m.medalCategory === 'ranking')
  const groupKey = (m: EngineerMedalEntry) => `${m.medalType}|${m.metricType}`
  const groupMap = new Map<string, EngineerMedalEntry[]>()
  for (const m of rankingMedals) {
    const key = groupKey(m)
    if (!groupMap.has(key)) groupMap.set(key, [])
    groupMap.get(key)!.push(m)
  }

  const rankOrder: Record<string, number> = { gold: 0, silver: 1, bronze: 2 }
  const metricOrder: Record<string, number> = { tokens: 0, time: 1 }

  const rankingGroups: RankingGroup[] = Array.from(groupMap.entries())
    .map(([, group]) => {
      const first = group[0]
      const isTokens = first.metricType === 'tokens'
      const metricLabel = isTokens ? 'Tokens Burned' : 'Coding Time'
      const rankLabel = first.medalType === 'gold' ? 'Gold' : first.medalType === 'silver' ? 'Silver' : 'Bronze'
      return {
        rank: first.medalType as Rank,
        metric: first.metricType as BadgeMetric,
        count: group.length,
        description: `Weekly ${rankLabel} · ${metricLabel} · Won ${group.length} ${group.length === 1 ? 'time' : 'times'}`,
      }
    })
    .sort((a, b) => {
      const r = (rankOrder[a.rank] ?? 9) - (rankOrder[b.rank] ?? 9)
      if (r !== 0) return r
      return (metricOrder[a.metric] ?? 9) - (metricOrder[b.metric] ?? 9)
    })

  const actionMedals = medals.filter((m) => m.medalCategory === 'action')

  // Only show the highest milestone per metric type (tokens / time)
  const TOKEN_MILESTONE_ORDER: string[] = ['token_10b', 'token_1b', 'token_500m', 'token_250m', 'token_100m', 'token_50m', 'token_10m', 'token_1m']
  const TIME_MILESTONE_ORDER: string[] = ['time_25000h', 'time_10000h', 'time_5000h', 'time_2500h', 'time_1000h', 'time_500h', 'time_100h', 'time_10h']
  const allMilestones = medals.filter((m) => m.medalCategory === 'milestone')
  const milestoneTypes = new Set(allMilestones.map((m) => m.medalType))
  const highestToken = TOKEN_MILESTONE_ORDER.find((t) => milestoneTypes.has(t))
  const highestTime = TIME_MILESTONE_ORDER.find((t) => milestoneTypes.has(t))
  const milestoneMedals = allMilestones.filter(
    (m) => m.medalType === highestToken || m.medalType === highestTime
  )

  const hasCrowns = crowns.length > 0
  const hasRanking = rankingGroups.length > 0
  const hasAction = actionMedals.length > 0
  const hasMilestones = milestoneMedals.length > 0
  const totalBadges = crowns.length + rankingGroups.length + actionMedals.length + milestoneMedals.length
  if (totalBadges === 0) return null

  const separator = <div className="w-px h-8 bg-border/60 mx-1" />

  return (
    <div className="flex flex-wrap gap-2 items-center">
      {crowns.map((crown) => {
        const crownKind = crown.crownType.replace('weekly_', '') as CrownKind
        const isTokens = crownKind === 'tokens'
        const valueStr = isTokens ? formatTokens(crown.value) : formatMinutes(crown.value)
        return (
          <Tooltip key={`crown-${crown.crownType}`}>
            <TooltipTrigger asChild>
              <div><CrownBadgeComponent kind={crownKind} /></div>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-72 text-center">
              <p className="text-sm font-medium">
                Company Record · {isTokens ? 'Most Tokens Burned' : 'Most Coding Time'} ({valueStr})
              </p>
            </TooltipContent>
          </Tooltip>
        )
      })}
      {hasCrowns && hasRanking && separator}
      {rankingGroups.map((g) => (
        <Tooltip key={`rank-${g.rank}-${g.metric}`}>
          <TooltipTrigger asChild>
            <div><RankingMedal rank={g.rank} metric={g.metric} count={g.count} /></div>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-72 text-center">
            <p className="text-sm font-medium">{g.description}</p>
          </TooltipContent>
        </Tooltip>
      ))}
      {(hasCrowns || hasRanking) && hasAction && separator}
      {actionMedals.map((m, i) => {
        const dateStr = format(new Date(m.createdAt), 'MMM d, yyyy')
        return (
          <Tooltip key={`action-${i}`}>
            <TooltipTrigger asChild>
              <div><PurpleHeartBadge /></div>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-72 text-center">
              <p className="text-sm font-medium">Purple Heart — Awarded {dateStr}</p>
              {m.citation && (
                <p className="text-xs italic text-muted-foreground mt-1">"{m.citation}"</p>
              )}
              {m.awardedByDisplayName && (
                <p className="text-[10px] text-muted-foreground mt-0.5">— awarded by {m.awardedByDisplayName}</p>
              )}
            </TooltipContent>
          </Tooltip>
        )
      })}
      {(hasCrowns || hasRanking || hasAction) && hasMilestones && separator}
      {milestoneMedals.map((m, i) => {
        const dateStr = format(new Date(m.createdAt), 'MMM d, yyyy')
        return (
          <Tooltip key={`ms-${m.medalType}-${i}`}>
            <TooltipTrigger asChild>
              <div><MilestoneBadge kind={m.medalType as MilestoneKind} /></div>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-72 text-center">
              <p className="text-sm font-medium">{buildMilestoneTooltip(m.medalType, dateStr)}</p>
            </TooltipContent>
          </Tooltip>
        )
      })}
    </div>
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
    <div className="space-y-6 relative">
      <AnimatedFlames intensity="medium" />
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
          {/* Medals Ribbon inline with name (Flame War users only) */}
          {showFlameWar && medalsData && (medalsData.crowns.length > 0 || medalsData.medals.length > 0) && (
            <MedalsRibbon medalsData={medalsData} />
          )}
          {showFlameWar && engineerId && <AwardMedalButton engineerId={engineerId} />}
        </div>
        <MetricToggle metric={metric} setMetric={setMetric} />
      </div>

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
