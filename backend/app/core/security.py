"""
Security utilities and authentication
JWT tokens, password hashing, and access control
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
import structlog
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=True)


class SecurityManager:
    """Security utilities and token management"""
    
    def __init__(self):
        self.algorithm = settings.jwt_algorithm
        self.secret_key = settings.jwt_secret_key
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days
    
    # Password hashing
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_password_reset_token() -> str:
        """Generate secure random token for password reset"""
        return secrets.token_urlsafe(32)
    
    # Email hashing for privacy
    @staticmethod
    def hash_email(email: str) -> str:
        """Hash email for privacy-compliant storage"""
        return hashlib.sha256(email.lower().encode()).hexdigest()
    
    # Content hashing
    @staticmethod
    def hash_content(content: Union[str, bytes]) -> str:
        """Hash content for deduplication"""
        if isinstance(content, str):
            content = content.encode()
        return hashlib.sha256(content).hexdigest()
    
    # Query hashing for search privacy
    @staticmethod
    def hash_query(query: str) -> str:
        """Hash search query for privacy-compliant analytics"""
        # Use salt to prevent rainbow table attacks
        salt = settings.secret_key[:16]  # Use part of secret key as salt
        salted_query = salt + query.lower()
        return hashlib.sha256(salted_query.encode()).hexdigest()
    
    # JWT Token management
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != token_type:
                raise JWTError("Invalid token type")
            
            # Check expiration
            exp = payload.get("exp")
            if exp is None or datetime.utcnow().timestamp() > exp:
                raise JWTError("Token expired")
            
            return payload
            
        except JWTError as e:
            logger.error("Token verification failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from refresh token"""
        try:
            payload = self.verify_token(refresh_token, token_type="refresh")
            
            # Extract user data (exclude token-specific fields)
            user_data = {
                key: value 
                for key, value in payload.items() 
                if key not in ["exp", "iat", "type"]
            }
            
            # Create new access token
            new_access_token = self.create_access_token(user_data)
            return new_access_token
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Token refresh failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    
    def get_token_payload(self, token: str) -> Dict[str, Any]:
        """Extract payload from token without verification (for expired tokens)"""
        try:
            # Decode without verification to get payload
            payload = jwt.get_unverified_claims(token)
            return payload
        except JWTError:
            return {}
    
    # API Key management
    @staticmethod
    def generate_api_key() -> str:
        """Generate API key"""
        return f"mcp_rag_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    # Permission checking
    @staticmethod
    def check_permission(user_permissions: list, required_permission: str) -> bool:
        """Check if user has required permission"""
        if "*" in user_permissions:  # Admin wildcard
            return True
        return required_permission in user_permissions
    
    @staticmethod
    def check_scope(token_scopes: list, required_scope: str) -> bool:
        """Check if token has required scope"""
        return required_scope in token_scopes or "admin" in token_scopes


class RateLimiter:
    """Rate limiting utilities"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def is_rate_limited(
        self, 
        identifier: str, 
        limit: int, 
        window_seconds: int = 60,
        endpoint: str = "default"
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request should be rate limited
        Returns (is_limited, rate_limit_info)
        """
        key = f"rate_limit:{endpoint}:{identifier}"
        
        try:
            # Get current count
            current_count = await self.redis.get(key)
            current_count = int(current_count) if current_count else 0
            
            # Get TTL
            ttl = await self.redis.ttl(key)
            if ttl == -1:  # Key exists but no expiration
                await self.redis.expire(key, window_seconds)
                ttl = window_seconds
            elif ttl == -2:  # Key doesn't exist
                ttl = window_seconds
            
            rate_limit_info = {
                "limit": limit,
                "remaining": max(0, limit - current_count - 1),
                "reset": datetime.utcnow() + timedelta(seconds=ttl),
                "retry_after": ttl if current_count >= limit else None
            }
            
            if current_count >= limit:
                return True, rate_limit_info
            
            # Increment counter
            await self.redis.incr(key)
            if current_count == 0:
                await self.redis.expire(key, window_seconds)
            
            return False, rate_limit_info
            
        except Exception as e:
            logger.error("Rate limiting error", identifier=identifier, error=str(e))
            # On error, allow the request (fail open)
            return False, {
                "limit": limit,
                "remaining": limit - 1,
                "reset": datetime.utcnow() + timedelta(seconds=window_seconds),
                "retry_after": None
            }


class CSRFProtection:
    """CSRF protection utilities"""
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def verify_csrf_token(token: str, session_token: str) -> bool:
        """Verify CSRF token against session token"""
        return secrets.compare_digest(token, session_token)


class InputSanitizer:
    """Input sanitization utilities"""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path separators and dangerous characters
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*', '\0']
        sanitized = filename
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            sanitized = f"{name[:max_name_length]}.{ext}" if ext else name[:255]
        
        return sanitized
    
    @staticmethod
    def sanitize_search_query(query: str) -> str:
        """Sanitize search query"""
        # Remove potentially dangerous characters for search
        sanitized = query.strip()
        
        # Remove SQL injection patterns (basic)
        dangerous_patterns = [
            '--', '/*', '*/', 'xp_', 'exec', 'execute', 
            'drop', 'create', 'alter', 'insert', 'update', 'delete'
        ]
        
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern.lower(), '')
            sanitized = sanitized.replace(pattern.upper(), '')
        
        # Limit length
        return sanitized[:1000]
    
    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """Validate UUID format"""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(uuid_string))


# Global security manager
security_manager = SecurityManager()

# Export convenience functions
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    return security_manager.create_access_token(data, expires_delta)

def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    return security_manager.create_refresh_token(data, expires_delta)

def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    return security_manager.verify_token(token, token_type)

def hash_password(password: str) -> str:
    return security_manager.hash_password(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return security_manager.verify_password(plain_password, hashed_password)

def hash_email(email: str) -> str:
    return security_manager.hash_email(email)

def hash_content(content: Union[str, bytes]) -> str:
    return security_manager.hash_content(content)


__all__ = [
    "SecurityManager",
    "RateLimiter", 
    "CSRFProtection",
    "InputSanitizer",
    "security_manager",
    "security",
    "create_access_token",
    "create_refresh_token",
    "verify_token", 
    "hash_password",
    "verify_password",
    "hash_email",
    "hash_content",
]