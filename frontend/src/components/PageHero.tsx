interface PageHeroProps {
  kicker?: string
  line1: string
  line2?: string
  lede?: string
  cue?: string
}

export function PageHero({ kicker, line1, line2, lede, cue }: PageHeroProps) {
  return (
    <section className="page-hero" aria-label="Page intro">
      {kicker && <p className="hero-kicker">{kicker}</p>}
      <h1 className="hero-title">
        <span className="hero-line-wrap">
          <span className="hero-line">{line1}</span>
        </span>
        {line2 && (
          <span className="hero-line-wrap">
            <span className="hero-line hero-line-delay">{line2}</span>
          </span>
        )}
      </h1>
      {lede && <p className="hero-lede">{lede}</p>}
      {cue && <p className="cue-label mono">{cue}</p>}
    </section>
  )
}
