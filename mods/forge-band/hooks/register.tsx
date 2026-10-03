import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { actions, cacheState, CONFIRM_MS, LAYOUTS, parseForge, summary, tokens, WARN_MS } from './band'
import type { Forge } from '../types'

const lastResponseAt = atom({ plugin: 'forge-band', key: 'lastResponseAt' } as const, 0)
const contextTokens = atom({ plugin: 'forge-band', key: 'contextTokens' } as const, 0)
const forgeState = atom({ plugin: 'forge-band', key: 'forge' } as const, null)
const hidden = atom({ plugin: 'forge-band', key: 'hidden' } as const, false)
const warned = atom({ plugin: 'forge-band', key: 'warned' } as const, false)
const armed = atom({ plugin: 'forge-band', key: 'armed' } as const, null)

// Slash commands this session can run; reset with the module, refilled in session.start.
let available: ReadonlySet<string> = new Set()

// Reads the task queue and registry drift through Forge Flow's own CLI.
// Returns null outside a Forge Flow project, so the band shows the cache alone.
async function loadForge($: EngineInterface): Promise<Forge | null> {
  for (const root of LAYOUTS) {
    const ready = await $.process.run(['python3', `${root}scripts/forge/forge.py`, 'task', 'ls', '--ready', '--json'])
    if (ready.exitCode !== 0) continue
    const drift = await $.process.run(['python3', `${root}hooks/forge/consistency-banner.py`, '--json'], { stdin: '' })
    const version = await $.process.run(['python3', `${root}scripts/forge/forge.py`, 'version'])
    return parseForge(ready.stdout, drift.stdout, version.stdout)
  }
  return null
}

async function refresh($: EngineInterface) {
  const forge = await loadForge($).catch(() => null)
  await update($, forgeState, () => forge)
}

async function stamp($: EngineInterface) {
  const now = await $.clock.now()
  await update($, lastResponseAt, () => now)
  await update($, warned, () => false)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'forge-band', description: 'Print the forge band as text; "show" unhides it' })
    available = new Set((await $.command.list()).map(c => c.name))
    void refresh($)
    // Redraw the countdown, and warn once when the cache is about to lapse.
    $.clock.every(30_000, async () => {
      const cache = cacheState(await read($, lastResponseAt), await $.clock.now())
      if (cache.leftMs > 0 && cache.leftMs <= WARN_MS && !(await read($, warned))) {
        await update($, warned, () => true)
        $.ui.toast(`Prompt cache expires in ${Math.ceil(cache.leftMs / 60000)}m. Handoff now, or the next turn re-sends the whole context.`)
      }
      $.ui.invalidate('ui.render')
    })
    return next(e)
  })

  // Fires when the main thread's context fill moves, i.e. after each model response.
  on('session.measure', async ($, e, next) => {
    if (e.context.tokens) {
      await update($, contextTokens, () => e.context.tokens ?? 0)
      await stamp($)
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (!e.agentId) void refresh($)
    return result
  })

  on('command.run', { command: 'forge-band' }, async ($, e) => {
    if (e.args.trim() === 'show') await update($, hidden, () => false)
    await refresh($)
    const forge = await read($, forgeState)
    const line = summary(cacheState(await read($, lastResponseAt), await $.clock.now()), await read($, contextTokens), forge)
    const buttons = actions(forge, available).map(a => `/${a.command} ${a.args}`).join(', ')
    return { text: `${line}\nbuttons: ${buttons}` }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || (await read($, hidden))) return next(e)

    const { Box, Button, Text } = $.ui.resolve(e)
    const forge = await read($, forgeState)
    const cache = cacheState(await read($, lastResponseAt), await $.clock.now())
    const ctx = tokens(await read($, contextTokens))

    return (
      <Box borderStyle="round" borderColor="cyan" paddingX={1} flexDirection="row" flexWrap="wrap" justifyContent="space-between" columnGap={3}>
        <Box flexDirection="row" flexWrap="wrap" columnGap={3}>
          <Text>
            <Text bold color="cyan">◆ forge</Text>
            {forge?.version && <Text dimColor> v{forge.version}</Text>}
          </Text>
          <Text>
            <Text color={cache.color}>● </Text>
            <Text>{cache.label.replace('cache ', '')}</Text>
            <Text dimColor> cache · {ctx} ctx</Text>
          </Text>
          {forge && (
            <Text>
              <Text color="cyan">▸ </Text>
              {forge.next ? <Text bold>{forge.next.id}</Text> : <Text dimColor>no ready tasks</Text>}
              {forge.next && <Text dimColor> · {forge.next.epic} · {forge.ready} ready</Text>}
            </Text>
          )}
          {forge && (forge.drift === 0
            ? <Text color="green">✓ in sync</Text>
            : <Text color="yellow">⚠ {forge.drift < 0 ? 'drift ?' : `${forge.drift} drift`}</Text>)}
        </Box>
        <Box flexDirection="row" columnGap={1}>
          {actions(forge, available, await read($, armed)).map(a => (
            <Button
              key={a.key}
              label={a.label}
              onPress={async () => {
                if (a.confirm && (await read($, armed)) !== a.args) {
                  await update($, armed, () => a.args)
                  $.clock.after(CONFIRM_MS, () => update($, armed, () => null))
                  return
                }
                await update($, armed, () => null)
                await $.command.run({ command: a.command, args: a.args }).catch(err => $.ui.toast(`/${a.command} ${a.args}: ${err}`))
              }}
            />
          ))}
          <Button key="hide" label="×" plain dimColor onPress={() => update($, hidden, () => true)} />
        </Box>
      </Box>
    )
  })
}
