import { useLocation, useOutlet } from "react-router"
import { AnimatePresence, motion } from "framer-motion"
import { cloneElement, useRef, useMemo } from "react"

const AUTH_ROUTES = ['/login', '/signup', '/auth/callback', '/forgot-password', '/reset-password']

function isAuthRoute(pathname: string): boolean {
  return AUTH_ROUTES.some(route => pathname.startsWith(route))
}

function getRouteGroup(pathname: string): string {
  if (isAuthRoute(pathname)) return 'auth'
  if (pathname.startsWith('/projects')) return 'projects'
  return 'other'
}

export function AnimatedOutlet() {
  const location = useLocation()
  const outlet = useOutlet()
  const previousOutlet = useRef(outlet)
  const previousGroup = useRef<string | null>(null)
  const hasAnimatedToProjects = useRef(false)

  // Store the outlet element to keep it rendered during exit animation
  if (outlet) {
    previousOutlet.current = outlet
  }

  const currentGroup = getRouteGroup(location.pathname)

  // Determine if we should animate this transition
  const shouldAnimate = useMemo(() => {
    const prevGroup = previousGroup.current

    // Always animate auth route changes
    if (currentGroup === 'auth') {
      return true
    }

    // Animate first transition to projects (from auth or initial load)
    if (currentGroup === 'projects' && !hasAnimatedToProjects.current) {
      if (prevGroup === null || prevGroup === 'auth') {
        hasAnimatedToProjects.current = true
        return true
      }
    }

    return false
  }, [currentGroup, location.pathname])

  // Update previous group after determining animation
  previousGroup.current = currentGroup

  // Clone the outlet element to add a key prop for AnimatePresence
  const element = outlet || previousOutlet.current

  // Use route group as key for auth routes, but stable key for projects
  const animationKey = shouldAnimate ? location.pathname : 'stable-projects'
  const animatedElement = element ? cloneElement(element as React.ReactElement, { key: animationKey }) : null

  if (!shouldAnimate) {
    return <div style={{ height: "100%", width: "100%" }}>{element}</div>
  }

  return (
    <AnimatePresence mode="wait">
      {animatedElement && (
        <motion.div
          key={animationKey}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{
            opacity: 1,
            scale: 1,
            transition: {
              duration: 0.2,
              ease: [0.32, 0.72, 0, 1],
              delay: 0.05
            }
          }}
          exit={{
            opacity: 0,
            scale: 0.98,
            transition: {
              duration: 0.15,
              ease: [0.32, 0, 0.67, 0]
            }
          }}
          style={{ height: "100%", width: "100%" }}
        >
          {animatedElement}
        </motion.div>
      )}
    </AnimatePresence>
  )
}