# Multi-Factor Authentication (MFA) Module

## Overview

This module implements Multi-Factor Authentication (MFA) for Burn Notice, providing an additional security layer beyond primary authentication methods (password, magic link, SSO). MFA is configurable per entity and supports multiple verification methods.

## Supported MFA Methods

### EMAIL (Legacy)
Time-limited 6-digit codes sent via email.

**Flow:**
1. User authenticates with primary method (password/magic link)
2. System generates 6-digit code
3. Code sent to user's email
4. User enters code within 5 minutes
5. Code deleted after use (single-use)

**Properties:**
- **Code Format**: 6-digit numeric
- **Expiration**: 5 minutes
- **Single-use**: Code deleted after verification
- **Delivery**: SendGrid email

### TOTP (Time-Based One-Time Password)
Industry-standard TOTP using authenticator apps (Google Authenticator, Authy, 1Password, etc.).

**Flow:**
1. User sets up TOTP in security settings
2. System generates secret + QR code
3. User scans QR code with authenticator app
4. User verifies with first code
5. On future logins, user enters current TOTP code

**Properties:**
- **Algorithm**: SHA-1 (RFC 6238)
- **Code Format**: 6-digit numeric
- **Time Window**: 30 seconds per code
- **Clock Drift**: ±1 window (90s total tolerance)
- **Secret Storage**: Encrypted at rest
- **Backup Codes**: 8 single-use recovery codes

### SMS
Time-limited 6-digit codes sent via SMS using AWS SNS.

**Flow:**
1. User sets up SMS in security settings
2. User enters phone number (E.164 format)
3. System sends 6-digit verification code via SMS
4. User verifies with code to enable SMS MFA
5. On future logins, code sent to registered phone

**Properties:**
- **Code Format**: 6-digit numeric
- **Expiration**: 5 minutes
- **Single-use**: Code deleted after verification
- **Delivery**: AWS SNS (requires separate SNS credentials)
- **Phone Format**: E.164 (+1234567890)
- **No Backup Codes**: Use alternative MFA methods as backup

## Architecture

### Design Principles

1. **Method Isolation**: Each MFA method is self-contained in its own service
2. **Shared State**: MFA tokens track intermediate authentication state
3. **Entity Control**: MFA requirements configured per entity
4. **User Choice**: Multiple MFA methods can be enabled simultaneously
5. **Recovery Path**: TOTP has backup codes; EMAIL/SMS use alternative methods for recovery

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Primary + MFA Authentication                      │
└─────────────────────────────────────────────────────────────────────────┘

    User                Frontend              Backend                 MFA
     │                      │                    │                     │
     │  1. Login           │                    │                     │
     │  (email+password)   │                    │                     │
     ├────────────────────>│                    │                     │
     │                     │  2. Authenticate   │                     │
     │                     ├───────────────────>│                     │
     │                     │                    │                     │
     │                     │  3. MFA Required   │                     │
     │                     │     (MFA Token)    │                     │
     │                     │<───────────────────┤                     │
     │                     │                    │                     │
     │                     │  4. Generate MFA   │                     │
     │                     │     challenge      │                     │
     │                     ├───────────────────>│                     │
     │                     │                    │  5. Create code/    │
     │                     │                    │     setup          │
     │                     │                    ├───────────────────>│
     │                     │                    │                     │
     │  6. Enter code      │                    │                     │
     │  (email or TOTP)    │                    │                     │
     ├────────────────────>│                    │                     │
     │                     │  7. Verify MFA     │                     │
     │                     ├───────────────────>│                     │
     │                     │                    │  8. Check code      │
     │                     │                    ├───────────────────>│
     │                     │                    │  9. Valid/Invalid   │
     │                     │                    │<───────────────────┤
     │                     │  10. JWT Token     │                     │
     │                     │<───────────────────┤                     │
     │  11. Logged in      │                    │                     │
     │<────────────────────┤                    │                     │
