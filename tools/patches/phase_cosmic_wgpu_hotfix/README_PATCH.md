# NeoDash COSMIC WGPU hotfix

This patch fixes the non-COSMIC `cosmic-winit` preview panic:

```text
Visual ... does not use softbuffer's pixel format and is unsupported
```

It enables libcosmic's WGPU renderer for both `cosmic-winit` and
`cosmic-wayland`, and removes the unused `Noop` message that would fail a
`clippy -D warnings` gate.

Apply from the NeoDash repository root:

```bash
unzip -o ~/Downloads/neodash_phase_cosmic_wgpu_hotfix.zip -d .
bash tools/patches/phase_cosmic_wgpu_hotfix/apply.sh
```
