import { createBrowserRouter, Navigate } from "react-router"
import { RootLayout } from "@/components/RootLayout"
import { AuthenticatedLayout } from "@/views/AuthenticatedLayout"
import { HomePage } from "@/views/HomePage"
import { EngineerPage } from "@/views/EngineerPage"
import { LeaderboardPage } from "@/views/LeaderboardPage"
import { SetupPage } from "@/views/SetupPage"
import { ManageTeamPage } from "@/views/team/ManageTeamPage"
import { LoginPage } from "@/views/LoginPage"
import { SignupPage } from "@/views/SignupPage"
import { AuthCallback } from "@/views/AuthCallback"
import { GitHubCallbackPage } from "@/views/GitHubCallbackPage"
import { ForgotPasswordPage } from "@/views/ForgotPasswordPage"
import { ResetPasswordPage } from "@/views/ResetPasswordPage"
import { CreateTeamPage } from "@/views/CreateTeamPage"
import { AcceptInvitationPage } from "@/views/AcceptInvitationPage"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      // Public routes
      {
        path: "login",
        element: <LoginPage />,
      },
      {
        path: "signup",
        element: <SignupPage />,
      },
      {
        path: "auth/callback",
        element: <AuthCallback />,
      },
      {
        path: "auth/github/callback",
        element: <GitHubCallbackPage />,
      },
      {
        path: "forgot-password",
        element: <ForgotPasswordPage />,
      },
      {
        path: "reset-password/:userId/:token",
        element: <ResetPasswordPage />,
      },
      {
        path: "accept-invitation",
        element: <AcceptInvitationPage />,
      },
      // Create customer route (requires auth but not membership)
      {
        path: "create-team",
        element: <CreateTeamPage />,
      },
      // Authenticated routes with layout (requires auth and membership)
      {
        element: <AuthenticatedLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="/dashboard" replace />,
          },
          {
            path: "dashboard",
            element: <HomePage />,
          },
          {
            path: "engineers/:engineerId",
            element: <EngineerPage />,
          },
          {
            path: "leaderboard",
            element: <LeaderboardPage />,
          },
          {
            path: "team",
            element: <ManageTeamPage />,
          },
          {
            path: "setup",
            element: <SetupPage />,
          },
        ],
      },
    ],
  },
])
