import React, { useState } from 'react'
import { loginUser, registerUser, getCurrentUser, type AuthUser } from '../services/auth'
import { LockIcon } from './Icons'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (user: AuthUser) => void
}

export function AuthModal({ isOpen, onClose, onSuccess }: AuthModalProps) {
  const [tab, setTab] = useState<'LOGIN' | 'REGISTER'>('LOGIN')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!isOpen) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (tab === 'REGISTER') {
        await registerUser(name, email, password)
      }
      await loginUser(email, password)
      const user = await getCurrentUser()
      onSuccess(user)
      onClose()
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(28, 27, 24, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 200,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        className="paper-panel"
        style={{ maxWidth: '420px', width: '100%', padding: '32px' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{ color: 'var(--brand-green)', marginBottom: '8px' }}>
            <LockIcon size={28} />
          </div>
          <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '24px', fontWeight: 400 }}>
            {tab === 'LOGIN' ? 'Access Private Ledger' : 'Create Auditor Account'}
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Institutional financial reconciliation platform
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
          <button
            type="button"
            className={`btn btn-sm ${tab === 'LOGIN' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ flex: 1 }}
            onClick={() => setTab('LOGIN')}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`btn btn-sm ${tab === 'REGISTER' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ flex: 1 }}
            onClick={() => setTab('REGISTER')}
          >
            Register
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: '10px',
              backgroundColor: 'var(--semantic-error-bg)',
              color: 'var(--semantic-error)',
              border: '1px solid var(--semantic-error-border)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {tab === 'REGISTER' && (
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                type="text"
                className="form-input"
                required
                placeholder="e.g. Aditya Pandey"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Work Email Address</label>
            <input
              type="email"
              className="form-input"
              required
              placeholder="auditor@firm.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Security Password</label>
            <input
              type="password"
              className="form-input"
              required
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div style={{ marginTop: '24px' }}>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px' }}
              disabled={loading}
            >
              {loading ? 'Authenticating…' : tab === 'LOGIN' ? 'Enter Ledger' : 'Register Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
