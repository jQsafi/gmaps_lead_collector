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

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), index=True, nullable=False)
    message_template = Column(Text, nullable=False)
    locations = Column(Text, nullable=True)
    status = Column(String(50), default="Draft", index=True) # Draft, Running, Paused, Stopped, Completed
    total_scraped = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    total_skipped = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> Dict:
        return {
            "ID": self.id,
            "Name": self.name,
            "Message Template": self.message_template,
            "Locations": self.locations or "",
            "Status": self.status,
            "Total Scraped": self.total_scraped or 0,
            "Total Sent": self.total_sent or 0,
            "Total Failed": self.total_failed or 0,
            "Total Skipped": self.total_skipped or 0,
            "Created At": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "Completed At": self.completed_at.strftime("%Y-%m-%d %H:%M:%S") if self.completed_at else ""
        }

class CampaignMessage(Base):
    __tablename__ = "campaign_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, index=True, nullable=False)
    campaign_name = Column(String(255), index=True, nullable=False)
    lead_name = Column(String(255), nullable=True)
    phone = Column(String(100), index=True, nullable=False)
    message_text = Column(Text, nullable=True)
    status = Column(String(50), default="Pending", index=True) # Sent, Failed, Invalid Number, Skipped Duplicate
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> Dict:
        return {
            "ID": self.id,
            "Campaign ID": self.campaign_id,
            "Campaign Name": self.campaign_name,
            "Business Name": self.lead_name or "",
            "Phone": self.phone or "",
            "Message Text": self.message_text or "",
            "Status": self.status or "",
            "Error Details": self.error_message or "",
            "Date & Time": self.sent_at.strftime("%Y-%m-%d %H:%M:%S") if self.sent_at else ""
        }

class SavedMessage(Base):
    __tablename__ = "saved_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "ID": self.id,
            "Title": self.title,
            "Content": self.content,
            "Created At": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
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

# ----------------- Campaign Management & Reporting ----------------- #