```

### TOTP Setup Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TOTP Enrollment                                │
└─────────────────────────────────────────────────────────────────────────┘

    User              Frontend            Backend           Authenticator App
     │                   │                   │                    │
     │  1. Enable TOTP   │                   │                    │
     ├──────────────────>│                   │                    │
     │                   │  2. Request setup │                    │
     │                   ├──────────────────>│                    │
     │                   │                   │                    │
     │                   │  3. Generate      │                    │
     │                   │     - Secret      │                    │
     │                   │     - QR code     │                    │
     │                   │     - Backup codes│                    │
     │                   │<──────────────────┤                    │
     │                   │                   │                    │
     │  4. Display QR &  │                   │                    │
     │     backup codes  │                   │                    │
     │<──────────────────┤                   │                    │
     │                   │                   │                    │
     │  5. Scan QR code  │                   │                    │
     ├──────────────────────────────────────────────────────────>│
     │                   │                   │                    │
     │  6. Show 6-digit  │                   │                    │
     │     code          │                   │                    │
     │<──────────────────────────────────────────────────────────┤
     │                   │                   │                    │
     │  7. Enter code    │                   │                    │
     │  (verification)   │                   │                    │
     ├──────────────────>│                   │                    │
     │                   │  8. Enable TOTP   │                    │
     │                   │     (verify code) │                    │
     │                   ├──────────────────>│                    │
     │                   │                   │                    │
     │                   │  9. Verified ✓    │                    │
     │                   │     TOTP active   │                    │
     │                   │<──────────────────┤                    │
     │  10. Success      │                   │                    │
     │<──────────────────┤                   │                    │
```

## API Endpoints

### MFA Challenge Generation

#### Generate Email MFA Code
```
POST /api/auth/generate-mfa-challenge
```
**Request:**
```json
{
  "email": "user@example.com"
}
```
**Response:**
```json
{
  "token": "mfa_abc123...",
  "message": "MFA code sent to email"
}
```

### MFA Verification

#### Verify MFA Code
```
POST /api/auth/authenticate-mfa
```
**Request:**
```json
{
  "email": "user@example.com",
  "mfa_code": "123456",
  "mfa_token": "mfa_abc123...",
  "mfa_method": "EMAIL"  // or "TOTP"
}
```
**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### TOTP Management

#### Generate TOTP Secret
```
POST /api/auth/generate-totp-secret
```
**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,iVBOR...",
  "backup_codes": [
    "ABCD-1234-EF",
    "GHIJ-5678-KL",
    ...
  ]
}
```

#### Enable TOTP
```
POST /api/auth/enable-totp
```
**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "code": "123456"
}
```
**Response:**
```json
{
  "success": true,
  "message": "TOTP enabled successfully"
}
```

#### Disable TOTP
```
POST /api/auth/disable-totp
```
**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true,
  "message": "TOTP disabled successfully"
}
```

#### Get TOTP Status
```
GET /api/auth/get-totp-status
```
**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "enabled": true,
  "created_at": "2025-10-03T12:00:00Z",
  "verified_at": "2025-10-03T12:05:00Z",
  "last_used_at": "2025-10-03T14:30:00Z",
  "backup_codes_remaining": 6
}
```

## Database Schema

### MfaAuthCode (Email)
```python
class MfaAuthCode:
    id: NanoIdType              # Primary key
    user_id: NanoIdType         # FK to user
    code: str                   # 6-digit code
    expiration_at: datetime     # 5-minute expiry
```

### MFASecret (Unified: TOTP & SMS)
```python
class MFASecret:
    id: NanoIdType                # Primary key
    user_id: NanoIdType           # FK to user
    mfa_method: str               # 'TOTP' or 'SMS'
    secret: str                   # Encrypted TOTP secret or SMS verification code
    phone_number: str | None      # E.164 format for SMS
    is_verified: bool             # Setup completed
    verification_attempts: int    # Rate limiting (max 5)
    backup_codes: list[str] | None  # Only for TOTP (8 codes)
    created_at: datetime
    verified_at: datetime | None
    last_used_at: datetime | None
```

### EntityAuthSettings
```python
class EntityAuthSettings:
    # ... other fields ...
    mfa_methods: List[MultiFactorMethodEnum]  # ['EMAIL', 'TOTP', 'SMS']
```

## Configuration

### Entity-Level MFA

MFA is configured per entity in `EntityAuthSettings`:

```python
# Example: Require TOTP for an entity
EntityAuthSettings.update(
    entity_id='ent_...',
    mfa_methods=[MultiFactorMethodEnum.TOTP]
)

# Example: Allow EMAIL or TOTP (user choice)
EntityAuthSettings.update(
    entity_id='ent_...',
    mfa_methods=[MultiFactorMethodEnum.EMAIL, MultiFactorMethodEnum.TOTP]
)
```

