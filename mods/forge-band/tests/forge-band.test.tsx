import { expect, test } from 'claude-code/testing'

import { actions, cacheState, CACHE_TTL_MS, parseForge, parsePr } from '../hooks/band'

const READY = JSON.stringify([
  { id: 'T313', epic: 'E16' },
  { id: 'T314', epic: 'E16' },
])
const CLEAN = JSON.stringify({ findings: [] })
const ALL = new Set(['reflect', 'run-epic', 'pr-review-toolkit:review-pr'])

test('cache countdown: gray before a reply, green, red near expiry, cold after', async () => {
  expect(cacheState(0, 1000).color).toBe('gray')
  expect(cacheState(1000, 1000 + 10 * 60000).label).toBe('cache 50m left')
  expect(cacheState(1000, 1000 + 50 * 60000).color).toBe('yellow')
  expect(cacheState(1000, 1000 + 56 * 60000).color).toBe('red')
  expect(cacheState(1000, 1000 + CACHE_TTL_MS).label).toBe('cache cold')
})

test('parseForge: next task is the first ready one; unreadable drift is -1', async () => {
  expect(parseForge(READY, CLEAN, '4.8.0\n')).toEqual({ next: { id: 'T313', epic: 'E16' }, ready: 2, drift: 0, version: '4.8.0' })
  expect(parseForge('[]', 'not json', 'unknown (VERSION file not found — pre-4.2 install?)')).toEqual({ next: null, ready: 0, drift: -1, version: null })
})

test('Review PR shows only for an open PR, and only with the plugin installed', async () => {
  expect(parsePr(0, '{"number":89,"state":"OPEN"}')).toBe(89)
  expect(parsePr(0, '{"number":88,"state":"MERGED"}')).toBeNull()
  expect(parsePr(1, 'no pull requests found for branch "main"')).toBeNull()
  expect(actions(null, ALL, null, 89).at(-1)?.label).toBe('Review PR #89')
  expect(actions(null, ALL, null, null).map(a => a.key)).not.toContain('review')
  expect(actions(null, new Set(['reflect']), null, 89).map(a => a.key)).not.toContain('review')
})

test('the Run button exists only when a task is ready', async () => {
  expect(actions(null, new Set(['run-epic']))).toEqual([])
  expect(actions(null, ALL).map(a => a.key)).toEqual(['status', 'resume', 'handoff'])
  expect(actions(parseForge(READY, CLEAN), ALL).at(-1)).toEqual({
    key: 'run', label: 'Run E16', command: 'run-epic', args: 'E16', confirm: true,
  })
  expect(actions(parseForge(READY, CLEAN), ALL, 'E16').at(-1)?.label).toBe('Confirm Run E16?')
})

test('band shows the next task; Run needs a confirming second press', async ($, on) => {
  on('process.run', async (_$, e) => {
    const script = e.argv[1] ?? ''
    if (e.argv[0] === 'gh') return { value: { exitCode: 0, stdout: '{"number":89,"state":"OPEN"}', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    const stdout = e.argv[2] === 'version' ? '4.8.0\n' : script.endsWith("forge.py") ? READY : CLEAN
    const run = { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false }
    return { value: run }
  })
  const ran: string[] = []
  on('command.run', async (_$, e) => {
    ran.push(`${e.command} ${e.args ?? ''}`.trim())
    return { text: '' }
  })

  on('command.register', async () => ({ value: undefined }) as never)
  on('session.start', async (_$, e) => e as never)
  on('command.list', async () => ({ value: [{ name: 'reflect' }, { name: 'run-epic' }, { name: 'pr-review-toolkit:review-pr' }] }) as never)
  on("clock.every", async () => ({ value: undefined }) as never)
  on("clock.now", async () => ({ value: 1000 }) as never)
  on("clock.after", async () => ({ deny: "timer held: the confirm window stays open" }) as never)
  await $.session.start({ source: 'startup', cwd: '/repo' } as never)

  const text = (await $.command.run({ command: 'forge-band', args: '' } as never)).text
  expect(text).toContain('next T313 (E16) · 2 ready')
  expect(text).toContain('drift 0')
  expect(text).toContain('forge v4.8.0')
  expect(text).toContain('/pr-review-toolkit:review-pr')

  const band = await $.ui.mount({ plugin: 'forge-band', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false } as never })
  expect(JSON.stringify(await band.drawn())).toContain('"borderStyle":"round"')
  expect(await band.find({ type: 'Text', text: '◆ forge' })).toBeDefined()
  expect(await band.find({ type: 'Text', text: 'T313' })).toBeDefined()
  expect(JSON.stringify(await band.drawn())).toContain('4.8.0')
  expect(await band.find({ type: 'Text', text: '✓ in sync' })).toBeDefined()
  // the Desktop app's table must accept the same tree
  await $.ui.mount({ plugin: 'forge-band', surface: 'desktop', component: 'AbovePrompt', props: { hasSurvey: false } as never })
  await band.press({ key: 'run' })
  expect(ran).not.toContain('run-epic E16') // first press only arms
  expect(await band.find({ key: 'run', text: 'Confirm Run E16?' })).toBeDefined()
  await band.press({ key: 'run' })
  expect(ran).toContain('run-epic E16')
})
