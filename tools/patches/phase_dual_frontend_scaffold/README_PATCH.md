# NeoDash phase: dual frontend scaffold

This phase corrects the platform architecture so COSMIC is a first-class native
target rather than a synonym for generic Wayland.

It adds:

- explicit GTK and libcosmic frontend identities;
- `CosmicNative` backend detection;
- capability-based platform information;
- deterministic environment-detection tests;
- a new `neodash-cosmic` crate;
- `cosmic-winit` for visual iteration outside COSMIC;
- `cosmic-wayland` for continuous native-target compilation;
- a combined frontend check script;
- a dedicated GitHub Actions COSMIC compile job;
- dual-frontend architecture documentation.

Apply from the NeoDash repository root:

```bash
unzip -o neodash_phase_dual_frontend_scaffold.zip -d .
bash tools/patches/phase_dual_frontend_scaffold/apply.sh
```

The phase does not yet implement COSMIC desktop-layer widget surfaces. It creates
the correct host boundary and development loop before daemon/runtime work and
compositor-specific integration continue.
