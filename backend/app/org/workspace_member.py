"""WorkspaceMember model for workspace-level permissions in org schemas."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, server_default="member")  # owner, member, viewer
    invited_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('workspace_id', 'user_id', name='uq_ws_member'),)
