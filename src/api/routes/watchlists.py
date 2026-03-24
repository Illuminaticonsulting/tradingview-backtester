"""
Watchlist routes - Import and manage symbol watchlists.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
import csv
import io

from ..database import get_db
from ..models.user import User
from ..models.watchlist import Watchlist, WatchlistSymbol
from ..routes.auth import get_current_user
from ..services.watchlist_parser import parse_tradingview_watchlist_url

router = APIRouter()


# Schemas
class SymbolInput(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    category: Optional[str] = None


class WatchlistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    symbols: list[SymbolInput] = []


class WatchlistImportURL(BaseModel):
    url: str
    name: Optional[str] = None


class WatchlistResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    source: str
    symbol_count: int
    symbols: list[dict] = []

    class Config:
        from_attributes = True


# Routes
@router.post("/", response_model=WatchlistResponse)
async def create_watchlist(
    data: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new watchlist with symbols."""
    watchlist = Watchlist(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        source="manual"
    )
    db.add(watchlist)
    await db.flush()  # Get watchlist.id
    
    # Add symbols
    for i, sym in enumerate(data.symbols):
        exchange = sym.exchange or ""
        full_symbol = f"{exchange}:{sym.symbol}" if exchange else sym.symbol
        
        symbol = WatchlistSymbol(
            watchlist_id=watchlist.id,
            symbol=sym.symbol,
            exchange=exchange,
            full_symbol=full_symbol,
            category=sym.category,
            position=i
        )
        db.add(symbol)
    
    await db.commit()
    await db.refresh(watchlist)
    
    # Load symbols for response
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.symbols))
        .where(Watchlist.id == watchlist.id)
    )
    watchlist = result.scalar_one()
    
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        source=watchlist.source,
        symbol_count=len(watchlist.symbols),
        symbols=[{
            "symbol": s.symbol,
            "exchange": s.exchange,
            "full_symbol": s.full_symbol,
            "category": s.category
        } for s in watchlist.symbols]
    )


@router.post("/import/url", response_model=WatchlistResponse)
async def import_watchlist_from_url(
    data: WatchlistImportURL,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Import watchlist from TradingView public URL."""
    try:
        parsed = await parse_tradingview_watchlist_url(data.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse watchlist: {str(e)}")
    
    name = data.name or parsed.get("name", "Imported Watchlist")
    
    watchlist = Watchlist(
        user_id=current_user.id,
        name=name,
        description=f"Imported from TradingView",
        source="url",
        source_url=data.url
    )
    db.add(watchlist)
    await db.flush()
    
    # Add parsed symbols
    for i, sym in enumerate(parsed.get("symbols", [])):
        symbol = WatchlistSymbol(
            watchlist_id=watchlist.id,
            symbol=sym["symbol"],
            exchange=sym.get("exchange", ""),
            full_symbol=sym.get("full_symbol", sym["symbol"]),
            category=sym.get("category"),
            position=i
        )
        db.add(symbol)
    
    await db.commit()
    await db.refresh(watchlist)
    
    # Reload with symbols
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.symbols))
        .where(Watchlist.id == watchlist.id)
    )
    watchlist = result.scalar_one()
    
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        source=watchlist.source,
        symbol_count=len(watchlist.symbols),
        symbols=[{
            "symbol": s.symbol,
            "exchange": s.exchange,
            "full_symbol": s.full_symbol,
            "category": s.category
        } for s in watchlist.symbols]
    )


@router.post("/import/csv", response_model=WatchlistResponse)
async def import_watchlist_from_csv(
    file: UploadFile = File(...),
    name: str = "CSV Import",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Import watchlist from CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be CSV")
    
    content = await file.read()
    text = content.decode('utf-8')
    
    watchlist = Watchlist(
        user_id=current_user.id,
        name=name,
        description=f"Imported from {file.filename}",
        source="csv"
    )
    db.add(watchlist)
    await db.flush()
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(text))
    for i, row in enumerate(reader):
        # Support various column names
        symbol = row.get('symbol') or row.get('Symbol') or row.get('ticker') or row.get('Ticker', '')
        exchange = row.get('exchange') or row.get('Exchange', '')
        category = row.get('category') or row.get('Category', '')
        
        if not symbol:
            continue
        
        full_symbol = f"{exchange}:{symbol}" if exchange else symbol
        
        sym = WatchlistSymbol(
            watchlist_id=watchlist.id,
            symbol=symbol,
            exchange=exchange,
            full_symbol=full_symbol,
            category=category,
            position=i
        )
        db.add(sym)
    
    await db.commit()
    await db.refresh(watchlist)
    
    # Reload with symbols
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.symbols))
        .where(Watchlist.id == watchlist.id)
    )
    watchlist = result.scalar_one()
    
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        source=watchlist.source,
        symbol_count=len(watchlist.symbols),
        symbols=[{
            "symbol": s.symbol,
            "exchange": s.exchange,
            "full_symbol": s.full_symbol,
            "category": s.category
        } for s in watchlist.symbols]
    )


@router.get("/", response_model=list[WatchlistResponse])
async def list_watchlists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's watchlists."""
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.symbols))
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.created_at.desc())
    )
    watchlists = result.scalars().all()
    
    return [
        WatchlistResponse(
            id=w.id,
            name=w.name,
            description=w.description,
            source=w.source,
            symbol_count=len(w.symbols),
            symbols=[{
                "symbol": s.symbol,
                "exchange": s.exchange,
                "full_symbol": s.full_symbol,
                "category": s.category
            } for s in w.symbols]
        )
        for w in watchlists
    ]


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
async def get_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get watchlist details."""
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.symbols))
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id)
    )
    watchlist = result.scalar_one_or_none()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        source=watchlist.source,
        symbol_count=len(watchlist.symbols),
        symbols=[{
            "symbol": s.symbol,
            "exchange": s.exchange,
            "full_symbol": s.full_symbol,
            "category": s.category
        } for s in watchlist.symbols]
    )


@router.delete("/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a watchlist."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.user_id == current_user.id
        )
    )
    watchlist = result.scalar_one_or_none()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    await db.delete(watchlist)
    await db.commit()
    
    return {"status": "deleted"}
