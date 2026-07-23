from __future__ import annotations

from pathlib import Path
import re

ROOT = Path.cwd()


def read(path: str) -> str:
    full = ROOT / path
    if not full.exists():
        raise SystemExit(f"Required file is missing: {path}")
    return full.read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def add_feature_item(line: str, item: str) -> str:
    if item in line:
        return line
    match = re.fullmatch(r"(?P<prefix>\s*[A-Za-z0-9_-]+\s*=\s*\[)(?P<body>.*)(?P<suffix>\]\s*)", line)
    if match is None:
        raise SystemExit(f"Could not parse Cargo feature line: {line!r}")
    body = match.group("body").rstrip()
    if body:
        body += f', "{item}"'
    else:
        body = f'"{item}"'
    return f'{match.group("prefix")}{body}{match.group("suffix")}'


def patch_cargo() -> None:
    path = "crates/neodash-cosmic/Cargo.toml"
    lines = read(path).splitlines()
    found_winit = False
    found_wayland = False
    updated: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("cosmic-winit ="):
            line = add_feature_item(line, "cosmic/wgpu")
            found_winit = True
        elif stripped.startswith("cosmic-wayland ="):
            line = add_feature_item(line, "cosmic/wgpu")
            found_wayland = True
        updated.append(line)

    if not found_winit or not found_wayland:
        raise SystemExit(
            "Could not find both cosmic-winit and cosmic-wayland feature definitions "
            "in crates/neodash-cosmic/Cargo.toml"
        )

    write(path, "\n".join(updated) + "\n")


def patch_main() -> None:
    path = "crates/neodash-cosmic/src/main.rs"
    text = read(path)

    message_block = '''    #[derive(Debug, Clone)]
    pub enum Message {
        Noop,
    }

'''
    text = text.replace(message_block, "", 1)
    text = text.replace("        type Message = Message;", "        type Message = ();", 1)

    if "type Message = ();" not in text:
        raise SystemExit("Could not convert the COSMIC scaffold message type to unit ()")
    if "pub enum Message" in text or "Noop," in text:
        raise SystemExit("The unused Noop message enum is still present after patching")

    write(path, text)


def write_notes() -> None:
    path = ROOT / "docs/COSMIC_RENDERING.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '''# COSMIC rendering modes

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
''',
        encoding="utf-8",
    )


def main() -> None:
    patch_cargo()
    patch_main()
    write_notes()
    print("NeoDash COSMIC WGPU hotfix applied.")


if __name__ == "__main__":
    main()
