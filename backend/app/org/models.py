"""Organization models in public schema."""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {'schema': 'public'}

    id = Column(String(50), primary_key=True)  # slug is the PK
    name = Column(String, nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, server_default='active')  # provisioning, active, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")

class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = {'schema': 'public'}

    id = Column(String(100), primary_key=True)  # "{org_slug}_{user_id}"
    organization_id = Column(String(50), ForeignKey("public.organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, server_default="member")  # owner, admin, member
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="members")

    __table_args__ = (UniqueConstraint('organization_id', 'user_id', name='uq_org_member'),)
