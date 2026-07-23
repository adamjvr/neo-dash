# Runtime event stream phase

This phase introduces the toolkit-neutral execution boundary that both GTK and
libcosmic will consume.

`neodash-runtime` now owns:

- validation of executable widget sources
- one-frame command execution
- output/error normalization
- refresh intervals
- worker cancellation
- renderer-neutral runtime events

The daemon can exercise the same stream without opening either GUI:

```bash
cargo run -p neodash-daemon -- \
  --widget examples/widgets/date.toml \
  --frames 3
```

The next phase replaces the GTK-local timeout loop with this event receiver and
then gives the COSMIC host the same adapter. No GTK or libcosmic type is allowed
inside `neodash-runtime`.
