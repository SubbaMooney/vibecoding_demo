import PyPDF2
import pdfplumber
import pymupdf4llm
import io
import re
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFProcessor:
    """
    PDF text extraction and preprocessing with multiple fallback methods.
    """
    
    def __init__(self):
        self.extraction_methods = [
            self._extract_with_pypdf2,
            self._extract_with_pdfplumber,
            self._extract_with_pymupdf
        ]
    
    async def extract_text(self, file_content: bytes, filename: str) -> Dict[str, any]:
        """
        Extract text from PDF using multiple methods with fallback.
        
        Returns:
            Dict containing extracted text, metadata, and processing info
        """
        result = {
            "text": "",
            "page_count": 0,
            "text_length": 0,
            "extraction_method": None,
            "processing_status": "error",
            "error_message": None,
            "metadata": {}
        }
        
        # Try each extraction method until one succeeds
        for i, method in enumerate(self.extraction_methods):
            try:
                logger.info(f"Attempting extraction method {i+1} for {filename}")
                extracted_data = await method(file_content)
                
                if extracted_data["text"] and len(extracted_data["text"].strip()) > 0:
                    result.update(extracted_data)
                    result["extraction_method"] = method.__name__
                    result["processing_status"] = "success"
                    
                    # Apply text preprocessing
                    result["text"] = await self._preprocess_text(result["text"])
                    result["text_length"] = len(result["text"])
                    
                    logger.info(f"Successfully extracted {result['text_length']} characters using {method.__name__}")
                    break
                    
            except Exception as e:
                logger.warning(f"Extraction method {method.__name__} failed: {str(e)}")
                continue
        
        if result["processing_status"] == "error":
            result["error_message"] = "All extraction methods failed"
            logger.error(f"Failed to extract text from {filename}")
        
        return result
    
    async def _extract_with_pypdf2(self, file_content: bytes) -> Dict[str, any]:
        """Primary extraction method using PyPDF2."""
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        if pdf_reader.is_encrypted:
            raise ValueError("PDF is password protected")
        
        text_pages = []
        page_count = len(pdf_reader.pages)
        
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                text_pages.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract page {page_num + 1}: {str(e)}")
                text_pages.append("")
        
        full_text = "\n\n".join(text_pages)
        
        # Extract metadata
        metadata = {}
        if pdf_reader.metadata:
            metadata = {
                "title": pdf_reader.metadata.get("/Title", ""),
                "author": pdf_reader.metadata.get("/Author", ""),
                "subject": pdf_reader.metadata.get("/Subject", ""),
                "creator": pdf_reader.metadata.get("/Creator", ""),
                "producer": pdf_reader.metadata.get("/Producer", ""),
                "creation_date": str(pdf_reader.metadata.get("/CreationDate", "")),
                "modification_date": str(pdf_reader.metadata.get("/ModDate", ""))
            }
        
        return {
            "text": full_text,
            "page_count": page_count,
            "metadata": metadata
        }
    
    async def _extract_with_pdfplumber(self, file_content: bytes) -> Dict[str, any]:
        """Fallback extraction method using pdfplumber."""
        with io.BytesIO(file_content) as pdf_file:
            with pdfplumber.open(pdf_file) as pdf:
                text_pages = []
                page_count = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_pages.append(page_text)
                        else:
                            text_pages.append("")
                    except Exception as e:
                        logger.warning(f"pdfplumber failed on page {page_num + 1}: {str(e)}")
                        text_pages.append("")
                
                full_text = "\n\n".join(text_pages)
                
                # Try to extract basic metadata
                metadata = {
                    "total_pages": page_count,
                    "extraction_method": "pdfplumber"
                }
                
                return {
                    "text": full_text,
                    "page_count": page_count,
                    "metadata": metadata
                }
    
    async def _extract_with_pymupdf(self, file_content: bytes) -> Dict[str, any]:
        """Advanced fallback extraction method using pymupdf."""
        try:
            # Use pymupdf4llm for better text extraction
            text = pymupdf4llm.to_markdown(file_content)
            
            # Extract basic page count (approximate)
            page_count = text.count("---") + 1  # Markdown page separators
            
            metadata = {
                "extraction_method": "pymupdf4llm",
                "format": "markdown"
            }
            
            return {
                "text": text,
                "page_count": page_count,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"pymupdf extraction failed: {str(e)}")
            raise
    
    async def _preprocess_text(self, text: str) -> str:
        """
        Clean and normalize extracted text for better search performance.
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\"\']+', ' ', text)
        
        # Fix common OCR errors and encoding issues
        replacements = {
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '–': '-',
            '—': '-',
            '…': '...',
            '\u00A0': ' ',  # Non-breaking space
            '\u200B': '',   # Zero-width space
            '\u200C': '',   # Zero-width non-joiner
            '\u200D': '',   # Zero-width joiner
            '\uFEFF': ''    # Byte order mark
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Normalize whitespace again after replacements
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    async def validate_pdf(self, file_content: bytes) -> Dict[str, any]:
        """
        Validate PDF file integrity and extract basic information.
        """
        validation_result = {
            "is_valid": False,
            "is_encrypted": False,
            "page_count": 0,
            "file_size": len(file_content),
            "error_message": None,
            "warnings": []
        }
        
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Check if encrypted
            if pdf_reader.is_encrypted:
                validation_result["is_encrypted"] = True
                validation_result["error_message"] = "PDF is password protected"
                return validation_result
            
            # Get page count
            page_count = len(pdf_reader.pages)
            validation_result["page_count"] = page_count
            
            if page_count == 0:
                validation_result["error_message"] = "PDF contains no pages"
                return validation_result
            
            # Try to read first page to verify content
            try:
                first_page = pdf_reader.pages[0]
                first_page.extract_text()
                validation_result["is_valid"] = True
                
            except Exception as e:
                validation_result["warnings"].append(f"Content extraction warning: {str(e)}")
                validation_result["is_valid"] = True  # Still valid PDF, just extraction issues
            
        except Exception as e:
            validation_result["error_message"] = f"PDF validation failed: {str(e)}"
        
        return validation_result
    
    async def get_document_structure(self, file_content: bytes) -> Dict[str, any]:
        """
        Extract document structure information (headings, sections, etc.).
        """
        structure = {
            "headings": [],
            "sections": [],
            "tables_count": 0,
            "images_count": 0,
            "links_count": 0
        }
        
        try:
            # Use pdfplumber for better structure analysis
            with io.BytesIO(file_content) as pdf_file:
                with pdfplumber.open(pdf_file) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        # Count tables
                        tables = page.find_tables()
                        structure["tables_count"] += len(tables)
                        
                        # Extract text and look for headings (simple heuristic)
                        text = page.extract_text()
                        if text:
                            lines = text.split('\n')
                            for line in lines:
                                line = line.strip()
                                # Simple heading detection (caps, short lines)
                                if (line.isupper() and len(line) < 100 and 
                                    len(line) > 3 and not line.isdigit()):
                                    structure["headings"].append({
                                        "text": line,
                                        "page": page_num + 1
                                    })
                        
        except Exception as e:
            logger.warning(f"Failed to extract document structure: {str(e)}")
        
        return structure