from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    word = Column(String, nullable=False)
    source_prompt = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User")

class MorphologicalAnalysis(Base):
    __tablename__ = "morphological_analyses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
    focus_question = Column(String, nullable=False)
    parameters_json = Column(Text, nullable=False, default="[]") # Store the list of parameters as JSON
    matrix_json = Column(Text, nullable=False, default="{}") # Store the evaluation matrix as JSON
    status = Column(String, nullable=False, default="pending") # pending, generating_parameters, parameters_ready, generate_failed, evaluating_matrix, matrix_ready, evaluate_failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User")
    workspace = relationship("Workspace")
