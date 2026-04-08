from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class BlackboardData(Base):
    __tablename__ = "blackboards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
    topic = Column(String, nullable=False)
    content_json = Column(Text, nullable=False, default="[]") # Store the generated StepsData JSON
    status = Column(String, nullable=False, default="pending") # pending, generating, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User")
    workspace = relationship("Workspace")
