import os
import re
from datetime import datetime
from typing import List, Dict, Union, Tuple, Optional
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    select,
    func
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

# Load environment variables from .env if present
load_dotenv()

Base = declarative_base()

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(255), index=True, nullable=True)
    name = Column(String(255), index=True, nullable=False)
    phone = Column(String(100), index=True, nullable=True)
    whatsapp = Column(String(255), nullable=True)
    category = Column(String(255), index=True, nullable=True)
    rating = Column(String(50), nullable=True)
    reviews = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    website = Column(Text, nullable=True)
    google_maps_url = Column(Text, nullable=True, index=True)
    whatsapp_status = Column(String(50), default="Pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "ID": self.id,
            "Query": self.query,
            "Name": self.name,
            "Phone": self.phone,
            "WhatsApp": self.whatsapp,
            "Category": self.category,
            "Rating": self.rating,
            "Reviews": self.reviews,
            "Address": self.address,
            "Website": self.website,
            "Google Maps URL": self.google_maps_url,
            "WhatsApp Status": self.whatsapp_status,
            "Created At": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "Updated At": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else ""
        }

def normalize_db_url(url: Optional[str] = None) -> str:
    """
    Returns sanitized database URL compatible with SQLAlchemy.
    Converts 'postgres://' to 'postgresql+psycopg2://'.
    Defaults to environment variable DATABASE_URL or local SQLite fallback.
    """
    if not url:
        try:
            import streamlit as st
            if "DATABASE_URL" in st.secrets:
                url = st.secrets["DATABASE_URL"]
        except Exception:
            pass
    if not url:
        url = os.environ.get("DATABASE_URL")
    if not url:
        url = "sqlite:///gmaps_leads_archive.db"

    url = url.strip()
    if url.startswith("postgres://"):
        url = re.sub(r"^postgres://", "postgresql+psycopg2://", url)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = re.sub(r"^postgresql://", "postgresql+psycopg2://", url)

    return url

def get_engine(db_url: Optional[str] = None):
    target_url = normalize_db_url(db_url)
    connect_args = {}
    if target_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(target_url, connect_args=connect_args, pool_pre_ping=True)

def test_connection(db_url: Optional[str] = None) -> Tuple[bool, str]:
    """Test connection to the remote or local database."""
    try:
        engine = get_engine(db_url)
        with engine.connect() as conn:
            # Run simple test query
            conn.execute(select(1))
        # Mask credentials in output message
        norm_url = normalize_db_url(db_url)
        safe_url = re.sub(r':([^@]+)@', ':****@', norm_url)
        return True, f"Successfully connected to database: {safe_url}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def init_db(db_url: Optional[str] = None):
    """Create database tables if they do not exist."""
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)

def save_leads_to_db(
    leads: Union[List[Dict], pd.DataFrame], 
    db_url: Optional[str] = None
) -> Dict[str, int]:
    """
    Saves a list of leads or DataFrame to the remote database.
    Performs intelligent deduplication based on Google Maps URL or (Name, Phone).
    Returns counts of inserted and updated/skipped records.
    """
    if isinstance(leads, pd.DataFrame):
        records = leads.to_dict("records")
    else:
        records = list(leads)

    if not records:
        return {"inserted": 0, "duplicates": 0, "total": 0}

    engine = get_engine(db_url)
    init_db(db_url)
    
    Session = sessionmaker(bind=engine)
    session = Session()

    inserted = 0
    duplicates = 0

    try:
        for r in records:
            name = str(r.get("Name") or "").strip()
            if not name:
                continue

            phone = str(r.get("Phone") or "").strip()
            maps_url = str(r.get("Google Maps URL") or "").strip()
            query = str(r.get("Query") or "").strip()
            category = str(r.get("Category") or "").strip()
            rating = str(r.get("Rating") or "").strip()
            reviews = str(r.get("Reviews") or "").strip()
            address = str(r.get("Address") or "").strip()
            website = str(r.get("Website") or "").strip()
            whatsapp = str(r.get("WhatsApp") or "").strip()

            # Check for existing lead by Google Maps URL or by (Name + Phone)
            existing = None
            if maps_url and len(maps_url) > 10:
                existing = session.query(Lead).filter(Lead.google_maps_url == maps_url).first()
            if not existing and phone:
                existing = session.query(Lead).filter(
                    func.lower(Lead.name) == name.lower(),
                    Lead.phone == phone
                ).first()

            if existing:
                # Update existing lead with latest info if missing
                if not existing.phone and phone:
                    existing.phone = phone
                if not existing.whatsapp and whatsapp:
                    existing.whatsapp = whatsapp
                if not existing.website and website:
                    existing.website = website
                if not existing.address and address:
                    existing.address = address
                existing.updated_at = datetime.utcnow()
                duplicates += 1
            else:
                new_lead = Lead(
                    query=query,
                    name=name,
                    phone=phone,
                    whatsapp=whatsapp,
                    category=category,
                    rating=rating,
                    reviews=reviews,
                    address=address,
                    website=website,
                    google_maps_url=maps_url,
                    whatsapp_status="Pending",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(new_lead)
                inserted += 1

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

    return {"inserted": inserted, "duplicates": duplicates, "total": len(records)}

def fetch_leads_from_db(
    db_url: Optional[str] = None,
    query_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    has_phone_only: bool = False,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """Fetch stored leads from the database with optional filters."""
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        q = session.query(Lead).order_by(Lead.id.desc())

        if query_filter:
            q = q.filter(Lead.query.ilike(f"%{query_filter}%"))
        if category_filter:
            q = q.filter(Lead.category.ilike(f"%{category_filter}%"))
        if has_phone_only:
            q = q.filter(Lead.phone.isnot(None), Lead.phone != "", Lead.phone != "N/A")
        if limit:
            q = q.limit(limit)

        leads = q.all()
        data = [lead.to_dict() for lead in leads]
        return pd.DataFrame(data)
    finally:
        session.close()

def get_db_stats(db_url: Optional[str] = None) -> Dict:
    """Get high-level summary statistics of stored leads."""
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        total_leads = session.query(func.count(Lead.id)).scalar() or 0
        leads_with_phone = session.query(func.count(Lead.id)).filter(
            Lead.phone.isnot(None), Lead.phone != "", Lead.phone != "N/A"
        ).scalar() or 0
        unique_categories = session.query(func.count(func.distinct(Lead.category))).scalar() or 0
        unique_queries = session.query(func.count(func.distinct(Lead.query))).scalar() or 0
        
        return {
            "total_leads": total_leads,
            "leads_with_phone": leads_with_phone,
            "unique_categories": unique_categories,
            "unique_queries": unique_queries
        }
    finally:
        session.close()

def update_whatsapp_status(phone: str, status: str, db_url: Optional[str] = None):
    """Update messaging status (e.g. Sent, Invalid Number) for a phone."""
    if not phone:
        return
    engine = get_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.query(Lead).filter(Lead.phone == phone).update(
            {"whatsapp_status": status, "updated_at": datetime.utcnow()}
        )
        session.commit()
    finally:
        session.close()
