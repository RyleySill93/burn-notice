import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Calculator, ArrowDownToLine, ArrowUpFromLine } from 'lucide-react'

type MetricType = 'total' | 'input' | 'output'

interface MetricToggleProps {
  metric: MetricType
  setMetric: (metric: MetricType) => void
}

const metricOptions: { value: MetricType; label: string; icon: React.ElementType }[] = [
  { value: 'total', label: 'Total Tokens', icon: Calculator },
  { value: 'input', label: 'Input Tokens', icon: ArrowDownToLine },
  { value: 'output', label: 'Output Tokens', icon: ArrowUpFromLine },
]

export function MetricToggle({ metric, setMetric }: MetricToggleProps) {
  const selected = metricOptions.find((o) => o.value === metric) || metricOptions[0]
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
        {metricOptions.map((option) => {
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
      </SelectContent>
    </Select>
  )
}
