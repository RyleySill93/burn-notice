# OIDC Authentication Module

## Overview

This module implements OpenID Connect (OIDC) authentication for Burn Notice, supporting both SP-initiated (Service Provider) and IdP-initiated (Identity Provider) SSO flows. The implementation provides enterprise-grade SSO with auto-provisioning, token refresh validation, and comprehensive claim management.

## Architecture

### Core Design Principles

1. **Token Exchange**: We exchange IdP tokens for our own JWT tokens to maintain complete control over claims, expiration, and session management
2. **Refresh Token Validation**: On token refresh, we validate against the IdP using stored refresh tokens (requires `offline_access` scope)
3. **Dual Provider Support**: Supports both entity-specific OIDC providers and a global staff provider
4. **Auto-Provisioning**: Optionally creates new users automatically from IdP claims
5. **Claim Storage**: Stores IdP user info for audit and debugging purposes

### Authentication Flows

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SP-Initiated Flow (Standard)                         │
└─────────────────────────────────────────────────────────────────────────────┘

    User                    Burn Notice                     IdP (Okta/Azure)
     │                         │                              │
     │   1. Click Login        │                              │
     ├────────────────────────>│                              │
     │                         │                              │
     │   2. Select OIDC SSO    │                              │
     ├────────────────────────>│                              │
     │                         │   3. Redirect to IdP         │
     │<────────────────────────┤      /authorize?...          │
     │                         │                              │
     │                         │   4. User authenticates      │
     ├───────────────────────────────────────────────────────>│
     │                         │                              │
     │                         │   5. Redirect with code      │
     │<───────────────────────────────────────────────────────┤
     │                         │                              │
     │   6. Send code          │                              │
     ├────────────────────────>│                              │
     │                         │   7. Exchange code           │
     │                         ├─────────────────────────────>│
     │                         │   8. Return tokens           │
     │                         │<─────────────────────────────┤
     │                         │                              │
     │   9. Burn Notice JWT        │                              │
     │<────────────────────────┤                              │
     │                         │                              │


┌─────────────────────────────────────────────────────────────────────────────┐
│                      IdP-Initiated Flow (Azure My Apps)                      │
└─────────────────────────────────────────────────────────────────────────────┘

    User              IdP Portal            Burn Notice              IdP Auth
     │                    │                     │                    │
     │  1. Click tile     │                     │                    │
     ├───────────────────>│                     │                    │
     │                    │                     │                    │
     │  2. Redirect to    │                     │                    │
     │  /auth/sso/        │                     │                    │
     │  initiate/:client  │                     │                    │
     │<───────────────────┤                     │                    │
     │                    │                     │                    │
     │  3. Load page      │                     │                    │
     ├────────────────────────────────────────->│                    │
     │                    │                     │                    │
     │                    │  4. Immediate       │                    │
     │                    │     redirect to IdP │                    │
     │<─────────────────────────────────────────┤                    │
     │                    │                     │                    │
     │  5. Already authenticated (SSO cookie)   │                    │
     ├──────────────────────────────────────────────────────────────>│
     │                    │                     │                    │
     │  6. Redirect with code                   │                    │
     │<──────────────────────────────────────────────────────────────┤
     │                    │                     │                    │
     │  7. Exchange & login                     │                    │
     ├────────────────────────────────────────->│                    │
     │                    │                     │  8. Validate       │
     │                    │                     ├───────────────────>│
     │                    │                     │<───────────────────┤
     │  9. Logged in      │                     │                    │
     │<─────────────────────────────────────────┤                    │
```

### Token Refresh Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Token Refresh Validation                          │
└─────────────────────────────────────────────────────────────────────────────┘

    Frontend              Burn Notice Backend           IdP
        │                      │                      │
        │  1. Refresh token    │                      │
        ├─────────────────────>│                      │
        │                      │                      │
        │                      │  2. Validate stored  │
        │                      │     IdP refresh token│
        │                      ├─────────────────────>│
        │                      │                      │
        │                      │  3. Valid/Invalid    │
        │                      │<─────────────────────┤
        │                      │                      │
        │  4. New JWT or       │                      │
        │     401 Unauthorized │                      │
        │<─────────────────────┤                      │
```

## User Provisioning

### Auto-Provisioning Flow

When `auto_create_users` is enabled on an OIDC provider:

1. **User authenticates** with IdP for the first time
2. **Claims extracted** from ID token (sub, email, name)
3. **User created** in Burn Notice with:
   - Email from IdP claims
   - Name parsed from claims (given_name, family_name, or name)
   - Auto-generated password (never used)
   - Default role assignment based on entity settings
4. **Mapping created** in OIDCProviderUser table:
   - Links Burn Notice user to external IdP user ID (sub claim)
   - Stores IdP refresh token (encrypted)
   - Stores user info/claims for audit

### Manual Provisioning

When `auto_create_users` is disabled:
- User must exist in Burn Notice before SSO login
- On first SSO login, mapping is created
- Subsequent logins use the existing mapping

## Staff OIDC Provider

The staff provider is a special case designed for Burn Notice employees:

### Architecture
- **Shell Record**: Database record with ID `oidc-staffoidc` and placeholder values
- **Environment Override**: Actual configuration from environment variables
- **Per-Environment**: Each environment (dev, staging, prod) has different IdP apps

### Configuration

Required environment variables:
```bash
# Enable OIDC for staff authentication
STAFF_AUTHENTICATION_METHOD=oidc

# IdP Application Credentials (per environment)
STAFF_OIDC_CLIENT_ID=<client-id-from-idp>
STAFF_OIDC_CLIENT_SECRET=<client-secret-from-idp>
STAFF_OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant>/.well-known/openid-configuration

# Optional: Auto-create staff users (default: true)
STAFF_OIDC_AUTO_CREATE_USERS=true

# Provider ID (consistent across environments)
STAFF_OIDC_PROVIDER_ID=oidc-staffoidc
```

