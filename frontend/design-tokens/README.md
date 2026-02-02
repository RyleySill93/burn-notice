# Design Tokens

This directory contains the design tokens that power both our application's UI and Figma designs.

## Files

- **`tokens.json`** - Source of truth for all design decisions
- **`tokens.figma.json`** - Auto-generated Figma-compatible version (DO NOT EDIT)
- **`build-tokens.js`** - Build script that generates CSS and Figma tokens

## Quick Start

### Edit a Token

1. Open `tokens.json`
2. Find the value you want to change
3. Update the `value` field
4. Run `npm run tokens:build`

### Example: Change Primary Color

```json
// In tokens.json
"primary": {
  "value": "#6366f1",  // ← Change this
  "type": "color",
  "description": "Primary brand color"
}
```

Then build:

```bash
npm run tokens:build
```

## Token Structure

```
tokens.json
├── global/          # Shared tokens (radius, fonts)
├── light/           # Light theme colors
│   └── color/
│       ├── primary
│       ├── secondary
│       └── ...
└── dark/            # Dark theme colors
    └── color/
        └── ...
```

## Color Format

- **In tokens.json**: HEX format for Figma compatibility
- **In descriptions**: Original OKLCH values preserved
- **In generated CSS**: Uses OKLCH from descriptions when available

## Commands

```bash
# Build CSS and Figma tokens
npm run tokens:build

# Watch for changes (requires chokidar)
npm run tokens:watch
```

## Figma Integration

### Method 1: Manual Import

1. Run `npm run tokens:build` to generate `tokens.figma.json`
2. In Figma: Plugins → Figma Tokens
3. Import → Load from File → Select `tokens.figma.json`

### Method 2: GitHub Sync (Recommended)

1. Install Figma Tokens plugin
2. Add GitHub repository URL
3. Set path to `frontend/design-tokens/tokens.json`
4. Tokens sync automatically

## Adding New Tokens

### Color Token

```json
"newColor": {
  "value": "#ff6b6b",
  "type": "color",
  "description": "oklch(0.64 0.29 17)"  // Optional: include OKLCH
}
```

### Spacing Token

```json
"spacing": {
  "xs": {
    "value": "4px",
    "type": "spacing"
  }
}
```

### Border Radius Token

```json
"radius": {
  "pill": {
    "value": "9999px",
    "type": "borderRadius"
  }
}
```

## Important Notes

⚠️ **Never edit these files directly:**

- `tokens.figma.json` (generated)
- `../src/index.css` (generated)

✅ **Only edit:**

- `tokens.json`

## Troubleshooting

### Changes not appearing

1. Make sure you ran `npm run tokens:build`
2. Hard refresh your browser (Cmd+Shift+R)
3. Check for JSON syntax errors in `tokens.json`

### Figma not updating

1. Re-import `tokens.figma.json` in Figma Tokens plugin
2. Make sure you're using the latest generated file
3. Check plugin console for errors

### Build script fails

1. Check Node.js version (v18+ required)
2. Verify `tokens.json` is valid JSON
3. Ensure write permissions for `src/index.css`
