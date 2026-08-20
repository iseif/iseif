# What's in this repository?

This is a small self-updating GitHub Profile README inspired by terminal / Neofetch-style developer profiles.

| File | Purpose |
| --- | --- |
| `README.md` | The actual GitHub Profile README. Selects the correct SVG for dark/light mode. |
| `profile.json` | The editable profile content and technology list. |
| `generate.py` | Fetches public GitHub stats, converts the avatar to ASCII, and renders both SVG themes. |
| `dark_mode.svg` | Dark GitHub theme card. |
| `light_mode.svg` | Light GitHub theme card. |
| `.github/workflows/profile.yml` | Daily/automatic SVG refresh workflow. |
| `requirements.txt` | Python dependencies. |
| `SETUP.md` | Installation and customization instructions. |

## Privacy

The generator only displays the data explicitly configured in `profile.json` plus public GitHub statistics. No email address is included in this package.
