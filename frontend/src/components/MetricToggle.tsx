import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Calculator,
  ArrowDownToLine,
  ArrowUpFromLine,
  DollarSign,
  GitCommit,
  Plus,
  Minus,
  Code,
  GitPullRequest,
} from 'lucide-react'
import { type MetricType } from '@/hooks/useMetricToggle'

interface MetricToggleProps {
  metric: MetricType
  setMetric: (metric: MetricType) => void
}

interface MetricOption {
  value: MetricType
  label: string
  icon: React.ElementType
}

const tokenMetrics: MetricOption[] = [
  { value: 'total', label: 'Total Tokens', icon: Calculator },
  { value: 'input', label: 'Input Tokens', icon: ArrowDownToLine },
  { value: 'output', label: 'Output Tokens', icon: ArrowUpFromLine },
  { value: 'cost', label: 'Est. Cost', icon: DollarSign },
]

const githubMetrics: MetricOption[] = [
  { value: 'lines', label: 'Total Lines', icon: Code },
  { value: 'additions', label: 'Lines Added', icon: Plus },
  { value: 'deletions', label: 'Lines Removed', icon: Minus },
  { value: 'commits', label: 'Commits', icon: GitCommit },
  { value: 'prs', label: 'PRs Merged', icon: GitPullRequest },
]

const allMetrics = [...tokenMetrics, ...githubMetrics]

export function MetricToggle({ metric, setMetric }: MetricToggleProps) {
  const selected = allMetrics.find((o) => o.value === metric) || tokenMetrics[0]
  const Icon = selected.icon

  return (
    <Select value={metric} onValueChange={(value) => setMetric(value as MetricType)}>
      <SelectTrigger size="sm" className="w-[160px]">
        <SelectValue>
          <span className="flex items-center gap-2">
            <Icon className="h-4 w-4" />
            {selected.label}
          </span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectLabel className="text-xs text-muted-foreground px-2">Token Metrics</SelectLabel>
          {tokenMetrics.map((option) => {
            const OptionIcon = option.icon
            return (
              <SelectItem key={option.value} value={option.value}>
                <span className="flex items-center gap-2">
                  <OptionIcon className="h-4 w-4" />
                  {option.label}
                </span>
              </SelectItem>
            )
          })}
        </SelectGroup>
        <SelectGroup>
          <SelectLabel className="text-xs text-muted-foreground px-2">GitHub Metrics</SelectLabel>
          {githubMetrics.map((option) => {
            const OptionIcon = option.icon
            return (
              <SelectItem key={option.value} value={option.value}>
                <span className="flex items-center gap-2">
                  <OptionIcon className="h-4 w-4" />
                  {option.label}
                </span>
              </SelectItem>
            )
          })}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
