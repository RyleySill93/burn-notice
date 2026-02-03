import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Settings, Copy, Check } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SuperButton } from '@/components/SuperButton'
import { useAuth } from '@/contexts/AuthContext'
import axios from '@/lib/axios-instance'

interface MyApiKeyResponse {
  api_key: string
}

export function SetupPage() {
  const { customer } = useAuth()
  const [copied, setCopied] = useState(false)
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
    ? `# Add to ~/.zshrc (or ~/.bashrc), then run: source ~/.zshrc

# burn-notice - Claude Code usage tracking
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT="${apiUrl}"
export OTEL_EXPORTER_OTLP_HEADERS="X-API-Key=${apiKey}"`
    : ''

  const handleCopyApiKey = async () => {
    if (apiKey) {
      await navigator.clipboard.writeText(apiKey)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

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
            <>
              <div>
                <h3 className="font-semibold mb-2">Your Personal API Key</h3>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-muted px-3 py-2 rounded text-sm font-mono break-all">
                    {apiKey}
                  </code>
                  <SuperButton
                    variant="outline"
                    size="icon"
                    onClick={handleCopyApiKey}
                    className="shrink-0"
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </SuperButton>
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  This key identifies you on the leaderboard. Keep it private.
                </p>
              </div>

              <div>
                <h3 className="font-semibold mb-2">Shell Configuration</h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Add this to your shell config to enable Claude Code telemetry:
                </p>
                <div className="bg-zinc-900 text-zinc-100 rounded-lg p-4 font-mono text-sm overflow-x-auto">
                  <pre>{setupScript}</pre>
                </div>
                <div className="flex gap-2 mt-3">
                  <SuperButton onClick={handleCopyScript} variant="outline">
                    {copied ? 'Copied!' : 'Copy Script'}
                  </SuperButton>
                </div>
              </div>
            </>
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
