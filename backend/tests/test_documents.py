import pytest
import asyncio
import io
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import get_db, Base
from app.documents.models import Document
from app.documents.service import DocumentService
from app.documents.storage import DocumentStorage
from app.documents.processing import PDFProcessor

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_documents.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Override the dependency
app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def client():
    """Test client fixture."""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    """Database session fixture."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    # This is a minimal valid PDF content for testing
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""

@pytest.fixture
def mock_upload_file(sample_pdf_content):
    """Mock UploadFile for testing."""
    file = io.BytesIO(sample_pdf_content)
    upload_file = UploadFile(
        file=file,
        filename="test.pdf",
        headers={"content-type": "application/pdf"}
    )
    upload_file.size = len(sample_pdf_content)
    return upload_file

class TestDocumentAPI:
    """Test cases for document API endpoints."""
    
    @patch('app.documents.service.DocumentService.upload_document')
    def test_upload_document_success(self, mock_upload, client, sample_pdf_content):
        """Test successful document upload."""
        # Mock the service response
        mock_document = Document(
            id="123e4567-e89b-12d3-a456-426614174000",
            filename="test.pdf",
            original_filename="test.pdf",
            file_size=len(sample_pdf_content),
            mime_type="application/pdf",
            processing_status="uploaded",
            storage_path="/storage/test.pdf"
        )
        mock_upload.return_value = mock_document
        
        # Test upload
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", sample_pdf_content, "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["processing_status"] == "uploaded"
    
    def test_upload_invalid_file_type(self, client):
        """Test upload with invalid file type."""
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"Hello World", "text/plain")}
        )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]
    
    def test_upload_file_too_large(self, client):
        """Test upload with file too large."""
        large_content = b"x" * (51 * 1024 * 1024)  # 51MB
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.pdf", large_content, "application/pdf")}
        )
        
        assert response.status_code == 413
        assert "exceeds maximum allowed size" in response.json()["detail"]

class TestDocumentService:
    """Test cases for DocumentService."""
    
    @pytest.mark.asyncio
    async def test_upload_document(self, db_session, mock_upload_file):
        """Test document service upload."""
        service = DocumentService(db_session)
        
        with patch.object(service.pdf_processor, 'validate_pdf') as mock_validate:
            with patch.object(service.storage, 'store_file') as mock_store:
                # Mock validation
                mock_validate.return_value = {
                    "is_valid": True,
                    "is_encrypted": False,
                    "page_count": 1,
                    "file_size": 1000
                }
                
                # Mock storage
                mock_store.return_value = {
                    "storage_path": "/storage/test.pdf",
                    "secure_filename": "secure_test.pdf",
                    "original_dir": "/storage/original",
                    "processed_dir": "/storage/processed",
                    "metadata_dir": "/storage/metadata",
                    "file_size": 1000
                }
                
                # Test upload
                document = await service.upload_document(mock_upload_file)
                
                assert document.original_filename == "test.pdf"
                assert document.processing_status == "uploaded"
                assert document.file_size == 1000
    
    @pytest.mark.asyncio
    async def test_list_documents(self, db_session):
        """Test document listing with pagination."""
        service = DocumentService(db_session)
        
        # Create test documents
        for i in range(5):
            doc = Document(
                filename=f"test_{i}.pdf",
                original_filename=f"test_{i}.pdf",
                file_size=1000,
                mime_type="application/pdf",
                processing_status="ready",
                storage_path=f"/storage/test_{i}.pdf"
            )
            db_session.add(doc)
        db_session.commit()
        
        # Test listing
        documents, total = await service.list_documents(page=1, page_size=3)
        
        assert len(documents) == 3
        assert total == 5
    
    @pytest.mark.asyncio
    async def test_delete_document(self, db_session):
        """Test document deletion."""
        service = DocumentService(db_session)
        
        # Create test document
        doc = Document(
            filename="test.pdf",
            original_filename="test.pdf",
            file_size=1000,
            mime_type="application/pdf",
            processing_status="ready",
            storage_path="/storage/test.pdf"
        )
        db_session.add(doc)
        db_session.commit()
        document_id = str(doc.id)
        
        with patch.object(service.storage, 'delete_file') as mock_delete:
            mock_delete.return_value = True
            
            # Test deletion
            result = await service.delete_document(document_id)
            
            assert result is True
            # Verify document is deleted from database
            deleted_doc = db_session.query(Document).filter(Document.id == doc.id).first()
            assert deleted_doc is None

class TestPDFProcessor:
    """Test cases for PDF processing."""
    
    @pytest.mark.asyncio
    async def test_extract_text_success(self, sample_pdf_content):
        """Test successful text extraction."""
        processor = PDFProcessor()
        
        with patch('PyPDF2.PdfReader') as mock_reader:
            # Mock PDF reader
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Hello World"
            
            mock_pdf = MagicMock()
            mock_pdf.is_encrypted = False
            mock_pdf.pages = [mock_page]
            mock_pdf.metadata = {"/Title": "Test PDF"}
            
            mock_reader.return_value = mock_pdf
            
            # Test extraction
            result = await processor.extract_text(sample_pdf_content, "test.pdf")
            
            assert result["processing_status"] == "success"
            assert "Hello World" in result["text"]
            assert result["page_count"] == 1
    
    @pytest.mark.asyncio
    async def test_validate_pdf_encrypted(self, sample_pdf_content):
        """Test PDF validation with encrypted file."""
        processor = PDFProcessor()
        
        with patch('PyPDF2.PdfReader') as mock_reader:
            mock_pdf = MagicMock()
            mock_pdf.is_encrypted = True
            mock_reader.return_value = mock_pdf
            
            # Test validation
            result = await processor.validate_pdf(sample_pdf_content)
            
            assert result["is_valid"] is False
            assert result["is_encrypted"] is True
            assert "password protected" in result["error_message"]
    
    @pytest.mark.asyncio
    async def test_preprocess_text(self):
        """Test text preprocessing."""
        processor = PDFProcessor()
        
        # Test text with various issues
        raw_text = "Hello   World\u00A0\u200BThis is a "test"\nwith—various–issues…"
        
        processed = await processor._preprocess_text(raw_text)
        
        assert "Hello World" in processed
        assert '"test"' in processed
        assert "various-issues..." in processed
        assert "\u00A0" not in processed

class TestDocumentStorage:
    """Test cases for document storage."""
    
    @pytest.mark.asyncio
    async def test_store_file(self):
        """Test file storage."""
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            with patch('builtins.open', create=True) as mock_open:
                with patch('pathlib.Path.exists') as mock_exists:
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_exists.return_value = True
                        mock_stat.return_value.st_size = 1000
                        
                        storage = DocumentStorage("/tmp/test_storage")
                        
                        result = await storage.store_file(
                            b"test content",
                            "test.pdf",
                            "pdf"
                        )
                        
                        assert "storage_path" in result
                        assert "secure_filename" in result
                        assert result["file_size"] == 12
    
    @pytest.mark.asyncio
    async def test_delete_file(self):
        """Test file deletion."""
        with patch('pathlib.Path.exists') as mock_exists:
            with patch('pathlib.Path.unlink') as mock_unlink:
                mock_exists.return_value = True
                
                storage = DocumentStorage("/tmp/test_storage")
                
                result = await storage.delete_file("/tmp/test_storage/test.pdf")
                
                assert result is True
                mock_unlink.assert_called()

class TestErrorHandling:
    """Test cases for error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_corrupted_pdf_handling(self, db_session):
        """Test handling of corrupted PDF files."""
        service = DocumentService(db_session)
        
        # Create mock corrupted file
        corrupted_content = b"This is not a PDF file"
        mock_file = io.BytesIO(corrupted_content)
        upload_file = UploadFile(
            file=mock_file,
            filename="corrupted.pdf",
            headers={"content-type": "application/pdf"}
        )
        upload_file.size = len(corrupted_content)
        
        with pytest.raises(ValueError):
            await service.upload_document(upload_file)
    
    def test_invalid_document_id_format(self, client):
        """Test handling of invalid document ID format."""
        response = client.get("/api/v1/documents/invalid-id")
        
        assert response.status_code == 400
        assert "Invalid document ID format" in response.json()["detail"]
    
    def test_document_not_found(self, client):
        """Test handling of non-existent document."""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        response = client.get(f"/api/v1/documents/{valid_uuid}")
        
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

