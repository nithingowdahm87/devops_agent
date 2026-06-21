import hashlib
import json
import secrets
from sqlalchemy.orm import Session
from src.db.models_apikey import ApiKey

def _hash_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()

def create_api_key(db: Session, user_id: int, name: str, scopes: list = None, expires_at=None):
    """Generate a new API key. Returns (db_key, plain_key)."""
    plain_key = f"da_{secrets.token_urlsafe(32)}"
    db_key = ApiKey(
        user_id=user_id,
        name=name,
        key_hash=_hash_key(plain_key),
        scopes=json.dumps(scopes) if scopes else None,
        expires_at=expires_at,
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return db_key, plain_key

def get_api_key_by_hash(db: Session, key_hash: str):
    from datetime import datetime
    key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True).first()
    if key and key.expires_at and key.expires_at < datetime.now():
        return None
    return key

def revoke_api_key(db: Session, key_id: int, user_id: int):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user_id).first()
    if key:
        key.is_active = False
        db.commit()
        db.refresh(key)
    return key

def list_api_keys(db: Session, user_id: int, skip=0, limit=100):
    return db.query(ApiKey).filter(ApiKey.user_id == user_id, ApiKey.is_active == True).offset(skip).limit(limit).all()