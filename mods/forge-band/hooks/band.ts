// Pure logic for the band: no `$`, so tests can call it directly.
import type { Forge, NextTask } from '../types'

// ponytail: fixed 1h TTL. The API usage the mod sees carries no TTL, and under usage
// overage the cache drops to 5m; make it a userConfig option if that bites.
export const CACHE_TTL_MS = 60 * 60 * 1000
export const WARN_MS = 5 * 60 * 1000
const AMBER_MS = 15 * 60 * 1000

// Forge Flow lays out the same files under `.claude/` in a consumer project
// and at the root of the framework repo itself.
export const LAYOUTS = ['.claude/', ''] as const

export type Cache = { leftMs: number; color: 'green' | 'yellow' | 'red' | 'gray'; label: string }

export function cacheState(lastResponseAt: number, now: number): Cache {
  if (lastResponseAt === 0) return { leftMs: 0, color: 'gray', label: 'cache –' }
  const leftMs = Math.max(0, lastResponseAt + CACHE_TTL_MS - now)
  if (leftMs === 0) return { leftMs, color: 'red', label: 'cache cold' }
  const color = leftMs <= WARN_MS ? 'red' : leftMs <= AMBER_MS ? 'yellow' : 'green'
  return { leftMs, color, label: `cache ${Math.ceil(leftMs / 60000)}m left` }
}

export function tokens(n: number): string {
  return n >= 1000 ? `${Math.round(n / 1000)}k` : String(n)
}

// `forge task ls --ready --json` prints the queue in priority order.
// `forge version` prints the VERSION file, or an "unknown (...)" placeholder on pre-4.2 installs.
export function parseForge(readyJson: string, driftJson: string, versionOut = ''): Forge {
  const ready: Array<{ id: string; epic: string }> = JSON.parse(readyJson)
  const [first] = ready
  const next: NextTask | null = first ? { id: first.id, epic: first.epic } : null
  let drift = 0
  try {
    drift = (JSON.parse(driftJson).findings ?? []).length
  } catch {
    drift = -1 // banner unreadable: show "?" rather than a false 0
  }
  const version = /^\d/.test(versionOut.trim()) ? versionOut.trim() : null
  return { next, ready: ready.length, drift, version }
}

// `gh pr view --json number,state` exits non-zero when the branch has no PR,
// and still returns the PR after it is merged or closed.
export function parsePr(exitCode: number, stdout: string): number | null {
  if (exitCode !== 0) return null
  try {
    const pr = JSON.parse(stdout)
    return pr.state === 'OPEN' ? pr.number : null
  } catch {
    return null
  }
}

// `confirm`: the first press only arms the button; a second press within CONFIRM_MS runs it.
export type Action = { key: string; label: string; command: string; args: string; confirm?: true }

export const CONFIRM_MS = 10_000

// The four commands run most across the last 30 Forge Flow sessions, plus the specialist PR review.
// `armed` is the epic whose Run button was pressed once and awaits confirmation;
// `pr` is the current branch's open PR, without which there is nothing to review.
export function actions(forge: Forge | null, available: ReadonlySet<string>, armed: string | null = null, pr: number | null = null): Action[] {
  const list: Action[] = [
    { key: 'status', label: 'Status', command: 'reflect', args: 'status' },
    { key: 'resume', label: 'Resume', command: 'reflect', args: 'resume' },
    { key: 'handoff', label: 'Handoff', command: 'reflect', args: 'handoff' },
  ]
  if (pr !== null) list.push({ key: 'review', label: `Review PR #${pr}`, command: 'pr-review-toolkit:review-pr', args: '' })
  if (forge?.next) {
    const epic = forge.next.epic
    const label = armed === epic ? `Confirm Run ${epic}?` : `Run ${epic}`
    list.push({ key: 'run', label, command: 'run-epic', args: epic, confirm: true })
  }
  // A button whose skill is not installed here would only fail on press.
  return list.filter(a => available.has(a.command))
}

export function summary(cache: Cache, contextTokens: number, forge: Forge | null): string {
  const parts = [`${cache.label} · ${tokens(contextTokens)} ctx`]
  if (forge) {
    if (forge.version) parts.unshift(`forge v${forge.version}`)
    parts.push(forge.next ? `next ${forge.next.id} (${forge.next.epic}) · ${forge.ready} ready` : 'no ready tasks')
    parts.push(`drift ${forge.drift < 0 ? '?' : forge.drift}`)
  }
  return parts.join(' │ ')
}