class TestPerformanceScenarios:
    """Test cases for performance scenarios."""
    
    @pytest.mark.asyncio
    async def test_large_pdf_processing(self):
        """Test processing of large PDF files."""
        processor = PDFProcessor()
        
        # Mock large PDF content
        large_content = b"Mock large PDF content" * 1000
        
        with patch('PyPDF2.PdfReader') as mock_reader:
            mock_pages = [MagicMock() for _ in range(100)]
            for page in mock_pages:
                page.extract_text.return_value = "Page content " * 50
            
            mock_pdf = MagicMock()
            mock_pdf.is_encrypted = False
            mock_pdf.pages = mock_pages
            mock_pdf.metadata = {}
            
            mock_reader.return_value = mock_pdf
            
            # Test extraction
            result = await processor.extract_text(large_content, "large.pdf")
            
            assert result["processing_status"] == "success"
            assert result["page_count"] == 100
            assert len(result["text"]) > 1000
    
    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, db_session):
        """Test handling of concurrent document uploads."""
        service = DocumentService(db_session)
        
        # Create multiple mock upload files
        upload_tasks = []
        for i in range(5):
            mock_file = MagicMock(spec=UploadFile)
            mock_file.filename = f"test_{i}.pdf"
            mock_file.content_type = "application/pdf"
            mock_file.size = 1000
            mock_file.read = AsyncMock(return_value=b"mock pdf content")
            
            with patch.object(service.pdf_processor, 'validate_pdf') as mock_validate:
                with patch.object(service.storage, 'store_file') as mock_store:
                    mock_validate.return_value = {
                        "is_valid": True,
                        "is_encrypted": False,
                        "page_count": 1,
                        "file_size": 1000
                    }
                    
                    mock_store.return_value = {
                        "storage_path": f"/storage/test_{i}.pdf",
                        "secure_filename": f"secure_test_{i}.pdf",
                        "original_dir": "/storage/original",
                        "processed_dir": "/storage/processed", 
                        "metadata_dir": "/storage/metadata",
                        "file_size": 1000
                    }
                    
                    task = service.upload_document(mock_file)
                    upload_tasks.append(task)
        
        # Execute concurrent uploads
        results = await asyncio.gather(*upload_tasks, return_exceptions=True)
        
        # Verify all uploads succeeded
        for result in results:
            assert not isinstance(result, Exception)
            assert result.processing_status == "uploaded"

if __name__ == "__main__":
    pytest.main([__file__])