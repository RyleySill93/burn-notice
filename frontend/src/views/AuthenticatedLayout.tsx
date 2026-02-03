import { Navigate, Outlet, useNavigate, Link, useLocation } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import { Flame, LogOut, Check, Building2, Users, Settings, LayoutDashboard, Moon, Sun, Monitor } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuPortal,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { useTheme } from '@/hooks/useTheme'

export function AuthenticatedLayout() {
  const { isAuthenticated, isLoading, logout, user, hasMembership, isStaff, currentCustomerId, setCurrentCustomerId, customer } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { theme, setTheme } = useTheme()

  const handleSwitchCustomer = (customerId: string) => {
    setCurrentCustomerId(customerId)
    navigate('/dashboard')
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" />
  }

  // Redirect to create-team if user has no membership and is not staff
  if (!hasMembership && !isStaff) {
    return <Navigate to="/create-team" />
  }

  const userInitials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : 'U'

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/team', label: 'Team', icon: Users },
  ]

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-card border-b border-border sticky top-0 z-50">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2 font-bold text-lg">
                <Flame className="h-6 w-6 text-orange-500" />
                <span>burn-notice</span>
              </Link>

              <nav className="flex items-center gap-1">
                {navItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                      location.pathname === item.path
                        ? 'bg-accent text-accent-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>

            <div className="flex items-center gap-4">
              {customer && (
                <span className="text-sm text-muted-foreground">
                  {customer.name}
                </span>
              )}

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
                  <DropdownMenuItem asChild>
                    <Link to="/setup">
                      <Settings className="h-4 w-4 mr-2" />
                      Setup Instructions
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>
                      {theme === 'dark' ? (
                        <Moon className="h-4 w-4 mr-2" />
                      ) : theme === 'light' ? (
                        <Sun className="h-4 w-4 mr-2" />
                      ) : (
                        <Monitor className="h-4 w-4 mr-2" />
                      )}
                      Theme
                    </DropdownMenuSubTrigger>
                    <DropdownMenuPortal>
                      <DropdownMenuSubContent>
                        <DropdownMenuItem onClick={() => setTheme('light')}>
                          <Sun className="h-4 w-4 mr-2" />
                          Light
                          {theme === 'light' && <Check className="h-4 w-4 ml-auto" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setTheme('dark')}>
                          <Moon className="h-4 w-4 mr-2" />
                          Dark
                          {theme === 'dark' && <Check className="h-4 w-4 ml-auto" />}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setTheme('system')}>
                          <Monitor className="h-4 w-4 mr-2" />
                          System
                          {theme === 'system' && <Check className="h-4 w-4 ml-auto" />}
                        </DropdownMenuItem>
                      </DropdownMenuSubContent>
                    </DropdownMenuPortal>
                  </DropdownMenuSub>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={logout} className="text-red-600">
                    <LogOut className="h-4 w-4 mr-2" />
                    Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
