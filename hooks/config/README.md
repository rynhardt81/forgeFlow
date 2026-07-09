# Hook Configuration Files

Configuration consumed by hook validators. One rule: a config file in this directory must have code that reads it — configuration nothing parses is documentation in disguise, and gets deleted.

## Files

| File | Purpose | Consumed by |
|------|---------|-------------|
| `secret-patterns.yaml` | Secret detection patterns | `validators/agents/security_secrets.py` |
| `README.md` | This documentation | — |

## secret-patterns.yaml

Secret detection patterns used by the security validator. Advisory (never blocks).

### Sections

| Section | Purpose |
|---------|---------|
| `secret_patterns` | Regex patterns for API keys, tokens, passwords |
| `allowed_file_patterns` | Files that can contain example secrets |
| `scan_extensions` | File extensions to scan |

### Example Pattern

```yaml
secret_patterns:
  - name: "OpenAI API key"
    pattern: 'sk-[a-zA-Z0-9]{32,}'
    severity: critical
```

## See Also

- [hooks/README.md](../README.md) - Hook system documentation
