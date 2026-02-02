# Design System Documentation

## Overview

This project uses a **token-based design system** that keeps Figma and code in perfect sync. Design tokens are the single source of truth for all design decisions.

## Architecture

```
tokens.json (source of truth)
    ├→ index.css (generated CSS variables)
    └→ tokens.figma.json (Figma import format)
```

## Quick Start

### For Developers

1. **Edit design tokens:**

   ```bash
   # Edit the token values
   frontend/design-tokens/tokens.json
   ```

2. **Build CSS from tokens:**

   ```bash
   npm run tokens:build
   ```

3. **Watch mode during development:**
   ```bash
   npm run tokens:watch
   ```

### For Designers

1. **Install Figma Tokens plugin** in Figma
2. **Import** `frontend/design-tokens/tokens.figma.json`
3. **Apply tokens** to your designs
4. **Export changes** back to `tokens.json` (optional)

## Token Structure

### Colors

- **Light/Dark themes** - Automatic theme switching
- **Semantic naming** - `primary`, `secondary`, `destructive`, etc.
- **OKLCH color space** - Better color interpolation (converted to HEX for Figma)

### Spacing & Radius

- **Border radius** - `sm`, `md`, `lg`, `xl` variants
- **Based on rem units** - Scales with user preferences

## Component Library

We use **shadcn/ui** as our base component library with the following components:

| Component | Location                      | Variants                                              |
| --------- | ----------------------------- | ----------------------------------------------------- |
| Button    | `/components/ui/button.tsx`   | default, destructive, outline, secondary, ghost, link |
| Input     | `/components/ui/input.tsx`    | -                                                     |
| Checkbox  | `/components/ui/checkbox.tsx` | -                                                     |

### Component Naming Convention

- **Figma**: Use exact component names (Button, Input, Checkbox)
- **Code**: Import from `@/components/ui/*`
- **Variants**: Must match between Figma and code

## Workflow

### Adding a New Color

1. **Edit** `tokens.json`:

   ```json
   "brand": {
     "value": "#6366f1",
     "type": "color",
     "description": "Brand purple"
   }
   ```

2. **Build** the tokens:

   ```bash
   npm run tokens:build
   ```

3. **Use** in components:
   ```tsx
   className = 'bg-brand text-white'
   ```

### Creating Custom Components

1. **Design** in Figma using existing tokens
2. **Export** component specs
3. **Build** in code using shadcn patterns:
   ```tsx
   // Follow existing shadcn patterns
   const customVariants = cva('base-styles', {
     variants: {
       variant: {
         custom: 'token-based-styles',
       },
     },
   })
   ```

## Figma Integration

### Setup Figma Tokens Plugin

1. **Open Figma** → Plugins → Search "Figma Tokens"
2. **Install** the plugin
3. **Configure** token sources:
   - Local: Import `tokens.figma.json`
   - GitHub: Connect to `frontend/design-tokens/` (optional)

### Syncing Changes

#### Code → Figma

1. Edit `tokens.json`
2. Run `npm run tokens:build`
3. In Figma: Plugins → Figma Tokens → Sync

#### Figma → Code (Advanced)

1. Edit tokens in Figma Tokens plugin
2. Export to GitHub/JSON
3. Update `tokens.json`
4. Run `npm run tokens:build`

## Best Practices

### Do's ✅

- Always edit `tokens.json` for theme changes
- Use semantic token names
- Keep Figma component names matching code
- Run `tokens:build` after token changes
- Document new patterns in this file

### Don'ts ❌

- Never edit `index.css` directly for theme values
- Don't use hardcoded colors in components
- Avoid creating duplicate tokens
- Don't bypass the token system

## Troubleshooting

### CSS not updating

- Run `npm run tokens:build`
- Check for syntax errors in `tokens.json`
- Verify the build script has proper permissions

### Figma tokens not syncing

- Ensure `tokens.figma.json` was generated
- Check Figma Tokens plugin is updated
- Verify JSON syntax is valid

### Color mismatch

- OKLCH values are preserved in descriptions
- HEX values are used for Figma compatibility
- Browser DevTools show computed values

## Component Status

| Component | In Code | In Figma | Synced |
| --------- | ------- | -------- | ------ |
| Button    | ✅      | ✅       | ✅     |
| Input     | ✅      | ✅       | ✅     |
| Checkbox  | ✅      | ✅       | ✅     |
| Card      | ❌      | ❌       | -      |
| Dialog    | ❌      | ❌       | -      |

## Resources

- [shadcn/ui Documentation](https://ui.shadcn.com)
- [Figma Tokens Plugin](https://www.figma.com/community/plugin/843461159747178978)
- [OKLCH Color Space](https://oklch.com)
- [Token-based Design Systems](https://www.designtokens.org)

## Maintenance

- **Review tokens** quarterly for consistency
- **Update Figma kit** when adding new components
- **Document changes** in this file
- **Version control** all token changes
