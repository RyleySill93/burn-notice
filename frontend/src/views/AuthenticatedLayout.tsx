import { Navigate, Outlet, useParams, useNavigate } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import { ProjectSidebar } from '@/views/projects/ProjectSidebar'
import { Search, LogOut, Check, Building2 } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu'
import { useProjects } from '@/hooks/useProjects'

export function AuthenticatedLayout() {
  const { isAuthenticated, isLoading, logout, user, hasMembership, isStaff, currentCustomerId, setCurrentCustomerId } = useAuth()
  const { projectId } = useParams<{ projectId?: string }>()
  const navigate = useNavigate()

  const { data: projects = [] } = useProjects(currentCustomerId ?? undefined)

  const handleSwitchCustomer = (customerId: string) => {
    setCurrentCustomerId(customerId)
    // Navigate to projects home when switching teams
    navigate('/projects')
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" />
  }

  // Redirect to create-customer if user has no membership and is not staff
  if (!hasMembership && !isStaff) {
    return <Navigate to="/create-customer" />
  }

  const userInitials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : 'U'

  return (
    <div className="flex h-screen bg-gray-50">
      <ProjectSidebar projects={projects} selectedProjectId={projectId} />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 h-14 flex items-center px-6">
          <div className="flex-1 flex items-center gap-4">
            <div className="relative w-96">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="search"
                placeholder="Search"
                className="pl-10 bg-gray-50 border-gray-300 focus:bg-white"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="focus:outline-none">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-primary text-primary-foreground text-xs">
                      {userInitials}
                    </AvatarFallback>
                  </Avatar>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64">
                <div className="px-2 py-1.5">
                  <p className="text-sm font-medium">{user?.email}</p>
                </div>
                <DropdownMenuSeparator />
                {user?.memberships && user.memberships.length > 1 && (
                  <>
                    <DropdownMenuLabel className="text-xs text-muted-foreground">
                      Switch team
                    </DropdownMenuLabel>
                    {user.memberships.map((membership) => (
                      <DropdownMenuItem
                        key={membership.customerId}
                        onClick={() => handleSwitchCustomer(membership.customerId)}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4" />
                          <span>{membership.customer?.name || 'Unknown Team'}</span>
                        </div>
                        {currentCustomerId === membership.customerId && (
                          <Check className="h-4 w-4 text-primary" />
                        )}
                      </DropdownMenuItem>
                    ))}
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuItem onClick={logout} className="text-red-600">
                  <LogOut className="h-4 w-4 mr-2" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}