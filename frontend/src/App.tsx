import { Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from '@mantine/core'
import { Helmet } from 'react-helmet-async'
import { useHotkeys } from 'react-hotkeys-hook'

import { useAuthStore } from './stores/authStore'
import { useAccessibilityStore } from './stores/accessibilityStore'
import { AppHeader } from './components/layout/AppHeader'
import { AppNavbar } from './components/layout/AppNavbar'
import { AppFooter } from './components/layout/AppFooter'
import { LoadingOverlay } from './components/ui/LoadingOverlay'

// Pages
import { LoginPage } from './pages/auth/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { SearchPage } from './pages/SearchPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { DocumentDetailPage } from './pages/DocumentDetailPage'
import { SettingsPage } from './pages/SettingsPage'
import { AccessibilityPage } from './pages/AccessibilityPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { NotFoundPage } from './pages/NotFoundPage'

// Route guards
import { PrivateRoute } from './components/auth/PrivateRoute'
import { PublicRoute } from './components/auth/PublicRoute'

function App() {
  const { isAuthenticated, isLoading, user } = useAuthStore()
  const { skipToMain, announceNavigation } = useAccessibilityStore()

  // Global keyboard shortcuts
  useHotkeys('alt+1', () => announceNavigation('Search'))
  useHotkeys('alt+2', () => announceNavigation('Documents'))
  useHotkeys('alt+3', () => announceNavigation('Settings'))
  useHotkeys('alt+m', () => skipToMain())

  if (isLoading) {
    return <LoadingOverlay visible />
  }

  return (
    <>
      <Helmet>
        <title>MCP RAG Server</title>
        <meta name="description" content="Semantic search and document management with MCP protocol support" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#1976d2" />
        <link rel="manifest" href="/manifest.json" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </Helmet>

      {/* Skip to main content link for screen readers */}
      <a 
        href="#main-content"
        className="skip-link"
        onFocus={() => skipToMain()}
      >
        Skip to main content
      </a>

      <Routes>
        {/* Public routes */}
        <Route
          path="/login"
          element={
            <PublicRoute>
              <LoginPage />
            </PublicRoute>
          }
        />

        {/* Private routes */}
        <Route
          path="/*"
          element={
            <PrivateRoute>
              <AppLayout />
            </PrivateRoute>
          }
        />
      </Routes>
    </>
  )
}

function AppLayout() {
  const { user } = useAuthStore()
  const needsOnboarding = user && !user.onboarding_completed

  if (needsOnboarding) {
    return <OnboardingPage />
  }

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 300, breakpoint: 'sm', collapsed: { mobile: true } }}
      padding="md"
    >
      <AppHeader />
      <AppNavbar />
      
      <AppShell.Main id="main-content">
        <Routes>
          {/* Dashboard */}
          <Route path="/" element={<DashboardPage />} />
          <Route path="/dashboard" element={<Navigate to="/" replace />} />

          {/* Search */}
          <Route path="/search" element={<SearchPage />} />

          {/* Documents */}
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/:id" element={<DocumentDetailPage />} />

          {/* Settings */}
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/accessibility" element={<AccessibilityPage />} />

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AppShell.Main>

      <AppFooter />
    </AppShell>
  )
}

export default App