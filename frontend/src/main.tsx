import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { ModalsProvider } from '@mantine/modals'
import { HelmetProvider } from 'react-helmet-async'

import App from './App'
import { theme } from './theme'
import { AuthProvider } from './contexts/AuthContext'
import { ServiceWorkerProvider } from './contexts/ServiceWorkerContext'
import { AccessibilityProvider } from './contexts/AccessibilityContext'
import { registerSW } from './utils/serviceWorker'

import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import '@mantine/modals/styles.css'
import '@mantine/dropzone/styles.css'
import '@mantine/dates/styles.css'
import './styles/global.css'

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error: any) => {
        // Don't retry on 4xx errors (client errors)
        if (error?.response?.status >= 400 && error?.response?.status < 500) {
          return false
        }
        // Retry up to 3 times for other errors
        return failureCount < 3
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
    mutations: {
      retry: 1,
    },
  },
})

// Register service worker for PWA
if ('serviceWorker' in navigator) {
  registerSW()
}

// Error boundary
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Application error:', error, errorInfo)
    
    // Report to monitoring service in production
    if (import.meta.env.PROD) {
      // Sentry or other monitoring service
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          padding: '2rem', 
          textAlign: 'center',
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center'
        }}>
          <h1>Something went wrong</h1>
          <p>We're sorry for the inconvenience. Please refresh the page to try again.</p>
          <button 
            onClick={() => window.location.reload()}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              backgroundColor: '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Refresh Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <HelmetProvider>
        <QueryClientProvider client={queryClient}>
          <MantineProvider theme={theme}>
            <AccessibilityProvider>
              <ServiceWorkerProvider>
                <AuthProvider>
                  <BrowserRouter>
                    <ModalsProvider>
                      <Notifications position="top-right" />
                      <App />
                      {import.meta.env.DEV && <ReactQueryDevtools />}
                    </ModalsProvider>
                  </BrowserRouter>
                </AuthProvider>
              </ServiceWorkerProvider>
            </AccessibilityProvider>
          </MantineProvider>
          {import.meta.env.DEV && <ReactQueryDevtools />}
        </QueryClientProvider>
      </HelmetProvider>
    </ErrorBoundary>
  </React.StrictMode>
)