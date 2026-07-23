from pathlib import Path
import re

path = Path("crates/neodash-cli/src/main.rs")
text = path.read_text()

# The TOML snippets contain color values such as "#eeeeee". In Rust, an r#"..."#
# raw string ends at the sequence "#, so those TOML color values accidentally
# close the string. Use r##"..."## for the widget TOML constants instead.
def widen_raw_const_delimiter(text: str, const_name: str) -> str:
    pattern = re.compile(
        rf'(const {re.escape(const_name)}: &str = )r#"(.*?)"#;',
        re.DOTALL,
    )

    match = pattern.search(text)
    if not match:
        # Already fixed or the expected const is missing.
        if f"const {const_name}: &str = r##" in text:
            return text
        raise SystemExit(f"could not find {const_name} raw string constant")

    return (
        text[: match.start()]
        + match.group(1)
        + 'r##"'
        + match.group(2)
        + '"##;'
        + text[match.end():]
    )

text = widen_raw_const_delimiter(text, "DEFAULT_DATE_WIDGET_TOML")
text = widen_raw_const_delimiter(text, "DEFAULT_UPTIME_WIDGET_TOML")

path.write_text(text)
print("Fixed config-init widget TOML raw string delimiters.")
