import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Settings, Copy, Check } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/contexts/AuthContext'
import axios from '@/lib/axios-instance'

interface MyApiKeyResponse {
  api_key: string
}

export function SetupPage() {
  const { customer } = useAuth()
  const [copied, setCopied] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  const { data: myApiKey, isLoading } = useQuery<MyApiKeyResponse>({
    queryKey: ['my-api-key', customer?.id],
    queryFn: async () => {
      if (!customer?.id) throw new Error('No customer')
      const response = await axios.get<MyApiKeyResponse>(`/invitations/memberships/my-api-key?customer_id=${customer.id}`)
      return response.data
    },
    enabled: !!customer?.id,
  })

  const apiKey = myApiKey?.api_key

  const setupScript = apiKey
    ? `# burn-notice - Claude Code usage tracking
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT="${apiUrl}"
export OTEL_EXPORTER_OTLP_HEADERS="X-API-Key=${apiKey}"`
    : ''

  const handleCopyScript = async () => {
    await navigator.clipboard.writeText(setupScript)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <Settings className="h-12 w-12 text-primary mx-auto mb-4" />
          <CardTitle>Setup Instructions</CardTitle>
          <CardDescription>
            Configure Claude Code to track your usage on the leaderboard.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {apiKey && (
            <div>
              <h3 className="font-semibold mb-2">Shell Configuration</h3>
              <p className="text-sm text-muted-foreground mb-3">
                Add to <code className="bg-muted px-1.5 py-0.5 rounded text-xs">~/.zshrc</code> (or <code className="bg-muted px-1.5 py-0.5 rounded text-xs">~/.bashrc</code>), then run: <code className="bg-muted px-1.5 py-0.5 rounded text-xs">source ~/.zshrc</code>
              </p>
              <div
                className="relative bg-zinc-900 text-zinc-100 rounded-lg p-4 font-mono text-sm overflow-x-auto"
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
              >
                <button
                  onClick={handleCopyScript}
                  className={`absolute top-2 right-2 p-1.5 rounded bg-zinc-700 hover:bg-zinc-600 transition-opacity duration-200 ${
                    isHovered || copied ? 'opacity-100' : 'opacity-0'
                  }`}
                  title="Copy to clipboard"
                >
                  {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4 text-zinc-300" />}
                </button>
                <pre>{setupScript}</pre>
              </div>
            </div>
          )}
          {!apiKey && (
            <p className="text-sm text-yellow-600 text-center">
              Unable to load your API key. Please try refreshing the page.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
