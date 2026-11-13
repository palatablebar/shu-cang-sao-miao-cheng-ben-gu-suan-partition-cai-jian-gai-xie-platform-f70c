export function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value))
}

export function scale(value: number, max: number): number {
  if (max <= 0) return 0
  return clamp(value / max)
}

export function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0)
}
