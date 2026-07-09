"""Parse a project's Compose file and rewrite workflow env values to match.

Why this exists
---------------
GitHub Actions runs job env values like

    DATABASE_URL=postgresql://user:pw@localhost:5432/db

against service containers that GHA wires onto the runner's `localhost` at
the requested container port. On a developer machine running the project's
own `docker-compose.yml`, Compose usually publishes services on a non-default
host port (`5440 -> 5432` for Postgres) to avoid colliding with a host-local
install. The preflight generator's job is to make `.forge/preflight/*.sh`
work against the dev's running Compose stack — so the literal `:5432` in
the workflow needs to become `:5440` in the generated script.

Same shape for unauthenticated CI Redis vs. password-protected local Redis:
the workflow's `REDIS_PASSWORD=""` has to become `${REDIS_PASSWORD:-}` (an
env-var reference the dev exports from their .env), NOT inlined with the
literal Compose value — generated scripts stay gitleaks-safe.

Discovery order:
    0. pyproject.toml `[tool.forge.preflight] compose_file = "..."` (escape hatch)
    1. infrastructure/compose/docker-compose.yml
    2. docker-compose.yml
    3. compose.yaml
    4. compose.yml
No Compose found → no rewrite (callers fall through to current behaviour).

Public API:
    discover_compose_file(project_root: Path) -> Path | None
    load_port_map(compose_file: Path) -> dict[str, dict[int, int]]
        service_name -> {container_port: host_port}
    load_password_env(compose_file: Path) -> dict[str, set[str]]
        service_name -> {env var names that look like passwords}
    rewrite_env_for_compose(env, port_map, password_env) -> dict[str, str]
        the actual transform applied to a Job.env dict
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Compose file discovery: first hit wins. infrastructure/compose/
# docker-compose.yml covers projects that namespace their stack under
# infrastructure/; the other three are the vanilla Compose defaults.
COMPOSE_CANDIDATES = (
    Path("infrastructure/compose/docker-compose.yml"),
    Path("docker-compose.yml"),
    Path("compose.yaml"),
    Path("compose.yml"),
)

# Env-file candidates in layered-merge order (base first, override last).
# The generated script sources every existing file in this order via
# `set -a; . file; set +a` so the last layer wins per bash export
# semantics. Compose-installed `.env` is the base (installer-managed,
# matches the running containers); root `.env` is the optional override
# (user-managed, often has additional customisations or — when stale —
# placeholder values that should NOT silently win over Compose's real
# values). T498 reversed this from T497's first-found-wins after a
# consumer hit "stale root `.env` shadows real Compose values."
# Same gitleaks-safety as COMPOSE_CANDIDATES — generator never reads
# secrets, only embeds paths the dev's machine loads at script-run time.
ENV_FILE_CANDIDATES = (
    Path("infrastructure/compose/.env"),
    Path("compose/.env"),
    Path(".env"),
)

# Hostname/scheme → expected Compose service name. CI workflows speak to
# services by hostname (`@localhost:5432`, `REDIS_HOST=localhost`); Compose
# files name them (`postgres:`, `redis:`). We bridge the two by recognizing
# the container port + scheme.
#
# Maps (default container port) → service-name hints. The Compose service's
# *actual* name doesn't have to be one of these — we use the port to find it.
PASSWORD_VAR_RE = re.compile(r"PASSWORD$|PASSWD$", re.IGNORECASE)


def _read_pyproject_compose_override(project_root: Path) -> Path | None:
    """Return the Compose path from `pyproject.toml [tool.forge.preflight] compose_file`.

    Escape hatch for consumers whose dev Compose lives outside the four
    canonical locations (e.g. `docker-compose.dev.yml`, monorepo layouts
    with the stack pinned under a subdirectory). Returns None if
    pyproject.toml is missing, the key is absent, or the path doesn't
    resolve to a real file — callers fall through to the discovery list.

    Path is resolved relative to project_root.
    """
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        import tomllib  # stdlib >= 3.11
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, ValueError):
        return None
    try:
        rel = data["tool"]["forge"]["preflight"]["compose_file"]
    except (KeyError, TypeError):
        return None
    if not isinstance(rel, str) or not rel:
        return None
    candidate = (project_root / rel).resolve()
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def discover_compose_file(project_root: Path) -> Path | None:
    """Return the first Compose file found relative to project_root.

    The pyproject.toml override takes precedence over the canonical
    discovery list — a consumer that explicitly names a Compose file
    expects that one to win.
    """
    override = _read_pyproject_compose_override(project_root)
    if override is not None:
        return override
    for rel in COMPOSE_CANDIDATES:
        candidate = project_root / rel
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _read_pyproject_env_files_override(project_root: Path) -> list[Path] | None:
    """Return env-file paths from `pyproject.toml [tool.forge.preflight] env_files`.

    Symmetry with the compose_file override — consumers whose env files
    live outside the canonical locations can opt in. Order in the list
    is preserved and interpreted as base-first / override-last (T498):
    the generator sources every existing file in this order at script-
    run time, last layer wins per bash export semantics. Returns None
    when the file is missing, the key is absent, or the value isn't a
    list of strings; callers fall through to ENV_FILE_CANDIDATES.

    Paths in the list that don't resolve to a real file are silently
    dropped — typo-safe rather than failing the whole generation step.
    """
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, ValueError):
        return None
    try:
        items = data["tool"]["forge"]["preflight"]["env_files"]
    except (KeyError, TypeError):
        return None
    if not isinstance(items, list):
        return None
    resolved: list[Path] = []
    for entry in items:
        if not isinstance(entry, str) or not entry:
            continue
        candidate = (project_root / entry).resolve()
        if candidate.exists() and candidate.is_file():
            resolved.append(candidate)
    return resolved or None


def discover_env_files(
    project_root: Path,
    compose_file: Path | None = None,
) -> list[Path]:
    """Return ordered list of existing .env files for layered sourcing.

    First the pyproject.toml override (if present and resolves), otherwise
    the canonical list (Compose-subdir `.env` → root `.env`). Order is
    base-first / override-last — the generated script sources every
    existing file in this order via `set -a` / `. file` / `set +a`, so
    later layers override earlier ones via bash last-export-wins
    semantics.

    `compose_file` (optional): when supplied, the .env next to that
    compose file (Compose's own convention) is added between the canonical
    Compose-subdir candidates and the root .env. Catches projects whose
    Compose file lives in a non-canonical location (`deploy/compose/dev.yml`,
    monorepo subpaths) without needing a pyproject.toml opt-in. Duplicates
    against the canonical list are skipped, so no double-source when the
    compose file is already at one of the canonical paths.

    Returns an empty list when no env file is found. The generator still
    emits the source-block (acceptance criterion: "if no .env is present,
    script still runs"), the loop just exits with nothing sourced and
    the env-refs resolve empty.
    """
    override = _read_pyproject_env_files_override(project_root)
    if override is not None:
        return override

    # Layer 1: Compose-canonical base layers + compose-relative.
    # Insertion order: Compose-canonical entries from ENV_FILE_CANDIDATES
    # (excluding root `.env`), then the .env next to compose_file (if any
    # and not already covered), then root `.env`. This keeps the base-first
    # / override-last semantic intact: any installer-managed Compose `.env`
    # comes before the user-managed root override.
    found: list[Path] = []
    seen: set[Path] = set()

    for rel in ENV_FILE_CANDIDATES:
        if rel == Path(".env"):
            # root .env is appended last (override layer) — defer
            continue
        candidate = (project_root / rel).resolve()
        if candidate.exists() and candidate.is_file() and candidate not in seen:
            found.append(candidate)
            seen.add(candidate)

    if compose_file is not None:
        compose_relative = (compose_file.parent / ".env").resolve()
        if (
            compose_relative.exists()
            and compose_relative.is_file()
            and compose_relative not in seen
        ):
            found.append(compose_relative)
            seen.add(compose_relative)

    root_env = (project_root / ".env").resolve()
    if root_env.exists() and root_env.is_file() and root_env not in seen:
        found.append(root_env)

    return found


# `${VAR:-default}` or `${VAR-default}` — Compose-style env interpolation
# in port values. We extract the default literal so the generator can
# produce a working `localhost:HOST` rewrite. Caveat: if the dev's .env
# overrides VAR to something other than the default, the rewrite still
# uses the default (mismatch with the actually-published port). The
# fully correct fix is to emit `localhost:${VAR:-default}` into the
# generated script and let bash resolve it at script-run time; that's
# expanded scope and waits for a real consumer hit.
_INTERPOLATION_DEFAULT_RE = re.compile(
    r"\$\{[A-Za-z_][A-Za-z0-9_]*:?-([^}]+)\}"
)


# Recognised protocol suffixes per docker/go-connections `ParsePort`,
# which Compose calls when validating port entries. Compose lowercases
# the suffix internally, so `/TCP` and `/Tcp` are valid in compose
# files — we match case-insensitively.
_PROTOCOL_SUFFIX_RE = re.compile(r"/(tcp|udp|sctp)$", re.IGNORECASE)


def _strip_protocol_suffix(token: str) -> str | None:
    """Strip Compose's `/tcp` / `/udp` / `/sctp` protocol suffix.

    Compose accepts `5432/tcp`, `5440:5432/udp`, `${PG:-5440}:5432/sctp`.
    The suffix is metadata about the socket type — the host/container
    port semantic is unchanged, and the rewrite layer doesn't care
    about the protocol (we only rewrite URL ports, not transport).
    Strip it before any digit-parsing so port detection works for the
    suffixed forms.

    Returns the suffix-stripped token, or `None` if the token contains
    a `/` followed by something other than a known protocol. The
    None-return signals to the caller "unrecognised — don't fall back
    to digit-filter parsing, which would collapse to a wrong-but-
    plausible mapping" (consistent with T500's no-silent-wrong principle).
    """
    if "/" not in token:
        return token
    m = _PROTOCOL_SUFFIX_RE.search(token)
    if m is None:
        return None
    return token[: m.start()]


def _resolve_compose_int(value: Any) -> int | None:
    """Coerce a Compose port-position value to int.

    Accepts bare ints, all-digit strings, and `${VAR:-N}` / `${VAR-N}`
    interpolations with a numeric default. Tolerates a `/tcp` / `/udp`
    / `/sctp` protocol suffix. Returns None for anything else (bare
    `${VAR}` with no default, `${VAR:?required}`, garbage).
    """
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    s = _strip_protocol_suffix(value.strip())
    if s is None:
        return None
    if s.isdigit():
        return int(s)
    m = _INTERPOLATION_DEFAULT_RE.fullmatch(s)
    if m and m.group(1).isdigit():
        return int(m.group(1))
    return None


def _parse_port_string(value: Any) -> tuple[int, int] | None:
    """Compose port forms: '5432', '5440:5432', '127.0.0.1:5440:5432',
    or the long form dict `{published: 5440, target: 5432}`. Also
    handles `${VAR:-N}` / `${VAR-N}` interpolation in any position by
    substituting the default literal before splitting.

    Returns (host_port, container_port) or None if unrecognizable.
    """
    if isinstance(value, dict):
        host = _resolve_compose_int(value.get("published"))
        container = _resolve_compose_int(value.get("target"))
        if host is None or container is None:
            return None
        return host, container
    if isinstance(value, int):
        return value, value
    if not isinstance(value, str):
        return None
    # Substitute `${VAR:-N}` → `N` before splitting on ':' — the
    # interpolation itself contains a colon and would otherwise shred
    # the split (e.g. `127.0.0.1:${PG:-5440}:5432` splits to 4 parts
    # with only one all-digit segment).
    expanded = _INTERPOLATION_DEFAULT_RE.sub(
        lambda m: m.group(1) if m.group(1).isdigit() else "",
        value,
    )
    # Any remaining `${...}` is an interpolation we couldn't resolve
    # (no default, `:?` required, non-numeric default). Returning a
    # mapping that ignores it would silently rewrite to the wrong port.
    if "${" in expanded:
        return None
    # Strip `/tcp` / `/udp` / `/sctp` — the protocol suffix only appears
    # on the container-side token but stripping at the whole-string
    # level is equivalent (it's always the last token of the split) and
    # keeps the split logic simple. An unknown suffix (e.g. `/weirdsuffix`)
    # returns None — better than falling back to digit-filter parsing
    # that would collapse to (host, host) silently.
    expanded = _strip_protocol_suffix(expanded)
    if expanded is None:
        return None
    parts = expanded.split(":")
    nums = [p for p in parts if p.isdigit()]
    if len(nums) == 1:
        # "5432" — both sides are the same port
        p = int(nums[0])
        return p, p
    if len(nums) >= 2:
        # "5440:5432" or "127.0.0.1:5440:5432" → last two are host:container
        try:
            return int(nums[-2]), int(nums[-1])
        except ValueError:
            return None
    return None


def load_port_map(compose_file: Path) -> dict[str, dict[int, int]]:
    """Return {service_name: {container_port: host_port}}.

    Empty dict if the Compose file is unparseable or has no services.
    """
    try:
        import yaml  # lazy: only when we actually do introspection
    except ImportError:
        return {}
    try:
        raw = yaml.safe_load(compose_file.read_text())
    except yaml.YAMLError:
        return {}
    if not isinstance(raw, dict):
        return {}
    services = raw.get("services") or {}
    if not isinstance(services, dict):
        return {}
    out: dict[str, dict[int, int]] = {}
    for name, body in services.items():
        if not isinstance(body, dict):
            continue
        ports = body.get("ports") or []
        if not isinstance(ports, list):
            continue
        mapping: dict[int, int] = {}
        for p in ports:
            parsed = _parse_port_string(p)
            if parsed is None:
                continue
            host, container = parsed
            mapping[container] = host
        if mapping:
            out[str(name)] = mapping
    return out


def load_password_env(compose_file: Path) -> dict[str, set[str]]:
    """Return {service_name: {env var names that look like passwords}}.

    Looks at the service's `environment:` block for any `*_PASSWORD` /
    `*_PASSWD` keys. Used to decide when an empty workflow default
    (`REDIS_PASSWORD=""`) should become an env-var reference vs. stay empty.
    """
    try:
        import yaml
    except ImportError:
        return {}
    try:
        raw = yaml.safe_load(compose_file.read_text())
    except yaml.YAMLError:
        return {}
    if not isinstance(raw, dict):
        return {}
    services = raw.get("services") or {}
    if not isinstance(services, dict):
        return {}
    out: dict[str, set[str]] = {}
    for name, body in services.items():
        if not isinstance(body, dict):
            continue
        env = body.get("environment")
        keys: set[str] = set()
        if isinstance(env, dict):
            for key in env.keys():
                if PASSWORD_VAR_RE.search(str(key)):
                    keys.add(str(key))
        elif isinstance(env, list):
            for entry in env:
                if not isinstance(entry, str):
                    continue
                # Compose accepts both `KEY=value` and bare `KEY` (the
                # latter passes through the host env var by reference).
                # Bare-key entries are the ones that NEED env-ref
                # substitution in the workflow — dropping them on the
                # `=` filter is the bug T501 fixed.
                key = entry.split("=", 1)[0] if "=" in entry else entry
                if PASSWORD_VAR_RE.search(key):
                    keys.add(key)
        if keys:
            out[str(name)] = keys
    return out


# URL patterns we know how to rewrite. Anchored on `localhost` and
# `127.0.0.1` only — we don't touch values pointing at other hostnames.
_URL_PORT_RE = re.compile(
    r"(?P<host>localhost|127\.0\.0\.1):(?P<port>\d+)"
)


def _rewrite_ports_in_value(
    value: str, container_to_host: dict[int, int]
) -> str:
    """Substitute every `localhost:CONTAINER` with `localhost:HOST`.

    We anchor on `localhost`/`127.0.0.1` to avoid rewriting unrelated
    `:5432` substrings (e.g. a path component, version tag, etc).
    """

    def _sub(m: re.Match) -> str:
        host = m.group("host")
        port = int(m.group("port"))
        new_port = container_to_host.get(port, port)
        return f"{host}:{new_port}"

    return _URL_PORT_RE.sub(_sub, value)


def _flatten_port_map(
    port_map: dict[str, dict[int, int]],
) -> dict[int, int]:
    """Merge every service's container→host port mapping into one dict.

    Conflicts (two services both mapping container port 5432) are resolved
    last-wins; in practice the Compose services we care about (postgres,
    redis) have distinct container ports.
    """
    flat: dict[int, int] = {}
    for service_ports in port_map.values():
        for container, host in service_ports.items():
            flat[container] = host
    return flat


def rewrite_env_for_compose(
    env: dict[str, str],
    port_map: dict[str, dict[int, int]],
    password_env: dict[str, set[str]],
) -> dict[str, str]:
    """Apply Compose-aware rewrites to a workflow env dict.

    1. For every value, rewrite `localhost:CONTAINER` → `localhost:HOST`
       using the merged Compose port map.
    2. For every empty value whose KEY matches a `*_PASSWORD` env name
       declared in any Compose service's `environment:`, replace `""` with
       a GHA-template ref (`${{ env.KEY }}`). The existing
       `_rewrite_actions_templates` pass in script_generator turns that
       into bash `${KEY:-}` AND skips the `$`-escape path — so the dev's
       `.env`-exported value resolves at run time. Never inline the
       literal Compose value (generated scripts must stay gitleaks-safe).

    Returns a new dict; does not mutate input.
    """
    if not port_map and not password_env:
        return dict(env)

    flat_ports = _flatten_port_map(port_map)
    known_password_keys: set[str] = set()
    for keys in password_env.values():
        known_password_keys.update(keys)

    out: dict[str, str] = {}
    for k, v in env.items():
        sv = str(v) if v is not None else ""
        if flat_ports:
            sv = _rewrite_ports_in_value(sv, flat_ports)
        if sv == "" and k in known_password_keys:
            sv = "${{ env." + k + " }}"
        out[k] = sv
    return out
