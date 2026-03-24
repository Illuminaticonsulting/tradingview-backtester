"""
Credentials routes - Manage user API keys and TradingView cookies.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models.user import User
from ..models.credential import Credential
from ..routes.auth import get_current_user
from ..services.credential_vault import encrypt_credential, decrypt_credential

router = APIRouter()


# Schemas
class CredentialCreate(BaseModel):
    credential_type: str  # tv_cookies, deepseek_key, claude_key
    value: str
    label: Optional[str] = None


class CredentialResponse(BaseModel):
    id: int
    credential_type: str
    label: Optional[str]
    is_valid: int
    created_at: datetime
    updated_at: datetime
    # Never return the actual value!
    has_value: bool = True

    class Config:
        from_attributes = True


class CredentialUpdate(BaseModel):
    value: Optional[str] = None
    label: Optional[str] = None


# Routes
@router.post("/", response_model=CredentialResponse)
async def create_or_update_credential(
    data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create or update a credential (API key or cookies)."""
    valid_types = {"tv_cookies", "deepseek_key", "claude_key"}
    if data.credential_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid credential type. Must be one of: {valid_types}"
        )
    
    # Check existing
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == current_user.id,
            Credential.credential_type == data.credential_type
        )
    )
    existing = result.scalar_one_or_none()
    
    encrypted_value = encrypt_credential(data.value)
    
    if existing:
        # Update
        existing.encrypted_value = encrypted_value
        existing.label = data.label or existing.label
        existing.is_valid = -1  # Mark as unchecked
        existing.updated_at = datetime.utcnow()
        credential = existing
    else:
        # Create
        credential = Credential(
            user_id=current_user.id,
            credential_type=data.credential_type,
            encrypted_value=encrypted_value,
            label=data.label,
            is_valid=-1
        )
        db.add(credential)
    
    await db.commit()
    await db.refresh(credential)
    
    return CredentialResponse(
        id=credential.id,
        credential_type=credential.credential_type,
        label=credential.label,
        is_valid=credential.is_valid,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
        has_value=True
    )


@router.get("/", response_model=list[CredentialResponse])
async def list_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's credentials (values hidden)."""
    result = await db.execute(
        select(Credential).where(Credential.user_id == current_user.id)
    )
    credentials = result.scalars().all()
    
    return [
        CredentialResponse(
            id=c.id,
            credential_type=c.credential_type,
            label=c.label,
            is_valid=c.is_valid,
            created_at=c.created_at,
            updated_at=c.updated_at,
            has_value=bool(c.encrypted_value)
        )
        for c in credentials
    ]


@router.get("/status")
async def get_credentials_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get quick status of which credentials are configured."""
    result = await db.execute(
        select(Credential).where(Credential.user_id == current_user.id)
    )
    credentials = {c.credential_type: c.is_valid for c in result.scalars()}
    
    return {
        "tv_cookies": {
            "configured": "tv_cookies" in credentials,
            "valid": credentials.get("tv_cookies", -1) == 1
        },
        "deepseek_key": {
            "configured": "deepseek_key" in credentials,
            "valid": credentials.get("deepseek_key", -1) == 1
        },
        "claude_key": {
            "configured": "claude_key" in credentials,
            "valid": credentials.get("claude_key", -1) == 1
        }
    }


@router.delete("/{credential_type}")
async def delete_credential(
    credential_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a credential."""
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == current_user.id,
            Credential.credential_type == credential_type
        )
    )
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    await db.delete(credential)
    await db.commit()
    
    return {"status": "deleted"}


@router.post("/{credential_type}/validate")
async def validate_credential(
    credential_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate a credential (test if it works)."""
    result = await db.execute(
        select(Credential).where(
            Credential.user_id == current_user.id,
            Credential.credential_type == credential_type
        )
    )
    credential = result.scalar_one_or_none()
    
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    value = decrypt_credential(credential.encrypted_value)
    is_valid = False
    error = None
    
    try:
        if credential_type == "deepseek_key":
            # Test DeepSeek API
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {value}"},
                    json={"model": "deepseek-reasoner", "messages": [{"role": "user", "content": "test"}], "max_tokens": 1},
                    timeout=10.0
                )
                is_valid = resp.status_code in (200, 429)  # 429 = rate limited but key is valid
                
        elif credential_type == "claude_key":
            # Test Claude API
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": value,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={"model": "claude-3-haiku-20240307", "max_tokens": 1, "messages": [{"role": "user", "content": "test"}]},
                    timeout=10.0
                )
                is_valid = resp.status_code in (200, 429)
                
        elif credential_type == "tv_cookies":
            # Test TradingView cookies by fetching user page
            import httpx
            import json
            cookies = json.loads(value) if value.startswith('[') else {}
            cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in (cookies if isinstance(cookies, list) else [])])
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://www.tradingview.com/u/",
                    headers={"Cookie": cookie_header},
                    follow_redirects=True,
                    timeout=10.0
                )
                # If redirected to login, cookies are invalid
                is_valid = "signin" not in str(resp.url)
                
    except Exception as e:
        error = str(e)
        is_valid = False
    
    # Update validity status
    credential.is_valid = 1 if is_valid else 0
    await db.commit()
    
    return {
        "valid": is_valid,
        "error": error
    }
