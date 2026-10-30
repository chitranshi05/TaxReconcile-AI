import { useEffect, useRef } from 'react'

export function Cursor() {
  const rootRef = useRef<HTMLDivElement>(null)
  const ringRef = useRef<HTMLDivElement>(null)
  const dotRef = useRef<HTMLDivElement>(null)
  const chXRef = useRef<HTMLDivElement>(null)
  const chYRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fine = window.matchMedia('(pointer: fine)').matches
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!fine || reduce) return

    document.documentElement.classList.add('has-cursor', 'fx-crosshair')

    const pos = { x: window.innerWidth / 2, y: window.innerHeight / 2 }
    const ring = { x: pos.x, y: pos.y }
    let hovering = false
    let frame = 0

    const onMove = (e: PointerEvent) => {
      pos.x = e.clientX
      pos.y = e.clientY
      const target = e.target as HTMLElement | null
      hovering = Boolean(
        target?.closest(
          'a, button, input, textarea, select, label, [role="button"], .nav-item, .upload-zone, .data-table tbody tr',
        ),
      )
    }

    const tick = () => {
      ring.x += (pos.x - ring.x) * 0.18
      ring.y += (pos.y - ring.y) * 0.18

      if (dotRef.current) {
        dotRef.current.style.transform = `translate(${pos.x}px, ${pos.y}px)`
      }
      if (ringRef.current) {
        const s = hovering ? 1.85 : 1
        ringRef.current.style.transform = `translate(${ring.x}px, ${ring.y}px) scale(${s})`
      }
      if (chXRef.current) {
        chXRef.current.style.transform = `translateY(${pos.y}px)`
      }
      if (chYRef.current) {
        chYRef.current.style.transform = `translateX(${pos.x}px)`
      }
      frame = requestAnimationFrame(tick)
    }

    window.addEventListener('pointermove', onMove, { passive: true })
    frame = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', onMove)
      document.documentElement.classList.remove('has-cursor', 'fx-crosshair')
    }
  }, [])

  return (
    <div className="cursor-root" ref={rootRef} aria-hidden="true">
      <div className="crosshair">
        <div className="crosshair-x" ref={chXRef} />
        <div className="crosshair-y" ref={chYRef} />
      </div>
      <div className="cursor-ring" ref={ringRef} />
      <div className="cursor-dot" ref={dotRef} />
    </div>
  )
}
