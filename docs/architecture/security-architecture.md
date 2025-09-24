# Security Architecture

## 1. Authentication & Authorization

```yaml
# OAuth 2.0 / OIDC Configuration
authentication:
  providers:
    - type: oidc
      issuer: https://auth.example.com
      client_id: ${OIDC_CLIENT_ID}
      client_secret: ${OIDC_CLIENT_SECRET}
      scopes: [openid, profile, email]
  
  jwt:
    algorithm: RS256
    public_key_path: /keys/jwt-public.pem
    access_token_ttl: 900  # 15 minutes
    refresh_token_ttl: 604800  # 7 days

# RBAC Configuration
authorization:
  roles:
    anonymous:
      permissions: [search:basic]
    user:
      permissions: [search:*, document:read, document:write]
    admin:
      permissions: ['*']
```

## 2. Data Encryption

```python
# Encryption at Rest and in Transit
class EncryptionService:
    def __init__(self):
        self.kms = KeyManagementService()
    
    async def encrypt_document(self, document: bytes) -> EncryptedDocument:
        # Generate data encryption key
        dek = self.kms.generate_data_key()
        
        # Encrypt document with DEK
        encrypted_content = aes_gcm_encrypt(document, dek.plaintext)
        
        # Return with encrypted DEK
        return EncryptedDocument(
            content=encrypted_content,
            encrypted_dek=dek.encrypted,
            key_id=dek.key_id
        )
```

## 3. Privacy Controls

```python
# Consent Management
class ConsentManager:
    async def check_consent(self, user_id: str, feature: str) -> bool:
        consent = await self.get_user_consent(user_id)
        return consent.has_granted(feature)
    
    async def apply_privacy_filters(self, data: Any, user_id: str) -> Any:
        consent = await self.get_user_consent(user_id)
        
        if not consent.analytics:
            data = remove_analytics_fields(data)
        
        if not consent.personalization:
            data = remove_personalization_fields(data)
        
        return data
```

---
