import { useState, type FormEvent } from 'react'
import { login, register, getMe } from '../services/auth'
import type { UserResponse } from '../types/api'

interface LoginPageProps {
  onSuccess: (user: UserResponse) => void
}

type Mode = 'login' | 'register'

export function LoginPage({ onSuccess }: LoginPageProps) {
  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!email || !password) {
      setErrorMessage('Please enter both email and password.')
      return
    }

    if (mode === 'register' && !name.trim()) {
      setErrorMessage('Please enter your full name.')
      return
    }

    if (mode === 'register' && password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.')
      return
    }

    setLoading(true)

    try {
      if (mode === 'register') {
        await register(name.trim(), email.trim(), password)
        // Automatically login after successful registration
        await login(email.trim(), password)
      } else {
        await login(email.trim(), password)
      }

      // Fetch user profile
      const user = await getMe()
      onSuccess(user)
    } catch (err) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : 'Authentication failed. Please verify your credentials and try again.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        {/* Brand Header */}
        <div className="auth-brand">
          <div className="auth-brand-icon">🧾</div>
          <div className="auth-brand-text">
            <h2>TaxReconcile AI</h2>
            <span>Financial Ingestion & Reconciliation Platform</span>
          </div>
        </div>

        {/* Tab Toggle */}
        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={`auth-tab-btn ${mode === 'login' ? 'active' : ''}`}
            onClick={() => {
              setMode('login')
              setErrorMessage(null)
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            className={`auth-tab-btn ${mode === 'register' ? 'active' : ''}`}
            onClick={() => {
              setMode('register')
              setErrorMessage(null)
            }}
          >
            Create Account
          </button>
        </div>

        {/* Error Box */}
        {errorMessage && (
          <div className="auth-error-box" role="alert">
            <span className="auth-error-icon">⚠️</span>
            <div className="auth-error-text">{errorMessage}</div>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {mode === 'register' && (
            <div className="auth-field">
              <label htmlFor="name-input">Full Name</label>
              <input
                id="name-input"
                type="text"
                placeholder="e.g. Alexander Hamilton"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                disabled={loading}
                required
              />
            </div>
          )}

          <div className="auth-field">
            <label htmlFor="email-input">Email Address</label>
            <input
              id="email-input"
              type="email"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              disabled={loading}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="password-input">Password</label>
            <input
              id="password-input"
              type="password"
              placeholder={
                mode === 'register'
                  ? 'Min. 8 characters'
                  : 'Enter your password'
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={
                mode === 'register' ? 'new-password' : 'current-password'
              }
              disabled={loading}
              required
            />
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="auth-loading-spinner">Processing…</span>
            ) : mode === 'login' ? (
              'Sign In to Workspace'
            ) : (
              'Create Account'
            )}
          </button>
        </form>

        {/* Footer info */}
        <div className="auth-footer-help">
          {mode === 'login' ? (
            <p>
              New here?{' '}
              <button
                type="button"
                className="auth-link-btn"
                onClick={() => {
                  setMode('register')
                  setErrorMessage(null)
                }}
              >
                Create an account
              </button>
            </p>
          ) : (
            <p>
              Already registered?{' '}
              <button
                type="button"
                className="auth-link-btn"
                onClick={() => {
                  setMode('login')
                  setErrorMessage(null)
                }}
              >
                Sign in to your account
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
