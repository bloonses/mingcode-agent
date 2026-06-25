from rich.style import Style
from rich.console import Console

NEON_TEAL = "#00ff88"
NEON_RED = "#ff3366"
NEON_BLUE = "#00aaff"
NEON_PURPLE = "#aa44ff"
NEON_YELLOW = "#ffcc00"

BG_DARK = "#050510"
BG_MID = "#0a1210"
BG_PANEL = "#0d1a16"

PULSE_DURATION = 2.4

style_neon_teal = Style(color=NEON_TEAL, bold=True)
style_neon_red = Style(color=NEON_RED, bold=True)
style_neon_blue = Style(color=NEON_BLUE, bold=True)
style_neon_purple = Style(color=NEON_PURPLE, bold=True)
style_neon_yellow = Style(color=NEON_YELLOW, bold=True)

style_dim_teal = Style(color=NEON_TEAL, dim=True)
style_dim_purple = Style(color=NEON_PURPLE, dim=True)

style_text = Style(color="#c0d0c8")
style_text_muted = Style(color="#507060")

style_panel_border_teal = Style(color=NEON_TEAL)
style_panel_border_blue = Style(color=NEON_BLUE)
style_panel_border_purple = Style(color=NEON_PURPLE)
style_panel_border_red = Style(color=NEON_RED)
style_panel_border_dim = Style(color="#204030")

style_prompt = Style(color=NEON_TEAL, bold=True)
style_spinner = Style(color=NEON_TEAL)
