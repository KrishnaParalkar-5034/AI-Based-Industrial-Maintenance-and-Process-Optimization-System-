"""
SVG Vector Icon library for AI Industrial Maintenance dashboard.
Provides crisp, professional SVG icons replacing informal emojis.
Icons are designed on a 24x24 viewBox with configurable size, color, stroke, and styles.
"""

ICONS = {
    "factory": (
        '<path d="M2 20h20"/>'
        '<path d="M2 20V9l6 4V9l6 4V9l4-2v13"/>'
        '<path d="M6 4v5"/>'
        '<path d="M12 2v7"/>'
        '<path d="M18 6v3"/>'
        '<path d="M9 20v-4h3v4"/>'
        '<path d="M15 20v-4h2v4"/>'
    ),
    "shield-check": (
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="10"/>'
        '<polyline points="12 6 12 12 16 14"/>'
    ),
    "timer": (
        '<line x1="10" x2="14" y1="2" y2="2"/>'
        '<line x1="12" x2="15" y1="14" y2="11"/>'
        '<circle cx="12" cy="14" r="8"/>'
    ),
    "settings": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'
        '<path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>'
    ),
    "sensors": (
        '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/>'
        '<path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/>'
        '<circle cx="12" cy="12" r="2"/>'
        '<path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/>'
        '<path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/>'
    ),
    "sliders": (
        '<line x1="4" x2="4" y1="21" y2="14"/>'
        '<line x1="4" x2="4" y1="10" y2="3"/>'
        '<line x1="12" x2="12" y1="21" y2="12"/>'
        '<line x1="12" x2="12" y1="8" y2="3"/>'
        '<line x1="20" x2="20" y1="21" y2="16"/>'
        '<line x1="20" x2="20" y1="12" y2="3"/>'
        '<line x1="1" x2="7" y1="14" y2="14"/>'
        '<line x1="9" x2="15" y1="8" y2="8"/>'
        '<line x1="17" x2="23" y1="16" y2="16"/>'
    ),
    "play": (
        '<polygon points="6 3 20 12 6 21 6 3"/>'
    ),
    "activity": (
        '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'
    ),
    "clipboard-list": (
        '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/>'
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
        '<path d="M12 11h4"/><path d="M12 16h4"/>'
        '<path d="M8 11h.01"/><path d="M8 16h.01"/>'
    ),
    "alert-triangle": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
        '<line x1="12" y1="9" x2="12" y2="13"/>'
        '<line x1="12" y1="17" x2="12.01" y2="17"/>'
    ),
    "alert-octagon": (
        '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>'
        '<line x1="12" y1="8" x2="12" y2="12"/>'
        '<line x1="12" y1="16" x2="12.01" y2="16"/>'
    ),
    "siren": (
        '<path d="M7 18v-6a5 5 0 1 1 10 0v6"/>'
        '<path d="M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z"/>'
        '<path d="M21 12h1"/><path d="M18.5 4.5 19 4"/><path d="M2 12h1"/><path d="M12 2v1"/><path d="m4.929 4.929.707.707"/>'
        '<path d="M12 12v6"/>'
    ),
    "heart-pulse": (
        '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>'
        '<path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/>'
    ),
    "trending-up": (
        '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>'
        '<polyline points="16 7 22 7 22 13"/>'
    ),
    "trending-down": (
        '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/>'
        '<polyline points="16 17 22 17 22 11"/>'
    ),
    "zap": (
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
    ),
    "check-circle": (
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/>'
    ),
    "x-circle": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="15" y1="9" x2="9" y2="15"/>'
        '<line x1="9" y1="9" x2="15" y2="15"/>'
    ),
    "cpu": (
        '<rect x="4" y="4" width="16" height="16" rx="2"/>'
        '<rect x="9" y="9" width="6" height="6" rx="1"/>'
        '<path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>'
    ),
    "search": (
        '<circle cx="11" cy="11" r="8"/>'
        '<line x1="21" y1="21" x2="16.65" y2="16.65"/>'
    ),
    "bar-chart": (
        '<line x1="12" x2="12" y1="20" y2="10"/>'
        '<line x1="18" x2="18" y1="20" y2="4"/>'
        '<line x1="6" x2="6" y1="20" y2="16"/>'
    ),
    "wrench": (
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'
    ),
    "info": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 16v-4"/>'
        '<path d="M12 8h.01"/>'
    ),
    "dot": (
        '<circle cx="12" cy="12" r="5" fill="currentColor"/>'
    ),
    "gauge": (
        '<path d="M12 22a9 9 0 1 1 0-18 9 9 0 0 1 0 18z"/>'
        '<path d="M12 7v2"/>'
        '<path d="M7.07 9.07l1.42 1.42"/>'
        '<path d="M5 14h2"/>'
        '<path d="M17 14h2"/>'
        '<path d="M16.95 9.05l-1.41 1.42"/>'
        '<path d="m12 14 2.5-4"/>'
        '<circle cx="12" cy="14" r="1"/>'
    ),
    "tool": (
        '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'
    ),
}

ICON_ALIASES = {
    "warn": "alert-triangle",
    "warning": "alert-triangle",
    "crit": "alert-octagon",
    "critical": "alert-octagon",
    "alert": "alert-octagon",
    "health": "heart-pulse",
    "risk": "trending-up",
    "power": "zap",
    "failure": "zap",
    "plant": "factory",
    "gear": "settings",
    "control": "settings",
    "channels": "activity",
    "telemetry": "activity",
    "chart": "bar-chart",
    "tools": "tool",
    "recommendations": "wrench",
    "advisory": "shield-check",
    "time": "clock",
    "history": "timer",
    "summary": "clipboard-list",
    "source": "database",
    "thresholds": "sliders",
    "inspect": "search",
    "model": "cpu",
}


def icon_svg(
    name: str,
    size: int | str = 16,
    color: str = "currentColor",
    stroke_width: float = 2.0,
    class_name: str = "",
    style: str = "",
    fill: str = "none",
) -> str:
    """
    Generate an inline SVG string for the specified icon name.
    
    Args:
        name: Name or alias of the icon.
        size: Width and height in px (or CSS string like '1.2em').
        color: Stroke color ('currentColor', hex, rgba, etc.).
        stroke_width: Width of SVG stroke lines.
        class_name: Optional CSS class to append.
        style: Optional extra inline CSS styles.
        fill: Fill color ('none', 'currentColor', hex).
    """
    key = name.lower().strip()
    inner = ICONS.get(key)
    if not inner:
        aliased = ICON_ALIASES.get(key)
        if aliased:
            inner = ICONS.get(aliased)
    if not inner:
        inner = ICONS["info"]

    cls_attr = f' class="{class_name}"' if class_name else ""
    # Use vertical-align to align naturally with neighboring text
    base_style = "vertical-align:-0.15em;display:inline-block;flex-shrink:0;"
    full_style = f"{base_style}{style}"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="{fill}" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round"{cls_attr} style="{full_style}">'
        f'{inner}'
        f'</svg>'
    )

