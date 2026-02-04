import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Flame,
  TrendingUp,
  TrendingDown,
  Minus,
  Zap,
  Activity,
  BarChart3,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from '@/lib/axios-instance'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { format, isSameDay } from 'date-fns'
import { useMetricToggle, type MetricType } from '@/hooks/useMetricToggle'
import { useAuth } from '@/contexts/AuthContext'
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
}

interface UsageStats {
  date: string
  today: PeriodStats
  thisWeek: PeriodStats
  thisMonth: PeriodStats
}

interface LeaderboardEntry {
  engineerId: string
  displayName: string
  tokens: number
  tokensInput: number
  tokensOutput: number
  costUsd: number
  rank: number
  prevRank: number | null
  rankChange: number | null
  // GitHub metrics (nullable for users without GitHub connected)
  githubCommits: number | null
  githubAdditions: number | null
  githubDeletions: number | null
  githubPrsMerged: number | null
}

interface Leaderboard {
  date: string
  today: LeaderboardEntry[]
  yesterday: LeaderboardEntry[]
  weekly: LeaderboardEntry[]
  monthly: LeaderboardEntry[]
}

interface EngineerInfo {
  id: string
  displayName: string
}

interface EngineerTimeSeriesData {
  engineerId: string
  tokens: number
  tokensInput: number
  tokensOutput: number
  costUsd: number
  // GitHub metrics
  githubCommits: number
  githubAdditions: number
  githubDeletions: number
  githubPrsMerged: number
}

interface TeamTimeSeriesBucket {
  timestamp: string
  engineers: EngineerTimeSeriesData[]
}

interface TeamTimeSeriesResponse {
  period: string
  engineers: EngineerInfo[]
  data: TeamTimeSeriesBucket[]
}

type TimeSeriesPeriod = 'hourly' | 'daily' | 'weekly' | 'monthly'

