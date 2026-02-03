import { useSearchParams } from 'react-router'

export type MetricType = 'total' | 'input' | 'output' | 'cost'

export function useMetricToggle() {
  const [searchParams, setSearchParams] = useSearchParams()
  const metric = (searchParams.get('metric') as MetricType) || 'total'

  const setMetric = (newMetric: MetricType) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newMetric === 'total') {
        next.delete('metric')
      } else {
        next.set('metric', newMetric)
      }
      return next
    })
  }

  return { metric, setMetric }
}
