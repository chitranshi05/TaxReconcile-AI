// PlaceholderPage — shown for nav sections that are not yet built

interface PlaceholderPageProps {
  icon: string
  title: string
  description: string
}

export function PlaceholderPage({ icon, title, description }: PlaceholderPageProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        gap: 16,
        textAlign: 'center',
        padding: '40px 20px',
      }}
    >
      {/* Glowing orb behind the icon */}
      <div
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            position: 'absolute',
            width: 100,
            height: 100,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(99,102,241,0.18) 0%, transparent 70%)',
          }}
        />
        <span style={{ fontSize: 52, position: 'relative' }}>{icon}</span>
      </div>

      <div>
        <h2
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: 'var(--text-primary)',
            letterSpacing: '-0.5px',
            marginBottom: 8,
          }}
        >
          {title}
        </h2>
        <p
          style={{
            fontSize: 13,
            color: 'var(--text-secondary)',
            maxWidth: 360,
            lineHeight: 1.6,
          }}
        >
          {description}
        </p>
      </div>

      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 14px',
          borderRadius: 20,
          background: 'var(--brand-glow)',
          border: '1px solid var(--border-brand)',
          color: 'var(--brand-start)',
          fontSize: 11,
          fontWeight: 600,
        }}
      >
        🚧 Coming soon
      </div>
    </div>
  )
}
