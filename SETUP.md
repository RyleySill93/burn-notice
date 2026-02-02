# Project Setup Guide

This guide helps you set up a new project from this template.

## Initial Setup

### 1. Backend Setup
```bash
cd backend
make install     # Install dependencies
make dev         # Start development server
```

### 2. Frontend Setup
```bash
cd frontend
npm install      # Install dependencies
npm run dev      # Start development server
```

## Figma Design System Integration

This template includes a token-based design system that keeps your Figma designs and code in perfect sync.

### Overview
- **Design tokens** are the single source of truth for colors, spacing, and typography
- Changes in tokens automatically update both Figma and your application
- Designers and developers work with the same values

### Setting Up Figma Integration

#### 1. Duplicate the Figma Template
- Go to [Obra shadcn/ui Figma file](https://www.figma.com/community/file/1514746685758799870/obra-shadcn-ui)
- Click "Duplicate" to copy to your account
- This gives you all shadcn components matching the codebase

#### 2. Install Figma Tokens Plugin
- In Figma: **Plugins** → **Browse plugins**
- Search for "**Tokens Studio for Figma**"
- Install the plugin by Jan Six

#### 3. Connect to Your Repository
Create a GitHub Personal Access Token:
- Go to GitHub Settings → Developer settings → Personal access tokens → **Fine-grained tokens**
- Generate new token with:
  - **Repository access**: Select your new repo
  - **Permissions**: Contents (Read and write)
- Copy the token

Configure in Figma Tokens:
- Open the plugin in Figma
- Click **Settings** → **Add sync provider** → **GitHub**
- Enter:
  - Personal Access Token: (your token)
  - Repository: `YourUsername/YourRepo`
  - Branch: `main` or `master`
  - File Path: `frontend/design-tokens/tokens.json`
- Click **Connect**

#### 4. Test the Connection
- In Figma Tokens: Click **Pull from GitHub**
- You should see your tokens load (global, light, dark)
- Try changing a color and pushing back to GitHub

### Design Token Workflow

#### For Developers
1. Edit tokens in `frontend/design-tokens/tokens.json`
2. Run `npm run tokens:build` to update CSS
3. Commit and push changes
4. Designers pull updates in Figma

#### For Designers
1. Edit tokens in Figma using the Tokens Studio plugin
2. Push changes to GitHub from the plugin
3. Developers pull and run `npm run tokens:build`
4. CSS automatically updates with new values

### Token Structure
```
frontend/design-tokens/
├── tokens.json          # Single source of truth
├── tokens.figma.json    # Generated for Figma (don't edit)
├── build-tokens.js      # Build script
└── README.md           # Token documentation
```

### Available Commands
```bash
# Build CSS from tokens
npm run tokens:build

# Watch tokens for changes (requires chokidar)
npm run tokens:watch
```

### Customizing Your Design System

1. **Update brand colors** in `tokens.json`:
   ```json
   "primary": {
     "value": "#yourcolor",
     "type": "color"
   }
   ```

2. **Run build** to generate CSS:
   ```bash
   npm run tokens:build
   ```

3. **Sync with Figma**:
   - Push to GitHub
   - Pull in Figma Tokens plugin

### Best Practices
- ✅ Always edit `tokens.json` (never edit generated files)
- ✅ Use semantic token names (primary, secondary, not blue, red)
- ✅ Document token purposes in descriptions
- ✅ Test changes in both light and dark themes
- ✅ Keep Figma component names matching code components

### Troubleshooting

**Tokens not syncing to Figma:**
- Verify GitHub token has correct permissions
- Check branch name matches your default branch
- Ensure file path is exactly `frontend/design-tokens/tokens.json`

**CSS not updating:**
- Run `npm run tokens:build` after token changes
- Check for JSON syntax errors in tokens.json
- Verify build script has correct permissions

**Figma changes not reaching code:**
- Pull latest changes: `git pull`
- Rebuild tokens: `npm run tokens:build`
- Check commit was pushed from Figma

### Resources
- [Design System Documentation](frontend/DESIGN_SYSTEM.md)
- [Token README](frontend/design-tokens/README.md)
- [Figma Tokens Plugin Docs](https://docs.tokens.studio/)
- [shadcn/ui Components](https://ui.shadcn.com)

## Environment Configuration

### Backend (.env)
```bash
DATABASE_URL=postgresql://...
JWT_SECRET=your-secret-key
# Add other backend env variables
```

### Frontend (.env)
```bash
VITE_API_BASE_URL=http://localhost:8000
# Add other frontend env variables
```

## Database Setup

```bash
cd backend
make db-create    # Create database
make db-migrate   # Run migrations
make db-seed      # Seed initial data (if applicable)
```

## Testing

### Backend Tests
```bash
cd backend
make test         # Run all tests
make test-unit    # Run unit tests only
make test-integration  # Run integration tests
```

### Frontend Tests
```bash
cd frontend
npm run test      # Run tests
npm run test:watch  # Watch mode
```

## Deployment

[Add deployment instructions specific to your infrastructure]