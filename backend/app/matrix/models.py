from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, func
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


class MatrixCell(Base):
    __tablename__ = "matrix_cells"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("morphological_analyses.id"), nullable=False)
    pair_key = Column(String(20), nullable=False)  # e.g., "0_2"
    state_pair = Column(String(20), nullable=False)  # e.g., "1_3"
    status = Column(String(10), nullable=False)  # green, yellow, red
    contradiction_type = Column(String(1), nullable=True)  # L, E, N
    reason = Column(Text, nullable=True)

    analysis = relationship("MorphologicalAnalysis", back_populates="matrix_cells")


class SolutionCluster(Base):
    __tablename__ = "solution_clusters"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("morphological_analyses.id"), nullable=False)
    cluster_id = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    solution_indices = Column(JSON, nullable=False)  # List[int]
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis = relationship("MorphologicalAnalysis", back_populates="solution_clusters")


class AHPWeight(Base):
    __tablename__ = "ahp_weights"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("morphological_analyses.id"), nullable=False)
    criteria = Column(JSON, nullable=False)  # [{"name": "Cost", "weight": 0.25}, ...]
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis = relationship("MorphologicalAnalysis", back_populates="ahp_weights")

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
    matrix_cells = relationship("MatrixCell", back_populates="analysis")
    solution_clusters = relationship("SolutionCluster", back_populates="analysis")
    ahp_weights = relationship("AHPWeight", back_populates="analysis")
