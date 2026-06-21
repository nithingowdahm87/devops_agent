"""API Key management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.db.database import get_db
from src.db import crud, models
from src.db.crud_apikey import create_api_key, revoke_api_key, list_api_keys
from src.schemas_apikey import ApiKeyCreate, ApiKeyRead, ApiKeyCreatedResponse
from src.api.dependencies import get_current_user

router = APIRouter()

@router.post("/", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key_endpoint(
    api_key_data: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new API key. Returns the plain key only once."""
    db_key, plain_key = create_api_key(
        db, user_id=current_user.id, name=api_key_data.name, scopes=api_key_data.scopes
    )
    return ApiKeyCreatedResponse(
        id=db_key.id,
        name=db_key.name,
        key=plain_key,
        created_at=db_key.created_at,
    )

@router.get("/", response_model=list[ApiKeyRead])
def list_api_keys_endpoint(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all active API keys for the current user."""
    return list_api_keys(db, current_user.id)

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key_endpoint(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Revoke an API key."""
    key = revoke_api_key(db, key_id, current_user.id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return None