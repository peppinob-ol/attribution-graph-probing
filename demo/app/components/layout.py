"""
Reusable layout components for FastHTML pages
"""
from fasthtml.common import (
    Html, Head, Body, Title, Link, Script, Meta, Style
)


def base_head(title: str = "State Swap Explorer"):
    """Return common head elements."""
    return Head(
        Title(title),
        Meta(charset="UTF-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        Meta(name="description", content="Interactive visualization of circuit steering experiments across US states"),
        Link(rel="stylesheet", href="/static/css/tailwind.css"),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
        ),
        Style("""
            body {
                font-family: 'Space Grotesk', system-ui, sans-serif;
            }
            .font-mono {
                font-family: 'JetBrains Mono', monospace;
            }
        """),
    )


def base_scripts():
    """Return common script elements."""
    return (
        Script(src="/static/islands/Matrix.js", type="module"),
        Script(src="/static/islands/DetailPanel.js", type="module"),
    )

