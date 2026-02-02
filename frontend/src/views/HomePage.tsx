import { Navigate } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'

export function HomePage() {
  const { isAuthenticated } = useAuth()

  // Redirect to dashboard if authenticated, login if not
  if (isAuthenticated) {
    return <Navigate to="/dashboard" />
  }

  return <Navigate to="/login" />
}