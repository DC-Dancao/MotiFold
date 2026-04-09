from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
    query = Column(Text, nullable=False)
    research_topic = Column(Text, nullable=True)
    report = Column(Text, nullable=True)
    notes_json = Column(Text, nullable=False, default="[]")
    queries_json = Column(Text, nullable=False, default="[]")
    level = Column(String, nullable=False, default="standard")
    iterations = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User")
    workspace = relationship("Workspace")
