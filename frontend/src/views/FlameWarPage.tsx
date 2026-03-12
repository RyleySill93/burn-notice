import { useState } from 'react'
import { Navigate, Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Flame, Zap, Activity, BarChart3, Swords, Presentation } from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from '@/lib/axios-instance'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { format, isSameDay } from 'date-fns'
import { useMetricToggle, type MetricType } from '@/hooks/useMetricToggle'
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
  githubCommits: number
  githubAdditions: number
  githubDeletions: number
  githubPrsMerged: number
  comparisonGithubCommits: number
  comparisonGithubAdditions: number
  comparisonGithubDeletions: number
  comparisonGithubPrsMerged: number
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

interface TimeSeriesDataPoint {
  timestamp: string
  tokens: number
  tokensInput: number
  tokensOutput: number
  costUsd: number
  githubCommits: number
  githubAdditions: number
  githubDeletions: number
  githubPrsMerged: number
  activeMinutes: number
}

interface TimeSeriesResponse {
  engineerId: string
  period: string
  data: TimeSeriesDataPoint[]
}

interface LeaderboardEntry {
  engineerId: string
  displayName: string
  tokens: number
  rank: number
}

interface Leaderboard {
  date: string
  today: LeaderboardEntry[]
  yesterday: LeaderboardEntry[]
  weekly: LeaderboardEntry[]
  monthly: LeaderboardEntry[]
}


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

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.floor(n / 1_000)}K`
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
  if (metric === 'cost') return formatCost(n)
  if (metric === 'time') return formatMinutes(n)
  return formatTokens(n)
}

// The versus bar - shows proportional comparison between two values
function VersusBar({
  leftValue,
  rightValue,
  leftName,
  rightName,
  metric,
}: {
  leftValue: number
  rightValue: number
  leftName: string
  rightName: string
  metric: MetricType
}) {
  const total = leftValue + rightValue
  const leftPct = total > 0 ? (leftValue / total) * 100 : 50
  const rightPct = total > 0 ? (rightValue / total) * 100 : 50
  const leftWins = leftValue > rightValue
  const rightWins = rightValue > leftValue
  const tie = leftValue === rightValue

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <div className="text-left">
          <span className={cn(
            'text-lg font-bold tabular-nums',
            leftWins && 'text-orange-500',
            tie && total === 0 && 'text-muted-foreground'
          )}>
            {formatValue(leftValue, metric)}
          </span>
          {leftWins && <Flame className="inline h-4 w-4 text-orange-500 ml-1 -mt-1" />}
        </div>
        <div className="text-right">
          {rightWins && <Flame className="inline h-4 w-4 text-blue-500 mr-1 -mt-1" />}
          <span className={cn(
            'text-lg font-bold tabular-nums',
            rightWins && 'text-blue-500',
            tie && total === 0 && 'text-muted-foreground'
          )}>
            {formatValue(rightValue, metric)}
          </span>
        </div>
      </div>
      <div className="flex h-3 rounded-full overflow-hidden bg-muted">
        {total > 0 ? (
          <>
            <div
              className={cn(
                'transition-all duration-500 ease-out',
                leftWins ? 'bg-orange-500' : 'bg-orange-500/40'
              )}
              style={{ width: `${leftPct}%` }}
            />
            <div
              className={cn(
                'transition-all duration-500 ease-out',
                rightWins ? 'bg-blue-500' : 'bg-blue-500/40'
              )}
              style={{ width: `${rightPct}%` }}
            />
          </>
        ) : (
          <>
            <div className="w-1/2 bg-muted-foreground/20" />
            <div className="w-1/2 bg-muted-foreground/20" />
          </>
        )}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{leftName}</span>
        <span>{rightName}</span>
      </div>
    </div>
  )
}

type PeriodType = 'daily' | 'weekly' | 'monthly'


function AllTimeScoreboard({
  leftStats,
  rightStats,
  leftName,
  rightName,
  metric,
}: {
  leftStats: EngineerStats | undefined
  rightStats: EngineerStats | undefined
  leftName: string
  rightName: string
  metric: MetricType
}) {
  const periods = ['today', 'thisWeek', 'thisMonth'] as const
  let leftWins = 0
  let rightWins = 0

  for (const period of periods) {
    const leftVal = leftStats ? getMetricValue(leftStats[period], metric) : 0
    const rightVal = rightStats ? getMetricValue(rightStats[period], metric) : 0
    if (leftVal > rightVal) leftWins++
    if (rightVal > leftVal) rightWins++
  }

  return (
    <Card>
      <CardContent className="py-8">
        <div className="flex items-center justify-center gap-8">
          <div className="text-center">
            <div className={cn(
              'text-5xl font-bold tabular-nums',
              leftWins > rightWins && 'text-orange-500'
            )}>
              {leftWins}
            </div>
            <div className="text-sm text-muted-foreground mt-1 max-w-[120px] truncate">{leftName}</div>
          </div>
          <div className="flex flex-col items-center gap-1">
            <Swords className="h-7 w-7 text-muted-foreground" />
            <span className="text-xs text-muted-foreground font-medium">VS</span>
          </div>
          <div className="text-center">
            <div className={cn(
              'text-5xl font-bold tabular-nums',
              rightWins > leftWins && 'text-blue-500'
            )}>
              {rightWins}
            </div>
            <div className="text-sm text-muted-foreground mt-1 max-w-[120px] truncate">{rightName}</div>
          </div>
        </div>
        <p className="text-center text-xs text-muted-foreground mt-4">
          Period wins (Today + This Week + This Month)
        </p>
      </CardContent>
    </Card>
  )
}

function EngineerSelector({
  value,
  onChange,
  engineers,
  label,
  color,
}: {
  value: string
  onChange: (id: string) => void
  engineers: { id: string; displayName: string }[]
  label: string
  color: string
}) {
  return (
    <div className="flex-1 min-w-0">
      <label className="text-xs font-medium text-muted-foreground mb-1.5 block">{label}</label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className={cn('w-full', value && `border-${color}-500/50`)}>
          <SelectValue placeholder="Select engineer..." />
        </SelectTrigger>
        <SelectContent>
          {engineers.map((eng) => (
            <SelectItem key={eng.id} value={eng.id}>
              {eng.displayName}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

const FLAME_WAR_USER_IDS = ['user-6yckeUKu1M9nH', 'user-pxSgASZi41Zq']

export function FlameWarPage() {
  const { user } = useAuth()

  if (!user?.id || !FLAME_WAR_USER_IDS.includes(user.id)) {
    return <Navigate to="/dashboard" replace />
  }

  return <FlameWarContent />
}

function FlameWarContent() {
  const [leftEngineerId, setLeftEngineerId] = useState<string>('')
  const [rightEngineerId, setRightEngineerId] = useState<string>('')
  const [timeSeriesPeriod, setTimeSeriesPeriod] = useState<PeriodType>('daily')
  const [timeSeriesDate, setTimeSeriesDate] = useState<Date>(new Date())
  const [isCumulative, setIsCumulative] = useState(false)
  const { metric, setMetric } = useMetricToggle()

  const timeSeriesIsToday = isSameDay(timeSeriesDate, new Date())

  // Fetch leaderboard to get engineer list
  const { data: leaderboard } = useQuery<Leaderboard>({
    queryKey: ['leaderboard'],
    queryFn: async () => {
      const response = await axios.get<Leaderboard>('/api/leaderboard')
      return response.data
    },
  })

  // Deduplicate engineers from all leaderboard periods
  const engineers = (() => {
    if (!leaderboard) return []
    const seen = new Map<string, string>()
    const allEntries = [
      ...leaderboard.monthly,
      ...leaderboard.weekly,
      ...leaderboard.today,
      ...leaderboard.yesterday,
    ]
    for (const entry of allEntries) {
      if (!seen.has(entry.engineerId)) {
        seen.set(entry.engineerId, entry.displayName)
      }
    }
    return Array.from(seen.entries())
      .map(([id, displayName]) => ({ id, displayName }))
      .sort((a, b) => a.displayName.localeCompare(b.displayName))
  })()

  // Fetch stats for both engineers
  const { data: leftStats } = useQuery<EngineerStats>({
    queryKey: ['engineer-stats', leftEngineerId],
    queryFn: async () => {
      const response = await axios.get<EngineerStats>(`/api/leaderboard/engineers/${leftEngineerId}/stats`)
      return response.data
    },
    enabled: !!leftEngineerId,
    refetchInterval: 10_000,
  })

  const { data: rightStats } = useQuery<EngineerStats>({
    queryKey: ['engineer-stats', rightEngineerId],
    queryFn: async () => {
      const response = await axios.get<EngineerStats>(`/api/leaderboard/engineers/${rightEngineerId}/stats`)
      return response.data
    },
    enabled: !!rightEngineerId,
    refetchInterval: 10_000,
  })

  // Fetch time series for both
  const { data: leftTimeSeries, isLoading: leftTSLoading } = useQuery<TimeSeriesResponse>({
    queryKey: ['engineer-time-series', leftEngineerId, timeSeriesPeriod, format(timeSeriesDate, 'yyyy-MM-dd')],
    queryFn: async () => {
      const response = await axios.get<TimeSeriesResponse>(
        `/api/leaderboard/engineers/${leftEngineerId}/time-series`,
        { params: { period: timeSeriesPeriod, as_of: format(timeSeriesDate, 'yyyy-MM-dd') } }
      )
      return response.data
    },
    enabled: !!leftEngineerId,
    refetchInterval: timeSeriesIsToday ? 10_000 : false,
  })

  const { data: rightTimeSeries, isLoading: rightTSLoading } = useQuery<TimeSeriesResponse>({
    queryKey: ['engineer-time-series', rightEngineerId, timeSeriesPeriod, format(timeSeriesDate, 'yyyy-MM-dd')],
    queryFn: async () => {
      const response = await axios.get<TimeSeriesResponse>(
        `/api/leaderboard/engineers/${rightEngineerId}/time-series`,
        { params: { period: timeSeriesPeriod, as_of: format(timeSeriesDate, 'yyyy-MM-dd') } }
      )
      return response.data
    },
    enabled: !!rightEngineerId,
    refetchInterval: timeSeriesIsToday ? 10_000 : false,
  })

  // Merge time series data for overlay chart
  const chartData = (() => {
    const leftData = leftTimeSeries?.data || []
    const rightData = rightTimeSeries?.data || []
    const maxLen = Math.max(leftData.length, rightData.length)
    if (maxLen === 0) return []

    let leftCumulative = 0
    let rightCumulative = 0

    const merged = []
    for (let i = 0; i < maxLen; i++) {
      const leftPoint = leftData[i]
      const rightPoint = rightData[i]
      const ts = leftPoint?.timestamp || rightPoint?.timestamp
      if (!ts) continue

      const timestamp = new Date(ts)
      let label: string
      if (timeSeriesPeriod === 'daily') {
        label = format(timestamp, 'MMM d')
      } else if (timeSeriesPeriod === 'weekly') {
        label = format(timestamp, 'MMM d')
      } else {
        label = format(timestamp, 'MMM yyyy')
      }

      const leftVal = leftPoint ? getMetricValue(leftPoint, metric) : 0
      const rightVal = rightPoint ? getMetricValue(rightPoint, metric) : 0
      leftCumulative += leftVal
      rightCumulative += rightVal

      merged.push({
        label,
        left: isCumulative ? leftCumulative : leftVal,
        right: isCumulative ? rightCumulative : rightVal,
      })
    }

    return merged
  })()

  const leftName = leftStats?.displayName || 'Engineer 1'
  const rightName = rightStats?.displayName || 'Engineer 2'
  const bothSelected = !!leftEngineerId && !!rightEngineerId
  const timeSeriesLoading = leftTSLoading || rightTSLoading

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Flame className="h-7 w-7 text-orange-500" />
            <Flame className="h-7 w-7 text-blue-500 absolute top-0 left-3 -scale-x-100" />
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
              Flame War
            </h1>
            <p className="text-muted-foreground text-sm">Head-to-head engineer comparison</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/weekly-recap"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors"
          >
            <Presentation className="h-4 w-4" />
            Weekly Recap
          </Link>
          <MetricToggle metric={metric} setMetric={setMetric} />
        </div>
      </div>

      {/* Engineer Selectors */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-end gap-4">
            <EngineerSelector
              value={leftEngineerId}
              onChange={setLeftEngineerId}
              engineers={engineers.filter(e => e.id !== rightEngineerId)}
              label="Challenger"
              color="orange"
            />
            <div className="flex items-center justify-center pb-2">
              <Badge variant="outline" className="text-xs font-bold px-3 py-1">
                VS
              </Badge>
            </div>
            <EngineerSelector
              value={rightEngineerId}
              onChange={setRightEngineerId}
              engineers={engineers.filter(e => e.id !== leftEngineerId)}
              label="Defender"
              color="blue"
            />
          </div>
        </CardContent>
      </Card>

      {bothSelected && (
        <>
          {/* All-Time Scoreboard */}
          <AllTimeScoreboard
            leftStats={leftStats}
            rightStats={rightStats}
            leftName={leftName}
            rightName={rightName}
            metric={metric}
          />

          {/* Period Comparisons */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Today</CardTitle>
                <Zap className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <VersusBar
                  leftValue={leftStats ? getMetricValue(leftStats.today, metric) : 0}
                  rightValue={rightStats ? getMetricValue(rightStats.today, metric) : 0}
                  leftName={leftName}
                  rightName={rightName}
                  metric={metric}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">This Week</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <VersusBar
                  leftValue={leftStats ? getMetricValue(leftStats.thisWeek, metric) : 0}
                  rightValue={rightStats ? getMetricValue(rightStats.thisWeek, metric) : 0}
                  leftName={leftName}
                  rightName={rightName}
                  metric={metric}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">This Month</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <VersusBar
                  leftValue={leftStats ? getMetricValue(leftStats.thisMonth, metric) : 0}
                  rightValue={rightStats ? getMetricValue(rightStats.thisMonth, metric) : 0}
                  leftName={leftName}
                  rightName={rightName}
                  metric={metric}
                />
              </CardContent>
            </Card>
          </div>

          {/* Time Series Comparison */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">
                Head-to-Head Over Time
                {isCumulative && ' (Cumulative)'}
              </CardTitle>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Switch
                    id="cumulative"
                    checked={isCumulative}
                    onCheckedChange={setIsCumulative}
                  />
                  <Label htmlFor="cumulative" className="text-xs">Cumulative</Label>
                </div>
                <LeaderboardDatePicker
                  activeTab={timeSeriesPeriod === 'daily' ? 'today' : timeSeriesPeriod}
                  selectedDate={timeSeriesDate}
                  onDateChange={setTimeSeriesDate}
                />
              </div>
            </CardHeader>
            <CardContent>
              <Tabs value={timeSeriesPeriod} onValueChange={(v) => setTimeSeriesPeriod(v as PeriodType)} className="w-full mb-4">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="daily" className="text-xs">Daily</TabsTrigger>
                  <TabsTrigger value="weekly" className="text-xs">Weekly</TabsTrigger>
                  <TabsTrigger value="monthly" className="text-xs">Monthly</TabsTrigger>
                </TabsList>
              </Tabs>
              <div className="h-[300px]">
                {timeSeriesLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                  </div>
                ) : chartData.length === 0 || chartData.every(d => d.left === 0 && d.right === 0) ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                    <BarChart3 className="h-12 w-12 mb-2 opacity-20" />
                    <p>No data for this period</p>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="label" fontSize={12} tickLine={false} axisLine={false} interval={timeSeriesPeriod === 'monthly' ? 0 : 'preserveStartEnd'} />
                      <YAxis fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => formatValue(v, metric)} />
                      <Tooltip
                        formatter={(value: number, name: string) => [
                          formatValue(value, metric),
                          name === 'left' ? leftName : rightName
                        ]}
                        labelStyle={{ fontWeight: 'bold', color: '#111827' }}
                      />
                      <Legend formatter={(value) => value === 'left' ? leftName : rightName} />
                      <Bar dataKey="left" fill="#f97316" name="left" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="right" fill="#3b82f6" name="right" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {!bothSelected && (
        <Card>
          <CardContent className="py-16">
            <div className="flex flex-col items-center justify-center text-muted-foreground">
              <Swords className="h-16 w-16 mb-4 opacity-20" />
              <p className="text-lg font-medium">Select two engineers to start the Flame War</p>
              <p className="text-sm mt-1">Choose a challenger and defender above to compare their stats head-to-head</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
