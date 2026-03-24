"""
Credential model for encrypted API keys and cookies.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class Credential(Base):
    """Encrypted user credentials for API keys and TradingView cookies."""
    
    __tablename__ = "credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Credential type
    credential_type = Column(String(50), nullable=False)  # tv_cookies, deepseek_key, claude_key
    
    # Encrypted value (Fernet encrypted)
    encrypted_value = Column(Text, nullable=False)
    
    # Metadata
    label = Column(String(100), nullable=True)  # User-friendly label
    is_valid = Column(Integer, default=1)  # Last validation status (1=valid, 0=invalid, -1=unchecked)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="credentials")
    
    def __repr__(self):
        return f"<Credential {self.credential_type} for user {self.user_id}>"
