# Multi-provider setup

Let `kadmon init` configure several providers at once, and add Grok.

## What changes for the user

Today init makes you pick one provider. That choice is also a lie: nothing reads
the file it writes, so the next run ignores your answer and uses Bedrock.

After this change:

- Init shows what it found on your machine and lets you **select several**
  providers, not one.
- The selection is saved and actually used.
- Config lives in one global place, so you set it up once, not per repo.
- Grok is one of the options.
- `kadmon --provider <name>` switches between configured providers. `/providers`
  lists them.

That is the whole feature.

## Config

```toml
# ~/.config/kadmon/config.toml
[providers.anthropic]
model = "claude-sonnet-4-6"
auth  = "env:ANTHROPIC_API_KEY"

[providers.grok]
model    = "grok-4"
base_url = "https://api.x.ai/v1"
auth     = "env:XAI_API_KEY"

default = "anthropic"
```

Secrets stay in env vars or `~/.config/kadmon/credentials.toml` (mode 0600),
never in `config.toml`.

Grok, Ollama, and OpenRouter all work by giving the existing `OpenAIProvider` a
`base_url`. One parameter, three providers.

## Testing plan

| Layer | What it covers |
|---|---|
| Unit | Config loads; several providers round-trip; missing key is a clear error; `base_url` reaches the client |
| Unit | Old single-provider config still loads, with its `[pricing]` preserved so `/cost` does not regress |
| Integration | Each configured provider answers a one-token prompt (mocked in CI, live behind a flag) |
| Manual | `kadmon init` on a machine with no keys, one key, and two keys |

Every provider construction site must go through the loader. There are six, and
two live outside `cli.py`: `SWEBenchRunner.run_instance` and
`PolyglotRunner._get_provider`. A test asserts no module builds a provider
directly.

## Cut

Subprocess providers wrapping `claude`/`grok` CLIs, cross-check and
`second_opinion`, delegate mode. All were built on the assumption that
subscription auth had to substitute for an API key. Not worth the machinery.

## Open question

You have no provider API keys on this machine. Multi-select is only useful once
at least one provider works — so this needs a key, or a running Ollama, before
it does anything for you.
