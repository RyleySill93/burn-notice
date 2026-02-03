import { useState } from 'react'
import { useParams, Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  CalendarIcon,
  Zap,
  Activity,
  BarChart3,
  ArrowLeft,
  Trophy,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from '@/lib/axios-instance'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { format, subDays } from 'date-fns'
import { useMetricToggle } from '@/hooks/useMetricToggle'

type MetricType = 'total' | 'input' | 'output' | 'cost'
import { MetricToggle } from '@/components/MetricToggle'

interface PeriodStats {
  tokens: number
  tokens_input: number
  tokens_output: number
  cost_usd: number
  comparison_tokens: number
  comparison_tokens_input: number
  comparison_tokens_output: number
  comparison_cost_usd: number
  change_percent: number | null
}

interface EngineerStats {
  engineer_id: string
  display_name: string
  date: string
  today: PeriodStats
  this_week: PeriodStats
  this_month: PeriodStats
}

interface DailyTotal {
  date: string
  tokens: number
  tokens_input: number
  tokens_output: number
  cost_usd: number
}

interface DailyTotalsResponse {
  start_date: string
  end_date: string
  totals: DailyTotal[]
}

interface HistoricalRank {
  period_start: string
  period_end: string
  rank: number | null
  tokens: number
  tokens_input: number
  tokens_output: number
  cost_usd: number
}

interface HistoricalRankingsResponse {
  engineer_id: string
  period_type: string
  rankings: HistoricalRank[]
}

function getMetricValue(data: { tokens: number; tokens_input: number; tokens_output: number; cost_usd?: number }, metric: MetricType): number {
  switch (metric) {
    case 'input':
      return data.tokens_input
    case 'output':
      return data.tokens_output
    case 'cost':
      return data.cost_usd || 0
    default:
      return data.tokens
  }
}

function getComparisonValue(data: PeriodStats, metric: MetricType): number {
  switch (metric) {
    case 'input':
      return data.comparison_tokens_input
    case 'output':
      return data.comparison_tokens_output
    case 'cost':
      return data.comparison_cost_usd || 0
    default:
      return data.comparison_tokens
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
  if (rankings.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Trophy className="h-8 w-8 mx-auto mb-2 opacity-20" />
        <p className="text-sm">No ranking history</p>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {rankings.map((entry, index) => (
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
              <p className="font-medium text-sm">
                {formatPeriodLabel(entry.period_start, entry.period_end, periodType)}
              </p>
              <p className="text-xs text-muted-foreground">{formatValue(getMetricValue(entry, metric), metric)}{metric !== 'cost' && ' tokens'}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export function EngineerPage() {
  const { engineerId } = useParams<{ engineerId: string }>()
  const [chartStartDate, setChartStartDate] = useState<Date>(subDays(new Date(), 29))
  const [rankingsPeriod, setRankingsPeriod] = useState<string>('daily')
  const { metric, setMetric } = useMetricToggle()

  const { data: stats, isLoading: statsLoading } = useQuery<EngineerStats>({
    queryKey: ['engineer-stats', engineerId],
    queryFn: async () => {
      const response = await axios.get<EngineerStats>(`/api/leaderboard/engineers/${engineerId}/stats`)
      return response.data
    },
    enabled: !!engineerId,
  })

  const { data: dailyTotals, isLoading: chartLoading } = useQuery<DailyTotalsResponse>({
    queryKey: ['engineer-daily-totals', engineerId, chartStartDate.toISOString()],
    queryFn: async () => {
      const response = await axios.get<DailyTotalsResponse>(
        `/api/leaderboard/engineers/${engineerId}/daily-totals`,
        {
          params: {
            start_date: format(chartStartDate, 'yyyy-MM-dd'),
            end_date: format(new Date(), 'yyyy-MM-dd'),
          },
        }
      )
      return response.data
    },
    enabled: !!engineerId,
  })

  const { data: rankings, isLoading: rankingsLoading } = useQuery<HistoricalRankingsResponse>({
    queryKey: ['engineer-rankings', engineerId, rankingsPeriod],
    queryFn: async () => {
      const response = await axios.get<HistoricalRankingsResponse>(
        `/api/leaderboard/engineers/${engineerId}/historical-rankings`,
        {
          params: {
            period_type: rankingsPeriod,
            num_periods: 20,
          },
        }
      )
      return response.data
    },
    enabled: !!engineerId,
  })

  const chartData =
    dailyTotals?.totals.map((t) => ({
      date: format(new Date(t.date), 'MMM d'),
      tokens: getMetricValue(t, metric),
    })) || []

  const isLoading = statsLoading || chartLoading || rankingsLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  const todayTokens = stats ? getMetricValue(stats.today, metric) : 0
  const todayComparison = stats ? getComparisonValue(stats.today, metric) : 0
  const weekTokens = stats ? getMetricValue(stats.this_week, metric) : 0
  const weekComparison = stats ? getComparisonValue(stats.this_week, metric) : 0
  const monthTokens = stats ? getMetricValue(stats.this_month, metric) : 0
  const monthComparison = stats ? getComparisonValue(stats.this_month, metric) : 0

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
            <h1 className="text-2xl font-bold">{stats?.display_name}</h1>
            <p className="text-muted-foreground text-sm">Individual token usage</p>
          </div>
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
          comparison="vs yesterday"
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

      {/* Chart and Historical Rankings */}
      <div className="grid gap-6 lg:grid-cols-5 items-start">
        {/* Chart */}
        <Card className="lg:col-span-3">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">{metric === 'cost' ? 'Daily Costs' : 'Daily Token Burns'}</CardTitle>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                  <CalendarIcon className="h-4 w-4" />
                  {format(chartStartDate, 'MMM d')} - Today
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <Calendar
                  mode="single"
                  selected={chartStartDate}
                  onSelect={(date) => date && setChartStartDate(date)}
                  disabled={(date) => date > new Date() || date < subDays(new Date(), 90)}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => formatValue(value, metric)}
                  />
                  <Tooltip
                    formatter={(value: number) => [formatValue(value, metric), metric === 'cost' ? 'Cost' : 'Tokens']}
                    labelStyle={{ fontWeight: 'bold' }}
                  />
                  <Bar dataKey="tokens" fill="#f97316" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Historical Rankings */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-500" />
              Ranking History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={rankingsPeriod} onValueChange={setRankingsPeriod} className="w-full">
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
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
