# COSMIC rendering modes

NeoDash enables libcosmic's WGPU renderer for both COSMIC frontend builds.

- `cosmic-winit` runs the libcosmic UI through winit on the current X11 or
  non-COSMIC desktop for day-to-day interface development.
- `cosmic-wayland` compiles the native COSMIC Wayland target.

The initial software-rendered winit scaffold used tiny-skia through softbuffer.
Some X11 visuals do not match softbuffer's required pixel format and can panic
while the window surface is created. WGPU avoids that X11 visual-format
restriction and also matches the GPU-accelerated renderer used by normal
libcosmic application templates.

Run locally:

```bash
cargo run -p neodash-cosmic --features cosmic-winit
```

Compile the native target:

```bash
cargo check -p neodash-cosmic --features cosmic-wayland
```
