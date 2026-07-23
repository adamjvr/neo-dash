# NeoDash — GTK Runtime Adapter Phase

## Goal

Make GTK consume the shared renderer-neutral runtime stream instead of executing
commands and scheduling refreshes inside `neodash-app`.

## Changes

- removes the direct `neodash-exec` dependency from `neodash-app`;
- replaces `run_shell_command_once()` and the GTK-local refresh loop;
- starts one cancellable `neodash-runtime` worker per GTK widget window;
- drains `RuntimeEvent` values on the GTK main loop;
- updates labels only when frame text changes;
- requests non-blocking runtime shutdown when a window closes;
- adds architecture documentation and an automated validation gate.

## Validation

```bash
cargo fmt --all
./scripts/check_gtk_runtime_adapter.sh

cargo run -p neodash-app --features gui,x11-desktop -- \
  --profile default \
  --layout-mode \
  --debug-frame
```

## Suggested commit

```text
feat(gtk): consume the shared widget runtime stream

- replace GTK-local command execution with RuntimeEvent handling
- move refresh ownership fully into neodash-runtime workers
- stop widget workers when GTK windows close
- remove the direct neodash-exec dependency from neodash-app
- add GTK runtime-adapter validation and documentation
```
