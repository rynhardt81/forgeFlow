export type NextTask = { id: string; epic: string }

export type Forge = {
  // null when the session's directory is not a Forge Flow project
  next: NextTask | null
  ready: number
  drift: number
  // installed Forge Flow version, e.g. "4.8.0"; null when VERSION is missing
  version: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'forge-band': {
      // ms since epoch of the last main-thread model response; 0 before the first
      lastResponseAt: number
      contextTokens: number
      forge: Forge | null
      hidden: boolean
      warned: boolean
      // epic whose Run button awaits its confirming second press
      armed: string | null
    }
  }
}