### User-Level Settings

Users see the **strictest** MFA requirements across all their entity memberships:

```python
# If user is member of:
# - Entity A: mfa_methods = ['EMAIL']
# - Entity B: mfa_methods = ['TOTP']
# User must use TOTP (stricter method)
```

## Security Considerations

### Email MFA

**Strengths:**
- ✅ No setup required
- ✅ Works for all users
- ✅ Single-use codes

**Weaknesses:**
- ⚠️ Email compromise = MFA bypass
- ⚠️ Delivery delays possible
- ⚠️ Not ideal for high-security scenarios

### TOTP

**Strengths:**
- ✅ Industry standard (RFC 6238)
- ✅ Offline verification
- ✅ No SMS/email dependency
- ✅ Encrypted secret storage
- ✅ Backup codes for recovery

**Weaknesses:**
- ⚠️ Requires user setup
- ⚠️ Device loss = account lockout (mitigated by backup codes)
- ⚠️ Clock drift issues (mitigated by ±1 window)

### SMS

**Strengths:**
- ✅ Familiar to users
- ✅ Works on any phone
- ✅ Single-use codes
- ✅ Separate AWS SNS credentials (least privilege)

**Weaknesses:**
- ⚠️ Requires phone number
- ⚠️ SMS interception possible
- ⚠️ Delivery delays/costs
- ⚠️ No backup codes (use EMAIL as alternative)

### Best Practices

1. **Backup Codes**: Provide for TOTP only; SMS/EMAIL use alternative methods
2. **Rate Limiting**: Enforce attempt limits (5 for setup, token expiry for login)
3. **Encrypted Storage**: All secrets encrypted at rest
4. **Credential Separation**: Dedicated AWS credentials (SNS for SMS, SES for email)
5. **Audit Logging**: Track all MFA operations
6. **Admin Override**: Staff can disable MFA for locked-out users
7. **User Education**: Clear instructions for setup and recovery options

## Testing

### Test Email MFA
```python
# 1. Generate code
response = client.post('/api/auth/generate-mfa-challenge', json={
    'email': 'test@example.com'
})
mfa_token = response.json()['token']

# 2. Get code from database (test only)
code = MfaAuthCode.get(user_id=user_id).code

# 3. Verify
response = client.post('/api/auth/authenticate-mfa', json={
    'email': 'test@example.com',
    'mfa_code': code,
    'mfa_token': mfa_token,
    'mfa_method': 'EMAIL'
})
assert response.status_code == 200
```

### Test TOTP
```python
import pyotp

# 1. Generate secret
response = client.post('/api/auth/generate-totp-secret',
    headers={'Authorization': f'Bearer {token}'})
secret = response.json()['secret']

# 2. Generate TOTP code
totp = pyotp.TOTP(secret)
code = totp.now()

# 3. Enable TOTP
response = client.post('/api/auth/enable-totp',
    headers={'Authorization': f'Bearer {token}'},
    json={'code': code})
assert response.json()['success'] == True

# 4. Test login with TOTP
totp_code = totp.now()
response = client.post('/api/auth/authenticate-mfa', json={
    'email': 'test@example.com',
    'mfa_code': totp_code,
    'mfa_token': mfa_token,
    'mfa_method': 'TOTP'
})
assert response.status_code == 200
```

### Test Backup Codes
```python
# 1. Setup TOTP (get backup codes)
response = client.post('/api/auth/generate-totp-secret', ...)
backup_codes = response.json()['backup_codes']

# 2. Use backup code for login
backup_code = backup_codes[0]
response = client.post('/api/auth/authenticate-mfa', json={
    'email': 'test@example.com',
    'mfa_code': backup_code,  # Use backup instead of TOTP
    'mfa_token': mfa_token,
    'mfa_method': 'TOTP'
})
assert response.status_code == 200

# 3. Verify code was consumed
status = client.get('/api/auth/get-totp-status', ...)
assert status.json()['backup_codes_remaining'] == 7
```

## Frontend Integration

### Components

#### Email MFA
```typescript
// User enters email code
<MFAInput
  method="EMAIL"
  onSubmit={(code) => verifyMFA(email, code, mfaToken, 'EMAIL')}
/>
```

