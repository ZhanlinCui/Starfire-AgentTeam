# Plugin install sources

> **TL;DR** — plugin **sources** (where a plugin comes from) and plugin
> **shapes** (what's inside it) are independent axes. Both are pluggable.
> Today we ship two sources (`local`, `github`) and one shape adapter
> (`AgentskillsAdaptor`). Both layers scale the same way: write one new
> class, register it, done.

## The two axes

```
┌──────────────────────────────────────────────┐
│ SOURCE — where we fetch the plugin from      │
│                                              │
│   local://my-plugin                          │
│   github://owner/repo#v1.0                   │
│   clawhub://name@1.2                         │
│   https://example.com/plugin.tgz             │
│                                              │
│   registered via plugins.Registry            │
└──────────────────────────────────────────────┘
                     │
                     │ fetch → /configs/plugins/<name>/
                     ▼
┌──────────────────────────────────────────────┐
│ SHAPE — what the plugin's files mean         │
│                                              │
│   agentskills.io format (SKILL.md + scripts) │
│   MCP server                                 │
│   DeepAgents sub-agent                       │
│   LangGraph sub-graph                        │
│                                              │
│   registered via plugins_registry resolver   │
│   inside the workspace runtime               │
└──────────────────────────────────────────────┘
```

Neither layer mandates the other. A plugin installed from `github://…`
might be agentskills-format. A plugin installed from `local://…` might
be an MCP server. A plugin installed from `clawhub://…` in the future
might be whatever shape ClawHub packs happen to be.

## Source API

`POST /workspaces/:id/plugins` accepts either:

```json
{"name": "my-plugin"}                    // back-compat: local registry
{"source": "local://my-plugin"}          // explicit local
{"source": "github://org/repo"}          // default branch
{"source": "github://org/repo#v1.2.0"}   // pinned tag/branch/sha
{"source": "clawhub://name@1.2.0"}       // once a ClawHub resolver is registered
```

`GET /plugins/sources` lists the currently registered schemes:

```bash
curl $PLATFORM/plugins/sources
{"schemes":["github","local"]}
```

## Registering a new source

```go
// platform/internal/router/router.go
plgh := handlers.NewPluginsHandler(pluginsDir, dockerCli, wh.RestartByID).
    WithSourceResolver(NewClawhubResolver(clawhubToken))
```

A `SourceResolver` must satisfy:

```go
type SourceResolver interface {
    Scheme() string                                              // unique scheme name
    Fetch(ctx context.Context, spec, dst string) (string, error) // copy into dst, return plugin name
}
```

Implementations must honour `ctx` cancellation, clean up temp state on
error, and validate their spec format before hitting the network.

## Built-in sources

### `local` — filesystem

```
local://<name>
<name>              # bare name, same as above
```

Reads from the directory configured as `pluginsDir` at startup (defaults
to the repo's `plugins/` directory). Name must match
`^[a-z0-9][a-z0-9._-]*$`; path-traversal attempts are rejected pre-fetch.

### `github` — GitHub repository

```
github://<owner>/<repo>
github://<owner>/<repo>#<ref>
```

Shallow-clones the repo (optionally at `ref`) via the system `git`
binary, strips `.git`, and copies the contents into the staging dir.
Owner + repo names are length-bounded; refs are restricted to safe
characters. The platform's Dockerfile installs `git`.

## Security

Every resolver validates its spec format before any network or
filesystem operation. The handler then re-validates the plugin name
returned by the resolver before it's used as a path component, so a
hostile resolver can't smuggle a traversal name into
`/configs/plugins/`. The plugin content itself isn't sandboxed; installs
should be treated as code-execution grants and audited accordingly.

## Shapes — the other axis

See [agentskills-compat.md](agentskills-compat.md) for how the shape
layer works. The two are wired together but independent: the source
layer's job ends when plugin files are staged on disk; the shape layer
(per-runtime adapter inside the workspace) decides what to do with them
on workspace startup.
