# NeoDash runtime event-stream phase

Apply from the repository root:

```bash
unzip -o ~/Downloads/neodash_phase_runtime_event_stream_fixed.zip -d .
bash tools/patches/phase_runtime_event_stream/apply.sh
```

The apply script resolves its own absolute location, patches the Git repository
root, and is safe to run more than once.

This corrected package also adds the required `clap` dependency to
`neodash-daemon`.
