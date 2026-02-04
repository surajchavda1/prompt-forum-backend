"""
Credit Package Models
Predefined credit packages for purchase
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class PackageStatus(str, Enum):
    """Package status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class CreditPackageInDB(BaseModel):
    """Credit package in database"""
    package_id: str         # Unique package identifier
    name: str               # Display name
    description: str = ""
    
    # Pricing
    price: float            # Price in currency
    credits: float          # Credits user receives
    bonus_credits: float = 0.0  # Bonus credits (if any)
    total_credits: float    # price + bonus
    currency: str = "INR"
    
    # Discount info
    discount_percentage: float = 0.0
    original_price: Optional[float] = None
    
    # Limits
    min_quantity: int = 1
    max_quantity: int = 1
    
    # Display
    is_popular: bool = False
    is_best_value: bool = False
    badge: Optional[str] = None  # "Most Popular", "Best Value", etc.
    sort_order: int = 0
    
    # Status
    status: PackageStatus = PackageStatus.ACTIVE
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreditPackageResponse(BaseModel):
    """Credit package response"""
    package_id: str
    name: str
    description: str
    price: float
    credits: float
    bonus_credits: float
    total_credits: float
    currency: str
    discount_percentage: float
    original_price: Optional[float]
    is_popular: bool
    is_best_value: bool
    badge: Optional[str]


class CreditPackageListResponse(BaseModel):
    """Credit package list response"""
    packages: List[CreditPackageResponse]
    currency: str