def create_campaign(
    name: str, 
    message_template: str, 
    locations: str = "", 
    db_url: Optional[str] = None
) -> int:
    """Creates a new campaign record and returns its ID."""
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        camp = Campaign(
            name=name.strip(),
            message_template=message_template.strip(),
            locations=locations.strip(),
            status="Draft",
            total_scraped=0,
            total_sent=0,
            total_failed=0,
            total_skipped=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(camp)
        session.commit()
        camp_id = camp.id
        return camp_id
    finally:
        session.close()

def get_campaign(campaign_id: int, db_url: Optional[str] = None) -> Optional[Dict]:
    """Retrieve details of a single campaign by ID."""
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        camp = session.query(Campaign).filter(Campaign.id == campaign_id).first()
        return camp.to_dict() if camp else None
    finally:
        session.close()

def get_all_campaigns(db_url: Optional[str] = None) -> pd.DataFrame:
    """Retrieve all campaigns as a DataFrame."""
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        camps = session.query(Campaign).order_by(Campaign.id.desc()).all()
        return pd.DataFrame([c.to_dict() for c in camps]) if camps else pd.DataFrame()
    finally:
        session.close()

def update_campaign_status(campaign_id: int, status: str, db_url: Optional[str] = None):
    """Update state of a campaign (e.g. Running, Paused, Stopped, Completed)."""
    engine = get_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        update_data = {"status": status, "updated_at": datetime.utcnow()}
        if status in ("Completed", "Stopped"):
            update_data["completed_at"] = datetime.utcnow()
        session.query(Campaign).filter(Campaign.id == campaign_id).update(update_data)
        session.commit()
    finally:
        session.close()

def update_campaign_stats(
    campaign_id: int, 
    scraped_delta: int = 0, 
    sent_delta: int = 0, 
    failed_delta: int = 0, 
    skipped_delta: int = 0, 
    db_url: Optional[str] = None
):
    """Increment execution metrics on a campaign."""
    engine = get_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        camp = session.query(Campaign).filter(Campaign.id == campaign_id).first()
        if camp:
            if scraped_delta:
                camp.total_scraped = (camp.total_scraped or 0) + scraped_delta
            if sent_delta:
                camp.total_sent = (camp.total_sent or 0) + sent_delta
            if failed_delta:
                camp.total_failed = (camp.total_failed or 0) + failed_delta
            if skipped_delta:
                camp.total_skipped = (camp.total_skipped or 0) + skipped_delta
            camp.updated_at = datetime.utcnow()
            session.commit()
    finally:
        session.close()

def normalize_phone_key(phone: str) -> str:
    """Strip all non-digits for consistent comparison."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', str(phone))
    return digits[-10:] if len(digits) >= 10 else digits

def has_campaign_messaged_phone(
    campaign_id: int, 
    phone: str, 
    db_url: Optional[str] = None
) -> bool:
    """
    Checks if a phone number was already sent a message under the same campaign.
    Prevents duplicate messages to the same recipient in a campaign.
    """
    if not phone or not campaign_id:
        return False
    norm_phone = normalize_phone_key(phone)
    if not norm_phone:
        return False

    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Check exact phone match or last 10 digits
        existing = session.query(CampaignMessage).filter(
            CampaignMessage.campaign_id == campaign_id,
            CampaignMessage.status.in_(["Sent", "Pending"])
        ).all()
        for msg in existing:
            if normalize_phone_key(msg.phone) == norm_phone:
                return True
        return False
    finally:
        session.close()

def log_campaign_message(
    campaign_id: int,
    campaign_name: str,
    lead_name: str,
    phone: str,
    message_text: str,
    status: str,
    error_message: Optional[str] = None,
    db_url: Optional[str] = None
) -> Dict:
    """Records an outreach attempt under a campaign."""
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        record = CampaignMessage(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            lead_name=lead_name,
            phone=phone,
            message_text=message_text,
            status=status,
            error_message=error_message,
            sent_at=datetime.utcnow()
        )
        session.add(record)
        session.commit()
        return record.to_dict()
    finally:
        session.close()

def fetch_campaign_reports(
    campaign_id: Optional[int] = None,
    start_date = None,
    end_date = None,
    status: Optional[str] = None,
    limit: Optional[int] = 1000,
    db_url: Optional[str] = None
) -> pd.DataFrame:
    """
    Queries campaign outreach records filtered by Date & Time, Campaign, and Status.
    """
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        q = session.query(CampaignMessage).order_by(CampaignMessage.id.desc())
        if campaign_id:
            q = q.filter(CampaignMessage.campaign_id == campaign_id)
        if status and status != "All":
            q = q.filter(CampaignMessage.status == status)
        if start_date:
            s_dt = datetime.combine(start_date, datetime.min.time())
            q = q.filter(CampaignMessage.sent_at >= s_dt)
        if end_date:
            e_dt = datetime.combine(end_date, datetime.max.time())
            q = q.filter(CampaignMessage.sent_at <= e_dt)
        if limit:
            q = q.limit(limit)

        records = q.all()
        return pd.DataFrame([r.to_dict() for r in records]) if records else pd.DataFrame()
    finally:
        session.close()

def save_message_template(title: str, content: str, db_url: Optional[str] = None):
    """Saves a message template for instant reuse without re-typing."""
    if not content or not content.strip():
        return
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Check if already exists
        existing = session.query(SavedMessage).filter(SavedMessage.content == content.strip()).first()
        if not existing:
            tpl = SavedMessage(
                title=title.strip() or f"Template {datetime.utcnow().strftime('%b %d, %H:%M')}",
                content=content.strip(),
                created_at=datetime.utcnow()
            )
            session.add(tpl)
            session.commit()
    finally:
        session.close()

def get_saved_message_templates(db_url: Optional[str] = None) -> List[Dict]:
    """Retrieves all stored message templates."""
    engine = get_engine(db_url)
    init_db(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        tpls = session.query(SavedMessage).order_by(SavedMessage.id.desc()).all()
        return [t.to_dict() for t in tpls]
    finally:
        session.close()
