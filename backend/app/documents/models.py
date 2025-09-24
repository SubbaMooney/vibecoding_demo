from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    page_count = Column(Integer)
    text_content_length = Column(BigInteger)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String(50), default="uploaded")
    storage_path = Column(String(500), nullable=False)
    metadata = Column(JSON)
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename})>"