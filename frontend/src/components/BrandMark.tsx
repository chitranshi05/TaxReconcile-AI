export function BrandMark({ className = 'brand-mark' }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 28"
      role="img"
      aria-hidden="true"
      fill="currentColor"
    >
      <rect x="0" y="0" width="4" height="12" />
      <rect x="0" y="16" width="4" height="12" />
      <rect x="20" y="0" width="4" height="12" />
      <rect x="20" y="16" width="4" height="12" />
      <rect x="6" y="0" width="12" height="3" />
      <rect x="10" y="3" width="4" height="9" />
      <rect x="6" y="6" width="3" height="6" />
      <rect x="15" y="6" width="3" height="6" />
      <rect x="6" y="16" width="3" height="9" />
      <rect x="10.5" y="16" width="3" height="9" />
      <rect x="15" y="16" width="3" height="9" />
      <rect x="6" y="25" width="12" height="3" />
    </svg>
  )
}
