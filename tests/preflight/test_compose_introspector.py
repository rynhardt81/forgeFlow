"""Unit tests for compose_introspector — the T496 Compose-aware env rewrite.

Run:
    python3 -m unittest tests.preflight.test_compose_introspector
    python3 tests/preflight/test_compose_introspector.py
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "preflight"))

from compose_introspector import (  # noqa: E402
    _flatten_port_map,
    _parse_port_string,
    _rewrite_ports_in_value,
    discover_compose_file,
    discover_env_files,
    load_password_env,
    load_port_map,
    rewrite_env_for_compose,
)

FIXTURE_COMPOSE = (
    REPO_ROOT / "tests" / "preflight" / "fixtures" / "docker-compose.yml"
)


class TestParsePortString(unittest.TestCase):
    def test_bare_port(self):
        self.assertEqual(_parse_port_string("5432"), (5432, 5432))

    def test_host_container_form(self):
        self.assertEqual(_parse_port_string("5440:5432"), (5440, 5432))

    def test_ip_host_container_form(self):
        self.assertEqual(
            _parse_port_string("127.0.0.1:5440:5432"), (5440, 5432)
        )

    def test_long_form_dict(self):
        self.assertEqual(
            _parse_port_string({"published": 5440, "target": 5432}),
            (5440, 5432),
        )

    def test_int(self):
        self.assertEqual(_parse_port_string(5432), (5432, 5432))

    def test_garbage(self):
        self.assertIsNone(_parse_port_string("not-a-port"))
        self.assertIsNone(_parse_port_string(None))
        self.assertIsNone(_parse_port_string({"only": "this"}))

    def test_interpolated_default_ip_host_container(self):
        # The Codex-named case: `127.0.0.1:${POSTGRES_PORT:-5440}:5432`.
        # Without interpolation handling, the colon inside `${...}` shreds
        # the split and the parser collapses host:container to 5432:5432.
        self.assertEqual(
            _parse_port_string("127.0.0.1:${POSTGRES_PORT:-5440}:5432"),
            (5440, 5432),
        )

    def test_interpolated_default_host_container(self):
        self.assertEqual(
            _parse_port_string("${POSTGRES_PORT:-5440}:5432"),
            (5440, 5432),
        )

    def test_interpolated_default_posix_form(self):
        # POSIX-style `${VAR-default}` (no colon) — Compose accepts it too.
        self.assertEqual(
            _parse_port_string("${PG-5440}:5432"),
            (5440, 5432),
        )

    def test_interpolated_default_long_form_dict(self):
        self.assertEqual(
            _parse_port_string(
                {"published": "${POSTGRES_PORT:-5440}", "target": 5432}
            ),
            (5440, 5432),
        )

    def test_protocol_suffix_tcp(self):
        # T504: Compose port mappings can carry a `/tcp` / `/udp` / `/sctp`
        # protocol suffix. Pre-fix the parser only stripped numeric tokens
        # via `isdigit()`, so `5432/tcp` was rejected and the parser
        # collapsed host:container to (host, host).
        self.assertEqual(
            _parse_port_string("5440:5432/tcp"), (5440, 5432)
        )

    def test_protocol_suffix_udp(self):
        self.assertEqual(
            _parse_port_string("5440:5432/udp"), (5440, 5432)
        )

    def test_protocol_suffix_sctp(self):
        self.assertEqual(
            _parse_port_string("5440:5432/sctp"), (5440, 5432)
        )

    def test_protocol_suffix_with_ip_prefix(self):
        self.assertEqual(
            _parse_port_string("127.0.0.1:5440:5432/tcp"), (5440, 5432)
        )

    def test_protocol_suffix_with_interpolated_default(self):
        # The codex-named round-2 case: variable substitution + protocol
        # suffix on the same port mapping.
        self.assertEqual(
            _parse_port_string("${POSTGRES_PORT:-5440}:5432/tcp"),
            (5440, 5432),
        )

    def test_protocol_suffix_bare_port(self):
        # Single-port form with suffix: `5432/tcp` → both sides 5432.
        self.assertEqual(
            _parse_port_string("5432/tcp"), (5432, 5432)
        )

    def test_protocol_suffix_case_insensitive(self):
        # Compose lowercases the protocol internally via go-connections'
        # ParsePort, so `5432/TCP` and `5432/Tcp` are valid in compose
        # files. Strip case-insensitively to match.
        self.assertEqual(_parse_port_string("5440:5432/TCP"), (5440, 5432))
        self.assertEqual(_parse_port_string("5440:5432/Udp"), (5440, 5432))

    def test_unknown_protocol_suffix_returns_none(self):
        # Conservative: an unrecognised suffix (`/weirdsuffix`,
        # `/http`, anything not tcp/udp/sctp) returns None rather than
        # silently falling back to digit-filter parsing — that fallback
        # would collapse to (host, host), the exact silent-wrong-port
        # failure mode T500 / T504 exist to prevent.
        self.assertIsNone(_parse_port_string("5440:5432/weirdsuffix"))
        self.assertIsNone(_parse_port_string("5432/http"))

    def test_interpolated_no_default_drops(self):
        # `${VAR}` with no default leaves us nothing to rewrite to —
        # better to drop the mapping than rewrite to the wrong port.
        self.assertIsNone(
            _parse_port_string("127.0.0.1:${POSTGRES_PORT}:5432")
        )
        self.assertIsNone(
            _parse_port_string(
                {"published": "${POSTGRES_PORT}", "target": 5432}
            )
        )


class TestRewritePorts(unittest.TestCase):
    def test_rewrite_localhost_url(self):
        flat = {5432: 5440}
        self.assertEqual(
            _rewrite_ports_in_value(
                "postgresql://user:pw@localhost:5432/db", flat
            ),
            "postgresql://user:pw@localhost:5440/db",
        )

    def test_rewrite_127_0_0_1_url(self):
        flat = {5432: 5440}
        self.assertEqual(
            _rewrite_ports_in_value("redis://127.0.0.1:5432", flat),
            "redis://127.0.0.1:5440",
        )

    def test_does_not_touch_non_localhost(self):
        flat = {5432: 5440}
        self.assertEqual(
            _rewrite_ports_in_value(
                "postgresql://user:pw@db.prod.example.com:5432/db", flat
            ),
            "postgresql://user:pw@db.prod.example.com:5432/db",
        )

    def test_does_not_touch_unmapped_port(self):
        flat = {5432: 5440}
        # 6379 isn't in the map — leave it alone
        self.assertEqual(
            _rewrite_ports_in_value("redis://localhost:6379", flat),
            "redis://localhost:6379",
        )

    def test_multiple_urls_in_one_value(self):
        flat = {5432: 5440, 6379: 6390}
        self.assertEqual(
            _rewrite_ports_in_value(
                "db=localhost:5432 cache=localhost:6379", flat
            ),
            "db=localhost:5440 cache=localhost:6390",
        )


class TestFlattenPortMap(unittest.TestCase):
    def test_merges_services(self):
        self.assertEqual(
            _flatten_port_map(
                {"postgres": {5432: 5440}, "redis": {6379: 6390}}
            ),
            {5432: 5440, 6379: 6390},
        )

    def test_empty(self):
        self.assertEqual(_flatten_port_map({}), {})


class TestComposeFileLoaders(unittest.TestCase):
    """End-to-end against the committed fixture."""

    def test_load_port_map(self):
        port_map = load_port_map(FIXTURE_COMPOSE)
        self.assertEqual(port_map.get("postgres"), {5432: 5440})
        self.assertEqual(port_map.get("redis"), {6379: 6390})

    def test_load_password_env_detects_postgres_password(self):
        passwords = load_password_env(FIXTURE_COMPOSE)
        # POSTGRES_PASSWORD ends in PASSWORD → caught
        self.assertIn("POSTGRES_PASSWORD", passwords.get("postgres", set()))
        # REDIS_PASSWORD ends in PASSWORD → caught
        self.assertIn("REDIS_PASSWORD", passwords.get("redis", set()))


class TestLoadPasswordEnvListForm(unittest.TestCase):
    """T501: list-form `environment:` accepts bare-key entries.

    Compose accepts `- REDIS_PASSWORD` (bare key — passes the host env var
    through by reference) as well as `- REDIS_PASSWORD=value`. The bare
    form is exactly the one that NEEDS workflow env-ref substitution; an
    `=` filter that drops it is the bug.
    """

    def _write_compose(self, body: str) -> Path:
        import shutil
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        path = tmp / "docker-compose.yml"
        path.write_text(textwrap.dedent(body).lstrip())
        return path

    def test_bare_key_detected(self):
        compose = self._write_compose(
            """
            services:
              redis:
                image: redis:7
                environment:
                  - REDIS_PASSWORD
            """
        )
        passwords = load_password_env(compose)
        self.assertIn("REDIS_PASSWORD", passwords.get("redis", set()))

    def test_empty_value_form_detected(self):
        compose = self._write_compose(
            """
            services:
              redis:
                image: redis:7
                environment:
                  - REDIS_PASSWORD=
            """
        )
        passwords = load_password_env(compose)
        self.assertIn("REDIS_PASSWORD", passwords.get("redis", set()))

    def test_key_value_form_still_detected(self):
        # Regression guard for the form that already worked.
        compose = self._write_compose(
            """
            services:
              redis:
                image: redis:7
                environment:
                  - REDIS_PASSWORD=secret
            """
        )
        passwords = load_password_env(compose)
        self.assertIn("REDIS_PASSWORD", passwords.get("redis", set()))

    def test_non_password_bare_key_ignored(self):
        # The PASSWORD/PASSWD regex still gates — unrelated bare keys
        # don't leak into the password set.
        compose = self._write_compose(
            """
            services:
              app:
                image: app:1
                environment:
                  - NODE_ENV
                  - LOG_LEVEL=debug
            """
        )
        passwords = load_password_env(compose)
        self.assertEqual(passwords.get("app", set()), set())


class TestDiscoverComposeFile(unittest.TestCase):
    def test_finds_docker_compose_yml_at_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docker-compose.yml").write_text("services: {}\n")
            self.assertEqual(
                discover_compose_file(root), root / "docker-compose.yml"
            )

    def test_prefers_infrastructure_compose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docker-compose.yml").write_text("services: {}\n")
            (root / "infrastructure" / "compose").mkdir(parents=True)
            (root / "infrastructure" / "compose" / "docker-compose.yml").write_text(
                "services: {}\n"
            )
            self.assertEqual(
                discover_compose_file(root),
                root / "infrastructure" / "compose" / "docker-compose.yml",
            )

    def test_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(discover_compose_file(Path(tmp)))

    def test_pyproject_override_wins(self):
        # Consumer explicitly names a non-canonical Compose file —
        # discovery returns the override even when canonical files exist.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docker-compose.yml").write_text("services: {}\n")
            (root / "docker-compose.dev.yml").write_text("services: {}\n")
            (root / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.forge.preflight]
                compose_file = "docker-compose.dev.yml"
                """))
            self.assertEqual(
                discover_compose_file(root),
                (root / "docker-compose.dev.yml").resolve(),
            )

    def test_pyproject_override_for_nested_path(self):
        # Override resolves through subdirectories (monorepo layout).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deploy" / "compose").mkdir(parents=True)
            (root / "deploy" / "compose" / "stack.yml").write_text("services: {}\n")
            (root / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.forge.preflight]
                compose_file = "deploy/compose/stack.yml"
                """))
            self.assertEqual(
                discover_compose_file(root),
                (root / "deploy" / "compose" / "stack.yml").resolve(),
            )

    def test_pyproject_without_key_falls_through(self):
        # pyproject.toml exists but doesn't set our key → use canonical list.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docker-compose.yml").write_text("services: {}\n")
            (root / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.something-else]
                key = "value"
                """))
            self.assertEqual(
                discover_compose_file(root), root / "docker-compose.yml"
            )

    def test_pyproject_pointing_at_missing_file_falls_through(self):
        # User typo → fall through to canonical list rather than silently
        # returning None and surprising the dev with "no rewrite happened."
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docker-compose.yml").write_text("services: {}\n")
            (root / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.forge.preflight]
                compose_file = "does-not-exist.yml"
                """))
            self.assertEqual(
                discover_compose_file(root), root / "docker-compose.yml"
            )

    def test_pyproject_with_malformed_toml_falls_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docker-compose.yml").write_text("services: {}\n")
            (root / "pyproject.toml").write_text("not [ valid toml")
            self.assertEqual(
                discover_compose_file(root), root / "docker-compose.yml"
            )


class TestRewriteEnvForCompose(unittest.TestCase):
    """The user-facing transform: workflow env → Compose-aware env."""

    def setUp(self):
        # Canonical Compose-stack shape: postgres 5440→5432, redis 6390→6379.
        self.port_map = {
            "postgres": {5432: 5440},
            "redis": {6379: 6390},
        }
        self.password_env = {
            "postgres": {"POSTGRES_PASSWORD"},
            "redis": {"REDIS_PASSWORD"},
        }

    def test_rewrites_database_url_port(self):
        env = {
            "DATABASE_URL": "postgresql://app:pw@localhost:5432/app_test",
        }
        out = rewrite_env_for_compose(env, self.port_map, self.password_env)
        self.assertEqual(
            out["DATABASE_URL"],
            "postgresql://app:pw@localhost:5440/app_test",
        )

    def test_rewrites_redis_url_port(self):
        env = {"REDIS_URL": "redis://localhost:6379"}
        out = rewrite_env_for_compose(env, self.port_map, self.password_env)
        self.assertEqual(out["REDIS_URL"], "redis://localhost:6390")

    def test_empty_password_becomes_env_ref(self):
        env = {"REDIS_PASSWORD": ""}
        out = rewrite_env_for_compose(env, self.port_map, self.password_env)
        # Empty workflow default + Compose service declares the password →
        # emit a GHA template that the script_generator's existing rewrite
        # pass turns into bash `${REDIS_PASSWORD:-}` AND keeps unescaped.
        self.assertEqual(out["REDIS_PASSWORD"], "${{ env.REDIS_PASSWORD }}")

    def test_non_password_empty_stays_empty(self):
        env = {"SOME_FLAG": ""}
        out = rewrite_env_for_compose(env, self.port_map, self.password_env)
        self.assertEqual(out["SOME_FLAG"], "")

    def test_non_empty_password_passes_through(self):
        # If the workflow already sets a password (CI uses a real secret),
        # we don't touch it — only the empty-default case triggers the
        # env-ref substitution.
        env = {"REDIS_PASSWORD": "${CI_REDIS_PASSWORD:-default}"}
        out = rewrite_env_for_compose(env, self.port_map, self.password_env)
        self.assertEqual(out["REDIS_PASSWORD"], "${CI_REDIS_PASSWORD:-default}")

    def test_no_port_map_no_change(self):
        env = {"DATABASE_URL": "postgresql://x:y@localhost:5432/z"}
        out = rewrite_env_for_compose(env, {}, {})
        self.assertEqual(out, env)

    def test_does_not_mutate_input(self):
        env = {"DATABASE_URL": "postgresql://x:y@localhost:5432/z"}
        snapshot = dict(env)
        rewrite_env_for_compose(env, self.port_map, self.password_env)
        self.assertEqual(env, snapshot)

    def test_handles_full_consumer_env_block(self):
        """The canonical env shape: workflow targets localhost service-container
        ports + empty REDIS_PASSWORD default; introspector rewrites to host
        port + env-ref."""
        env = {
            "DATABASE_URL": "postgresql://app:ci_ephemeral_pw@localhost:5432/app_test",
            "TEST_DATABASE_URL": "postgresql://app:ci_ephemeral_pw@localhost:5432/app_test",
            "REDIS_HOST": "localhost",
            "REDIS_PASSWORD": "",
        }
        out = rewrite_env_for_compose(env, self.port_map, self.password_env)
        # Ports rewritten in URLs
        self.assertIn("localhost:5440", out["DATABASE_URL"])
        self.assertIn("localhost:5440", out["TEST_DATABASE_URL"])
        # REDIS_HOST has no port → untouched
        self.assertEqual(out["REDIS_HOST"], "localhost")
        # Empty REDIS_PASSWORD → GHA template (downstream rewrite in
        # script_generator turns it into bash `${REDIS_PASSWORD:-}` in
        # the generated script).
        self.assertEqual(out["REDIS_PASSWORD"], "${{ env.REDIS_PASSWORD }}")


class TestDiscoverEnvFiles(unittest.TestCase):
    """T497: ordered .env discovery for the generated script's source-block."""

    def test_finds_root_dot_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("POSTGRES_PASSWORD=x\n")
            # T499 added .resolve() to the discovery path for compose-
            # relative dedupe correctness — compare resolved paths.
            self.assertEqual(
                discover_env_files(root), [(root / ".env").resolve()]
            )

    def test_finds_compose_subdir_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "infrastructure" / "compose").mkdir(parents=True)
            (root / "infrastructure" / "compose" / ".env").write_text(
                "POSTGRES_PASSWORD=x\n"
            )
            self.assertEqual(
                discover_env_files(root),
                [(root / "infrastructure" / "compose" / ".env").resolve()],
            )

    def test_returns_both_in_layered_order_compose_first_root_last(self):
        # The canonical layered case: .env at root AND infrastructure/compose/.env.
        # T498: canonical order is base-first (Compose) / override-last
        # (root), so the generator emits a no-break source-loop and root
        # .env wins per-key over Compose values via bash last-export
        # semantics. Earlier T497 was first-found-wins, which silently
        # let a stale root .env shadow the installer-managed Compose .env.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("X=1\n")
            (root / "infrastructure" / "compose").mkdir(parents=True)
            (root / "infrastructure" / "compose" / ".env").write_text("Y=2\n")
            result = discover_env_files(root)
            self.assertEqual(len(result), 2)
            # Compose .env first (base layer) — paths are resolved
            # post-T499 for dedupe correctness.
            self.assertEqual(
                result[0],
                (root / "infrastructure" / "compose" / ".env").resolve(),
            )
            # Root .env last (optional override)
            self.assertEqual(result[1], (root / ".env").resolve())

    def test_empty_when_no_env_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(discover_env_files(Path(tmp)), [])

    def test_pyproject_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # canonical files exist
            (root / ".env").write_text("X=1\n")
            # override points elsewhere
            (root / "secrets" / "dev.env").parent.mkdir(parents=True)
            (root / "secrets" / "dev.env").write_text("Y=2\n")
            (root / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.forge.preflight]
                env_files = ["secrets/dev.env"]
                """))
            result = discover_env_files(root)
            self.assertEqual(
                result, [(root / "secrets" / "dev.env").resolve()]
            )

    def test_pyproject_override_with_multiple_files_preserves_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.env").write_text("X=1\n")
            (root / "b.env").write_text("Y=2\n")
            (root / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.forge.preflight]
                env_files = ["b.env", "a.env"]
                """))
            result = discover_env_files(root)
            self.assertEqual(
                [p.name for p in result], ["b.env", "a.env"]
            )

    def test_compose_relative_env_picked_up_for_non_canonical_layout(self):
        # T499: a project whose compose file lives outside the canonical
        # list (e.g. `deploy/compose/dev.yml`) — the .env next to that
        # compose file is auto-discovered. No pyproject.toml needed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deploy" / "compose").mkdir(parents=True)
            (root / "deploy" / "compose" / "dev.yml").write_text("services: {}\n")
            (root / "deploy" / "compose" / ".env").write_text("X=1\n")
            result = discover_env_files(
                root, compose_file=root / "deploy" / "compose" / "dev.yml"
            )
            self.assertEqual(
                result, [(root / "deploy" / "compose" / ".env").resolve()]
            )

    def test_compose_relative_layered_before_root_env(self):
        # T499: compose-relative .env is base layer, root .env is the
        # override. Both contribute when both exist; root wins per-key
        # via bash last-export semantics at script-run time.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deploy" / "compose").mkdir(parents=True)
            (root / "deploy" / "compose" / "dev.yml").write_text("services: {}\n")
            (root / "deploy" / "compose" / ".env").write_text("X=base\n")
            (root / ".env").write_text("X=override\n")
            result = discover_env_files(
                root, compose_file=root / "deploy" / "compose" / "dev.yml"
            )
            self.assertEqual(len(result), 2)
            # Compose-relative first (base)
            self.assertEqual(
                result[0], (root / "deploy" / "compose" / ".env").resolve()
            )
            # Root .env last (override)
            self.assertEqual(result[1], (root / ".env").resolve())

    def test_compose_relative_dedupes_against_canonical(self):
        # When compose_file IS at the canonical path
        # (infrastructure/compose/docker-compose.yml), the compose-
        # relative .env is the same file as the canonical entry — no
        # double-source.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "infrastructure" / "compose").mkdir(parents=True)
            (root / "infrastructure" / "compose" / "docker-compose.yml").write_text(
                "services: {}\n"
            )
            (root / "infrastructure" / "compose" / ".env").write_text("X=1\n")
            result = discover_env_files(
                root,
                compose_file=root / "infrastructure" / "compose" / "docker-compose.yml",
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(
                result[0], (root / "infrastructure" / "compose" / ".env").resolve()
            )

    def test_compose_relative_skipped_when_no_compose_file(self):
        # No compose_file arg → behaves exactly as the canonical-list-only
        # discovery did before T499. Backwards-compat.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("X=1\n")
            self.assertEqual(discover_env_files(root), [(root / ".env").resolve()])
            self.assertEqual(
                discover_env_files(root, compose_file=None),
                [(root / ".env").resolve()],
            )

    def test_pyproject_override_drops_missing_paths(self):
        # Typo in pyproject → skip the missing path, keep real ones.
        # Returns None internally when nothing resolves, which makes
        # discover_env_files fall through to the canonical list.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("X=1\n")
            (root / "pyproject.toml").write_text(textwrap.dedent("""\
                [tool.forge.preflight]
                env_files = ["does-not-exist.env"]
                """))
            # Fall-through to canonical list, NOT silent empty result.
            result = discover_env_files(root)
            self.assertEqual(result, [(root / ".env").resolve()])


class TestUnparseableCompose(unittest.TestCase):
    """Bad input should fall through to no-op, not crash."""

    def test_bad_yaml_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(": this : is : not : yaml :")
            path = Path(f.name)
        try:
            self.assertEqual(load_port_map(path), {})
            self.assertEqual(load_password_env(path), {})
        finally:
            path.unlink()

    def test_no_services_key_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(textwrap.dedent("""\
                version: "3"
                volumes:
                  data: {}
                """))
            path = Path(f.name)
        try:
            self.assertEqual(load_port_map(path), {})
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
