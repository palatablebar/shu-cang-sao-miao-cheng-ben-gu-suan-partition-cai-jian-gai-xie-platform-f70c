const GIB = 1024 ** 3

export function toGib(bytes: number | null | undefined): number {
  return Number(bytes ?? 0) / GIB
}

export function gibLabel(bytes: number | null | undefined, digits = 2): string {
  const value = toGib(bytes)
  if (value === 0) return '0 GiB'
  if (value < 0.01) return `${(toGib(bytes) * 1024).toFixed(1)} MiB`
  return `${value.toFixed(digits)} GiB`
}

export function mibLabel(bytes: number | null | undefined): string {
  return `${(Number(bytes ?? 0) / 1024 ** 2).toFixed(1)} MiB`
}

export function cny(value: number | null | undefined, digits = 2): string {
  return `¥ ${Number(value ?? 0).toFixed(digits)}`
}

export function pct(value: number | null | undefined, digits = 1): string {
  return `${Number(value ?? 0).toFixed(digits)}%`
}

export function ratio(value: number | null | undefined, digits = 2): string {
  return Number(value ?? 0).toFixed(digits)
}

export function intLabel(value: number | null | undefined): string {
  return new Intl.NumberFormat('zh-CN').format(Number(value ?? 0))
}

export function durationLabel(ms: number | null | undefined): string {
  const value = Number(ms ?? 0)
  if (value < 1000) return `${value} ms`
  return `${(value / 1000).toFixed(1)} s`
}

export function dateLabel(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

export function scoreLabel(value: number | null | undefined): string {
  const score = Number(value ?? 0)
  if (score >= 1e9) return `${(score / 1e9).toFixed(2)}e9`
  if (score >= 1e6) return `${(score / 1e6).toFixed(2)}e6`
  if (score >= 1e3) return `${(score / 1e3).toFixed(1)}e3`
  return score.toFixed(0)
}

export function tone3(level: string | null | undefined): 'ok' | 'warn' | 'bad' | 'info' | 'mute' {
  switch (level) {
    case 'low':
    case 'ok':
    case 'prunable':
    case 'completed':
    case 'adopted':
      return 'ok'
    case 'medium':
    case 'warn':
    case 'pending':
    case 'queued':
    case 'running':
      return 'warn'
    case 'high':
    case 'over':
    case 'critical':
    case 'failed':
    case 'blocked':
      return 'bad'
    case 'info':
      return 'info'
    default:
      return 'mute'
  }
}
