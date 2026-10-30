import { useEffect, useState } from 'react'

function pad(n: number, w = 2) {
  return String(n).padStart(w, '0')
}

function formatTimecode(date: Date) {
  const frames = Math.floor(date.getMilliseconds() / (1000 / 30))
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}:${pad(frames)}`
}

function zoneLabel() {
  const offset = -new Date().getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const abs = Math.abs(offset)
  const h = Math.floor(abs / 60)
  const m = abs % 60
  return m ? `GMT${sign}${h}:${pad(m)}` : `GMT${sign}${h}`
}

export function Timecode({ version = 'ENGINE 0.1' }: { version?: string }) {
  const [tc, setTc] = useState(() => formatTimecode(new Date()))

  useEffect(() => {
    const id = window.setInterval(() => setTc(formatTimecode(new Date())), 33)
    return () => window.clearInterval(id)
  }, [])

  return (
    <span className="status mono">
      <span className="dot dot-live" aria-hidden="true" />
      <span className="status-tc t-num">{tc}</span>
      <span className="status-zone">{zoneLabel()}</span>
      <span className="status-sep">·</span>
      <span className="status-ver">{version}</span>
    </span>
  )
}
