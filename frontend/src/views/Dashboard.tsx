import { useAuth } from '@/contexts/AuthContext'

export function Dashboard() {
  const { user } = useAuth()

  return (
    <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <div className="mt-6">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h2 className="text-lg font-medium text-gray-900">Welcome back!</h2>
              <p className="mt-1 text-sm text-gray-600">You are logged in as: {user?.email}</p>
              <div className="mt-6">
                <p className="text-sm text-gray-500">User ID: {user?.id}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}