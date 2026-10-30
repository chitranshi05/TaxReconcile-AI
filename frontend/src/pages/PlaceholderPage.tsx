interface PlaceholderPageProps {
  icon: string
  title: string
  description: string
  kicker?: string
}

export function PlaceholderPage({
  icon,
  title,
  description,
  kicker,
}: PlaceholderPageProps) {
  return (
    <div className="coming-soon">
      <span className="coming-soon-kicker">CUE {icon} · Standby</span>
      <h2>
        <span className="hero-line-wrap">
          <span className="hero-line">{title}</span>
        </span>
      </h2>
      <p>{kicker ? `${kicker} ${description}` : description}</p>
    </div>
  )
}