function getMetricValue(
  data: {
    tokens: number
    tokensInput: number
    tokensOutput: number
    costUsd?: number
    githubCommits?: number | null
    githubAdditions?: number | null
    githubDeletions?: number | null
    githubPrsMerged?: number | null
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

function formatValue(n: number, metric: MetricType): string {
  if (metric === 'cost') {
    return formatCost(n)
  }
  return formatTokens(n)
}

function getMetricUnit(metric: MetricType): string {
  switch (metric) {
    case 'cost':
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

function RankChangeIndicator({ change }: { change: number | null }) {
  if (change === null) {
    return null
  }
  if (change > 0) {
    return (
      <Badge variant="outline" className="gap-1 text-green-600 border-green-200 bg-green-50">
        <TrendingUp className="h-3 w-3" />
        {change}
      </Badge>
    )
  }
  if (change < 0) {
    return (
      <Badge variant="outline" className="gap-1 text-red-600 border-red-200 bg-red-50">
        <TrendingDown className="h-3 w-3" />
        {Math.abs(change)}
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-gray-500 border-gray-200">
      <Minus className="h-3 w-3" />
    </Badge>
  )
}

function LeaderboardTable({
  entries,
  emptyMessage,
  metric,
  isLoading,
}: {
  entries: LeaderboardEntry[]
  emptyMessage: string
  metric: MetricType
  isLoading?: boolean
}) {
  // Sort entries by the selected metric and assign new ranks
  const sortedEntries = [...entries]
    .sort((a, b) => getMetricValue(b, metric) - getMetricValue(a, metric))
    .map((entry, index) => ({ ...entry, displayRank: index + 1 }))

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (sortedEntries.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Flame className="h-8 w-8 mx-auto mb-2 opacity-20" />
        <p className="text-sm">{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {sortedEntries.slice(0, 10).map((entry, index) => (
        <Link
          key={entry.engineerId}
          to={`/engineers/${entry.engineerId}`}
          className={cn(
            'flex items-center justify-between p-2.5 rounded-lg border transition-colors hover:border-orange-300',
            index === 0 && 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200',
            index === 1 && 'bg-gradient-to-r from-gray-50 to-slate-50 border-gray-200',
            index === 2 && 'bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200',
            index > 2 && 'bg-card'
          )}
        >
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs',
                index === 0 && 'bg-amber-500 text-white',
                index === 1 && 'bg-gray-400 text-white',
                index === 2 && 'bg-orange-400 text-white',
                index > 2 && 'bg-gray-100 text-gray-600'
              )}
            >
              {entry.displayRank}
            </div>
            <div>
              <p className={cn(
                'font-medium text-sm',
                index <= 2 ? 'text-gray-900 hover:text-orange-700' : 'hover:text-orange-600'
              )}>{entry.displayName}</p>
              <p className={cn(
                'text-xs',
                index <= 2 ? 'text-gray-600' : 'text-muted-foreground'
              )}>{formatValue(getMetricValue(entry, metric), metric)}{getMetricUnit(metric)}</p>
            </div>
          </div>
          <RankChangeIndicator change={entry.rankChange} />
        </Link>
      ))}
    </div>
  )
}

type LeaderboardTab = 'today' | 'weekly' | 'monthly'

export function HomePage() {
  // Aggregated chart state
  const [aggPeriod, setAggPeriod] = useState<TimeSeriesPeriod>('hourly')
  const [aggDate, setAggDate] = useState<Date>(new Date())
  const [aggIsCumulative, setAggIsCumulative] = useState(false)

  // By-engineer chart state
  const [timeSeriesPeriod, setTimeSeriesPeriod] = useState<TimeSeriesPeriod>('hourly')
  const [timeSeriesDate, setTimeSeriesDate] = useState<Date>(new Date())
  const [isCumulative, setIsCumulative] = useState(false)

  const [leaderboardDate, setLeaderboardDate] = useState<Date>(new Date())
  const [leaderboardTab, setLeaderboardTab] = useState<LeaderboardTab>('today')
  const { metric, setMetric } = useMetricToggle()
  const { customer } = useAuth()

  // Poll for live updates when viewing today's data (every 10s)
  const aggIsToday = isSameDay(aggDate, new Date())
  const timeSeriesIsToday = isSameDay(timeSeriesDate, new Date())
  const leaderboardIsToday = isSameDay(leaderboardDate, new Date())

  const { data: stats } = useQuery<UsageStats>({
    queryKey: ['usage-stats'],
    queryFn: async () => {
      const response = await axios.get<UsageStats>('/api/leaderboard/stats')
      return response.data
    },
    refetchInterval: 10_000, // Always poll stats since it shows today's data
  })

  // Aggregated chart data
  const { data: aggTimeSeries, isLoading: aggLoading } = useQuery<TeamTimeSeriesResponse>({
    queryKey: ['team-time-series-agg', aggPeriod, format(aggDate, 'yyyy-MM-dd')],
    queryFn: async () => {
      const response = await axios.get<TeamTimeSeriesResponse>('/api/leaderboard/time-series', {
        params: {
          period: aggPeriod,
          as_of: format(aggDate, 'yyyy-MM-dd'),
        },
      })
      return response.data
    },
    refetchInterval: aggIsToday ? 10_000 : false,
  })

  // By-engineer chart data
  const { data: teamTimeSeries, isLoading: timeSeriesLoading } = useQuery<TeamTimeSeriesResponse>({
    queryKey: ['team-time-series', timeSeriesPeriod, format(timeSeriesDate, 'yyyy-MM-dd')],
    queryFn: async () => {
      const response = await axios.get<TeamTimeSeriesResponse>('/api/leaderboard/time-series', {
        params: {
          period: timeSeriesPeriod,
          as_of: format(timeSeriesDate, 'yyyy-MM-dd'),
        },
      })
      return response.data
    },
    refetchInterval: timeSeriesIsToday ? 10_000 : false,
  })

  const { data: leaderboard, isLoading: leaderboardLoading } = useQuery<Leaderboard>({
    queryKey: ['leaderboard', format(leaderboardDate, 'yyyy-MM-dd')],
    queryFn: async () => {
      const response = await axios.get<Leaderboard>('/api/leaderboard', {
        params: {
          as_of: format(leaderboardDate, 'yyyy-MM-dd'),
        },
      })
      return response.data
    },
    refetchInterval: leaderboardIsToday ? 10_000 : false,
  })

  // Build aggregated chart data (sum across all engineers)
  const aggChartData = (() => {
    if (!aggTimeSeries) return []

    let cumulative = 0

    const allData = aggTimeSeries.data.map((bucket) => {
      // Format label based on period
      let label: string
      const timestamp = new Date(bucket.timestamp)
      if (aggPeriod === 'hourly') {
        label = format(timestamp, 'h:mm a')
      } else if (aggPeriod === 'daily') {
        label = format(timestamp, 'MMM d')
      } else if (aggPeriod === 'weekly') {
        label = format(timestamp, 'MMM d')
      } else {
        label = format(timestamp, 'MMM yyyy')
      }

      // Sum across all engineers for this bucket
      let bucketTotal = 0
      let bucketInput = 0
      let bucketOutput = 0
      for (const eng of bucket.engineers) {
        bucketTotal += getMetricValue(eng, metric)
        bucketInput += eng.tokensInput
        bucketOutput += eng.tokensOutput
      }

      cumulative += bucketTotal

      return {
        label,
        value: aggIsCumulative ? cumulative : bucketTotal,
        tokensInput: bucketInput,
        tokensOutput: bucketOutput,
      }
    })

    // Filter out leading zeros (only for hourly view)
    if (aggPeriod === 'hourly') {
      const firstNonZeroIndex = allData.findIndex(d => d.value > 0)
      if (firstNonZeroIndex > 0) {
        return allData.slice(firstNonZeroIndex)
      }
    }
    return allData
  })()

  // Build time series chart data (by engineer)
  const { timeSeriesChartData, sortedEngineers } = (() => {
    if (!teamTimeSeries) return { timeSeriesChartData: [], sortedEngineers: [] }

    const engineers = teamTimeSeries.engineers
    const cumulative: Record<string, number> = {}

    const data = teamTimeSeries.data.map((bucket) => {
      // Format label based on period
      let label: string
      const timestamp = new Date(bucket.timestamp)
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

      const row: Record<string, number | string> = { label }

      // Update cumulative totals and add values to row
      for (const eng of bucket.engineers) {
        const value = getMetricValue(eng, metric)
        cumulative[eng.engineerId] = (cumulative[eng.engineerId] || 0) + value
      }

      // Add all engineers to this row
      for (const eng of engineers) {
        if (isCumulative) {
          row[eng.id] = cumulative[eng.id] || 0
        } else {
          const engData = bucket.engineers.find(e => e.engineerId === eng.id)
          row[eng.id] = engData ? getMetricValue(engData, metric) : 0
        }
      }

      return row
    })

    // Sort engineers by their final cumulative value (descending)
    const sorted = [...engineers].sort((a, b) => {
      const aTotal = cumulative[a.id] || 0
      const bTotal = cumulative[b.id] || 0
      return bTotal - aTotal
    })

    // Filter out leading zeros (only for hourly view)
    let filteredData = data
    if (timeSeriesPeriod === 'hourly') {
      const firstNonZeroIndex = data.findIndex(row => {
        return engineers.some(eng => (row[eng.id] as number) > 0)
      })
      if (firstNonZeroIndex > 0) {
        filteredData = data.slice(firstNonZeroIndex)
      }
    }

    return { timeSeriesChartData: filteredData, sortedEngineers: sorted }
  })()

  // Colors for engineer lines
  const lineColors = [
    '#f97316', // orange
    '#3b82f6', // blue
    '#22c55e', // green
    '#a855f7', // purple
    '#ef4444', // red
    '#14b8a6', // teal
    '#f59e0b', // amber
    '#ec4899', // pink
    '#6366f1', // indigo
    '#84cc16', // lime
  ]

  const todayTokens = stats?.today ? getMetricValue(stats.today, metric) : 0
  const todayComparison = stats?.today ? getComparisonValue(stats.today, metric) : 0
  const weekTokens = stats?.thisWeek ? getMetricValue(stats.thisWeek, metric) : 0
  const weekComparison = stats?.thisWeek ? getComparisonValue(stats.thisWeek, metric) : 0
  const monthTokens = stats?.thisMonth ? getMetricValue(stats.thisMonth, metric) : 0
  const monthComparison = stats?.thisMonth ? getComparisonValue(stats.thisMonth, metric) : 0

  return (
    <div className="space-y-6">
      {/* Header with Team Name and Metric Toggle */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{customer?.name} Team</h1>
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

      {/* Aggregated Chart and Leaderboard - Side by Side */}
      <div className="grid gap-6 lg:grid-cols-2 items-start">
        {/* Aggregated Token Usage Chart */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">
              {metric === 'cost' ? 'Team Costs' : 'Team Token Usage'}
              {aggIsCumulative && ' (Cumulative)'}
            </CardTitle>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Switch
                  id="agg-cumulative"
                  checked={aggIsCumulative}
                  onCheckedChange={setAggIsCumulative}
                />
                <Label htmlFor="agg-cumulative" className="text-xs">Cumulative</Label>
              </div>
              <LeaderboardDatePicker
                activeTab={aggPeriod === 'daily' || aggPeriod === 'hourly' ? 'today' : aggPeriod}
                selectedDate={aggDate}
                onDateChange={setAggDate}
              />
            </div>
          </CardHeader>
          <CardContent>
            <Tabs value={aggPeriod} onValueChange={(v) => setAggPeriod(v as TimeSeriesPeriod)} className="w-full mb-4">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="hourly" className="text-xs">Hourly</TabsTrigger>
                <TabsTrigger value="daily" className="text-xs">Daily</TabsTrigger>
                <TabsTrigger value="weekly" className="text-xs">Weekly</TabsTrigger>
                <TabsTrigger value="monthly" className="text-xs">Monthly</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="h-[300px]">
              {aggLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                </div>
              ) : aggChartData.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  No data for this period
                </div>
              ) : aggPeriod === 'hourly' ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={aggChartData}>
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
                    <Tooltip
                      formatter={(value: number) => [
                        formatValue(value, metric),
                        metric === 'cost'
                          ? (aggIsCumulative ? 'Cumulative Cost' : 'Cost')
                          : (aggIsCumulative ? 'Cumulative Tokens' : 'Tokens')
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
                  <BarChart data={aggChartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="label"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      interval={aggPeriod === 'monthly' ? 0 : 'preserveStartEnd'}
                    />
                    <YAxis
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => formatValue(value, metric)}
                    />
                    <Tooltip
                      formatter={(value: number, name: string) => {
                        const label = name === 'tokensInput' ? 'Input' : name === 'tokensOutput' ? 'Output' : metric === 'cost' ? 'Cost' : 'Tokens'
                        return [formatValue(value, metric), label]
                      }}
                      labelStyle={{ fontWeight: 'bold', color: '#111827' }}
                    />
                    {metric === 'cost' || aggIsCumulative ? (
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

        {/* Leaderboard */}
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Flame className="h-4 w-4 text-orange-500" />
              Leaderboard
            </CardTitle>
            <LeaderboardDatePicker
              activeTab={leaderboardTab}
              selectedDate={leaderboardDate}
              onDateChange={setLeaderboardDate}
            />
          </CardHeader>
          <CardContent>
            <Tabs value={leaderboardTab} onValueChange={(v) => setLeaderboardTab(v as LeaderboardTab)} className="w-full">
              <TabsList className="grid w-full grid-cols-3 mb-4">
                <TabsTrigger value="today" className="text-xs">
                  Today
                </TabsTrigger>
                <TabsTrigger value="weekly" className="text-xs">
                  Week
                </TabsTrigger>
                <TabsTrigger value="monthly" className="text-xs">
                  Month
                </TabsTrigger>
              </TabsList>
              <TabsContent value="today">
                <LeaderboardTable
                  entries={leaderboard?.today || []}
                  emptyMessage="No usage today yet"
                  metric={metric}
                  isLoading={leaderboardLoading}
                />
              </TabsContent>
              <TabsContent value="weekly">
                <LeaderboardTable
                  entries={leaderboard?.weekly || []}
                  emptyMessage="No usage this week"
                  metric={metric}
                  isLoading={leaderboardLoading}
                />
              </TabsContent>
              <TabsContent value="monthly">
                <LeaderboardTable
                  entries={leaderboard?.monthly || []}
                  emptyMessage="No usage this month"
                  metric={metric}
                  isLoading={leaderboardLoading}
                />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      {/* Team Token Usage by Engineer */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">
            {metric === 'cost' ? 'Team Costs by Engineer' : 'Team Token Usage by Engineer'}
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
              activeTab={timeSeriesPeriod === 'daily' || timeSeriesPeriod === 'hourly' ? 'today' : timeSeriesPeriod}
              selectedDate={timeSeriesDate}
              onDateChange={setTimeSeriesDate}
            />
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={timeSeriesPeriod} onValueChange={(v) => setTimeSeriesPeriod(v as TimeSeriesPeriod)} className="w-full mb-4">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="hourly" className="text-xs">Hourly</TabsTrigger>
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
            ) : timeSeriesChartData.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                No data for this period
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
                  <Tooltip
                    formatter={(value: number, name: string) => {
                      const engineer = sortedEngineers.find(e => e.id === name)
                      return [formatValue(value, metric), engineer?.displayName || name]
                    }}
                    labelStyle={{ fontWeight: 'bold', color: '#111827' }}
                  />
                  <Legend
                    content={() => (
                      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
                        {sortedEngineers.map((eng, idx) => (
                          <Link
                            key={eng.id}
                            to={`/engineers/${eng.id}`}
                            className="flex items-center gap-1.5 text-sm hover:underline"
                          >
                            <span
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: lineColors[idx % lineColors.length] }}
                            />
                            {eng.displayName}
                          </Link>
                        ))}
                      </div>
                    )}
                  />
                  {sortedEngineers.map((eng, idx) => (
                    <Line
                      key={eng.id}
                      type="monotone"
                      dataKey={eng.id}
                      stroke={lineColors[idx % lineColors.length]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
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
                  <Tooltip
                    formatter={(value: number, name: string) => {
                      const engineer = sortedEngineers.find(e => e.id === name)
                      return [formatValue(value, metric), engineer?.displayName || name]
                    }}
                    labelStyle={{ fontWeight: 'bold', color: '#111827' }}
                  />
                  <Legend
                    content={() => (
                      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
                        {sortedEngineers.map((eng, idx) => (
                          <Link
                            key={eng.id}
                            to={`/engineers/${eng.id}`}
                            className="flex items-center gap-1.5 text-sm hover:underline"
                          >
                            <span
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: lineColors[idx % lineColors.length] }}
                            />
                            {eng.displayName}
                          </Link>
                        ))}
                      </div>
                    )}
                  />
                  {sortedEngineers.map((eng, idx) => (
                    <Bar
                      key={eng.id}
                      dataKey={eng.id}
                      fill={lineColors[idx % lineColors.length]}
                      stackId="engineers"
                      radius={idx === sortedEngineers.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
