// Validate required environment variables
if (!import.meta.env.VITE_API_BASE_URL) {
  throw new Error('VITE_API_BASE_URL environment variable is required')
}

if (!import.meta.env.VITE_WS_BASE_URL) {
  throw new Error('VITE_WS_BASE_URL environment variable is required')
}

export const config = {
  // Project branding
  projectName: import.meta.env.VITE_PROJECT_NAME || 'App',
  appTitle: import.meta.env.VITE_APP_TITLE || import.meta.env.VITE_PROJECT_NAME || 'App',
  
  // Company information
  supportEmail: import.meta.env.VITE_SUPPORT_EMAIL || 'support@example.com',
  companyName: import.meta.env.VITE_COMPANY_NAME || 'Company, Inc.',
  companyWebsite: import.meta.env.VITE_COMPANY_WEBSITE || 'www.example.com',
  logoUrl: import.meta.env.VITE_LOGO_URL || '/logo.png',
  
  // API configuration
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  wsBaseUrl: import.meta.env.VITE_WS_BASE_URL,
} as const