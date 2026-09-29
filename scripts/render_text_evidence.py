from __future__ import annotations

import argparse
import html
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a text evidence file as a readable local HTML page."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    body = html.escape(args.source.read_text(encoding="utf-8"))
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(args.title)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 34px; background: #08111f; color: #e8eef8; }}
    main {{ max-width: 1360px; margin: auto; }}
    h1 {{ margin: 0 0 9px; font-size: 26px; }}
    .subtitle {{ color: #8eabd0; margin-bottom: 24px; }}
    pre {{ margin: 0; padding: 24px; white-space: pre-wrap; overflow-wrap: anywhere;
      border: 1px solid #2b405e; border-radius: 14px; background: #0f1d30;
      box-shadow: 0 18px 40px #02071166; color: #d9e7fa;
      font: 15px/1.55 Consolas, "Cascadia Mono", monospace; }}
  </style>
</head>
<body><main>
  <h1>{html.escape(args.title)}</h1>
  <div class="subtitle">Submission evidence · generated from recorded runtime output</div>
  <pre>{body}</pre>
</main></body>
</html>"""
    args.output.write_text(document, encoding="utf-8")


if __name__ == "__main__":
    main()