#### TOTP Setup
```typescript
// 1. Initiate setup
const { secret, qr_code, backup_codes } = await generateTOTPSecret();

// 2. Display QR code
<QRCodeDisplay qrCode={qr_code} />

// 3. Show backup codes (user must save)
<BackupCodeList codes={backup_codes} />

// 4. Verify first code
<TOTPVerification
  onSubmit={(code) => enableTOTP(code)}
/>
```

#### TOTP Login
```typescript
// User enters current TOTP code
<MFAInput
  method="TOTP"
  onSubmit={(code) => verifyMFA(email, code, mfaToken, 'TOTP')}
  onUseBackupCode={() => setShowBackupInput(true)}
/>
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid code` | Wrong MFA code entered | User re-enters or requests new code |
| `Code expired` | Email code > 5 minutes old | Request new MFA challenge |
| `Maximum attempts exceeded` | 5+ failed TOTP setup attempts | Generate new TOTP secret |
| `TOTP already enabled` | User tries to setup TOTP twice | Disable first, then re-enable |
| `MFA token invalid` | Invalid/expired MFA token | Restart login flow |

### Rate Limiting

1. **Email MFA**: Token expiry (5 min) prevents brute force
2. **TOTP Setup**: Max 5 verification attempts, then must regenerate secret
3. **TOTP Login**: Relies on time-based expiry (30s codes)

## Migration Guide

### Adding MFA to Existing Entity

1. **Update entity settings:**
   ```python
   EntityAuthSettings.update(
       entity_id='ent_123',
       mfa_methods=[MultiFactorMethodEnum.EMAIL]  # Start with EMAIL
   )
   ```

2. **Communicate to users:**
   - Email announcement
   - Grace period for TOTP setup
   - Backup code instructions

3. **Gradual rollout:**
   - Week 1: EMAIL MFA (all users)
   - Week 2: TOTP available (optional)
   - Week 3: TOTP recommended
   - Week 4: TOTP required (with backup codes)

### Migrating from Email to TOTP

1. **Enable both methods:**
   ```python
   mfa_methods=[MultiFactorMethodEnum.EMAIL, MultiFactorMethodEnum.TOTP]
   ```

2. **Allow user choice during transition**

3. **Eventually remove EMAIL:**
   ```python
   mfa_methods=[MultiFactorMethodEnum.TOTP]
   ```

## Future Enhancements

- [ ] **WebAuthn/FIDO2**: Hardware key support (YubiKey, etc.)
- [ ] **Push Notifications**: Mobile app approval
- [ ] **Risk-Based MFA**: Only prompt for suspicious logins
- [ ] **Remember Device**: Skip MFA for 30 days on trusted devices
- [ ] **Backup Code Regeneration**: Allow users to generate new TOTP codes
- [ ] **Multiple TOTP Devices**: Support multiple authenticators per user
- [ ] **Passkeys**: Platform authenticator support

## Troubleshooting

### TOTP Clock Drift

**Symptom:** TOTP codes fail despite being correct

**Cause:** Server/client clock mismatch > 90s

**Solution:**
- Check server time sync (NTP)
- User checks device time
- Code uses ±1 window tolerance (90s total)

### Lost Authenticator Device

**Symptom:** User cannot generate TOTP codes

**Solutions:**
1. **Backup codes**: User enters saved backup code
2. **Admin override**: Staff disables TOTP for user
3. **Re-setup**: User re-enables TOTP with new secret

### Email Codes Not Arriving

**Symptom:** User doesn't receive email MFA code

**Solutions:**
1. Check spam folder
2. Verify SendGrid delivery logs
3. Check email service status
4. Use TOTP as alternative

## Dependencies

```txt
# TOTP
pyotp==2.9.0        # TOTP implementation (RFC 6238)
qrcode==7.4.2       # QR code generation
pillow==11.3.0      # Image library for QR codes
```

## References

- [RFC 6238 - TOTP](https://datatracker.ietf.org/doc/html/rfc6238)
- [RFC 4226 - HOTP](https://datatracker.ietf.org/doc/html/rfc4226)
- [Google Authenticator Key URI Format](https://github.com/google/google-authenticator/wiki/Key-Uri-Format)
- [pyotp Documentation](https://pyauth.github.io/pyotp/)