### Implementation Details

1. **Database Record**: Created via migration with placeholder values
2. **Runtime Override**: `OIDCService._get_staff_provider_config()` returns config from env vars
3. **Startup Hook**: `ensure_staff_provider_record_exists()` ensures shell record exists
4. **Consistent ID**: Same provider ID across all environments for foreign key integrity

## API Endpoints

### Authentication Endpoints

#### SP-Initiated Login
```
GET /api/auth/oidc/{provider_id}/login
```
Initiates OIDC flow for a specific provider

#### IdP-Initiated Login
```
GET /api/auth/oidc/initiate/{client_id}/login
```
Initiates OIDC flow using OAuth client ID (for IdP portals)

#### Callback
```
GET /api/auth/oidc/callback?code=...&state=...
```
Handles OAuth callback, exchanges code for tokens

### Management Endpoints

#### Entity OIDC Provider
```
GET  /api/auth/get-entity-oidc-provider?entity_id=...
POST /api/auth/save-entity-oidc-provider
POST /api/auth/test-entity-oidc-provider
```

#### Customer OIDC Provider
```
GET  /api/auth/get-customer-oidc-provider?customer_id=...
POST /api/auth/save-customer-oidc-provider
POST /api/auth/test-customer-oidc-provider
```

#### Staff Provider Info
```
GET /api/auth/get-staff-oidc-provider
```

## Frontend Routes

### User-Facing Routes

- `/auth/oidc/callback` - OAuth callback handler
- `/auth/sso/initiate/:clientId` - IdP-initiated SSO entry point

### Implementation Components

- `OIDCCallback.tsx` - Handles OAuth callback
- `InitiateSSOLogin.tsx` - IdP-initiated flow handler
- `OIDCButton.tsx` - SSO login button
- `ConfigureOIDCModal.tsx` - Admin configuration UI

## Security Considerations

### Token Management
1. **No IdP token storage**: We don't store IdP access tokens
2. **Encrypted refresh tokens**: IdP refresh tokens encrypted at rest
3. **Our JWT control**: Issue our own JWTs with custom claims
4. **Refresh validation**: Validate with IdP on every refresh

### CSRF Protection
- State parameter with CSRF token
- Provider ID encoded in state
- State validation on callback

### Scope Requirements
Required OIDC scopes:
- `openid` - Required for OIDC
- `email` - User email address
- `profile` - User profile info
- `offline_access` - Refresh tokens (critical for validation)

## Database Schema

### Tables

#### oidcprovider
- Stores OIDC provider configurations
- Encrypted client_secret field
- Auto-discovered endpoint storage
- Per-entity configuration

#### oidcprovideruser
- Maps IdP users to Burn Notice users
- Stores external user ID (sub claim)
- Encrypted refresh token storage
- Claims/user info audit trail

## Error Handling

### Exception Hierarchy
```
OIDCException (base)
├── OIDCStaffProviderMissing
├── MissingEnabledOIDCProvider
├── OIDCUserProvisionDisabled
├── OIDCTokenExchangeError
├── OIDCTokenValidationError
├── OIDCDiscoveryError
└── OIDCMissingClaimsError
```

### Common Issues

1. **"No email in ID token"**: IdP not returning email claim
   - Solution: Configure IdP to include email in claims

2. **"User provision disabled"**: auto_create_users=false and user doesn't exist
   - Solution: Create user manually or enable auto-provisioning

3. **Token refresh fails**: IdP refresh token expired or revoked
   - Solution: User must re-authenticate

## Testing

### Test Provider Setup
1. Create test IdP application (Okta, Azure AD, Auth0)
2. Configure redirect URIs:
   - `https://your-domain/auth/oidc/callback`
3. Note client ID and secret
4. Configure provider in Burn Notice admin

### Test Scenarios
- [ ] SP-initiated login
- [ ] IdP-initiated login (portal tiles)
- [ ] Auto-provisioning new user
- [ ] Existing user mapping
- [ ] Token refresh with IdP validation
- [ ] Disabled provider handling
- [ ] Invalid refresh token handling

## Migration Guide

### From Azure-specific SSO
1. Existing Azure SSO continues to work
2. OIDC is more generic, supports any OIDC provider
3. Can run both in parallel during migration

### Adding New Provider
1. Admin creates provider config
2. Users see new SSO option
3. First login creates mapping
4. Subsequent logins use mapping

## Best Practices

1. **Always use discovery**: Let the IdP provide endpoints via discovery
2. **Require offline_access**: Critical for refresh validation
3. **Store claims**: Keep IdP claims for debugging
4. **Encrypt secrets**: All secrets encrypted at rest
5. **Validate on refresh**: Always check with IdP on token refresh
6. **Use shell records**: For environment-specific providers (like staff)

## Troubleshooting

### Debug Logging
- Token exchange: Check `OIDCService.exchange_code()` logs
- Validation: Check `OIDCService.validate_id_token()` logs
- User provisioning: Check `find_or_create_user()` logs

### Common Solutions
| Problem | Solution |
|---------|----------|
| SSO tile doesn't work | Use `/auth/sso/initiate/{client_id}` URL format |
| Can't find user | Check auto_create_users setting |
| Token expired quickly | Check token_refresh_frequency in auth settings |
| Staff SSO not working | Verify all STAFF_OIDC_* env vars set |

## Future Enhancements

- [ ] SAML support alongside OIDC
- [ ] Multiple OIDC providers per entity
- [ ] Group/role mapping from IdP claims
- [ ] Just-in-time provisioning with attribute mapping
- [ ] Session timeout sync with IdP
- [ ] Single Logout (SLO) support