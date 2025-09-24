import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import shutil
import logging

logger = logging.getLogger(__name__)

class DocumentStorage:
    """Handles file storage organization by document type and upload date."""
    
    def __init__(self, base_storage_path: str = "storage/documents"):
        self.base_path = Path(base_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_storage_path(self, file_type: str, upload_date: datetime) -> Path:
        """
        Generate hierarchical storage path: storage/documents/{type}/{year}/{month}/{day}/
        """
        year = upload_date.strftime("%Y")
        month = upload_date.strftime("%m")
        day = upload_date.strftime("%d")
        
        storage_path = self.base_path / file_type / year / month / day
        storage_path.mkdir(parents=True, exist_ok=True)
        
        return storage_path
    
    def _create_secure_filename(self, original_filename: str) -> str:
        """
        Create secure filename with UUID prefix to prevent conflicts and security issues.
        """
        # Extract file extension
        file_ext = Path(original_filename).suffix.lower()
        
        # Create secure filename with UUID
        secure_name = f"{uuid.uuid4()}{file_ext}"
        
        return secure_name
    
    async def store_file(self, file_content: bytes, original_filename: str, 
                        file_type: str = "pdf", upload_date: Optional[datetime] = None) -> dict:
        """
        Store file in organized directory structure.
        
        Returns:
            dict: Storage information including paths and metadata
        """
        if upload_date is None:
            upload_date = datetime.utcnow()
        
        try:
            # Get storage directory
            storage_dir = self._get_storage_path(file_type, upload_date)
            
            # Create secure filename
            secure_filename = self._create_secure_filename(original_filename)
            
            # Create subdirectories
            original_dir = storage_dir / "original"
            processed_dir = storage_dir / "processed"
            metadata_dir = storage_dir / "metadata"
            
            for dir_path in [original_dir, processed_dir, metadata_dir]:
                dir_path.mkdir(exist_ok=True)
            
            # Store original file
            original_path = original_dir / secure_filename
            with open(original_path, 'wb') as f:
                f.write(file_content)
            
            # Verify file was written correctly
            if not original_path.exists() or original_path.stat().st_size != len(file_content):
                raise ValueError("File storage verification failed")
            
            logger.info(f"File stored successfully: {original_path}")
            
            return {
                "storage_path": str(original_path),
                "secure_filename": secure_filename,
                "original_dir": str(original_dir),
                "processed_dir": str(processed_dir),
                "metadata_dir": str(metadata_dir),
                "file_size": len(file_content)
            }
            
        except Exception as e:
            logger.error(f"Failed to store file {original_filename}: {str(e)}")
            raise
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete file and associated processing artifacts.
        """
        try:
            file_path = Path(storage_path)
            
            if not file_path.exists():
                logger.warning(f"File not found for deletion: {storage_path}")
                return False
            
            # Delete original file
            file_path.unlink()
            
            # Try to delete related processed files
            try:
                # Get the directory structure
                original_dir = file_path.parent
                base_dir = original_dir.parent
                processed_dir = base_dir / "processed"
                metadata_dir = base_dir / "metadata"
                
                # Delete processed files with same base name
                secure_filename = file_path.name
                base_name = secure_filename.rsplit('.', 1)[0]
                
                for dir_path in [processed_dir, metadata_dir]:
                    if dir_path.exists():
                        for related_file in dir_path.glob(f"{base_name}.*"):
                            related_file.unlink()
                            logger.info(f"Deleted related file: {related_file}")
                
            except Exception as e:
                logger.warning(f"Failed to clean up related files: {str(e)}")
            
            logger.info(f"File deleted successfully: {storage_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {storage_path}: {str(e)}")
            raise
    
    async def file_exists(self, storage_path: str) -> bool:
        """Check if file exists in storage."""
        return Path(storage_path).exists()
    
    async def get_file_info(self, storage_path: str) -> Optional[dict]:
        """Get file information from storage."""
        try:
            file_path = Path(storage_path)
            
            if not file_path.exists():
                return None
            
            stat = file_path.stat()
            
            return {
                "path": str(file_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "created": datetime.fromtimestamp(stat.st_ctime)
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {storage_path}: {str(e)}")
            return None
    
    async def cleanup_empty_directories(self) -> int:
        """
        Clean up empty directories in storage hierarchy.
        Returns number of directories removed.
        """
        removed_count = 0
        
        try:
            for root, dirs, files in os.walk(self.base_path, topdown=False):
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    try:
                        if not any(dir_path.iterdir()):
                            dir_path.rmdir()
                            removed_count += 1
                            logger.debug(f"Removed empty directory: {dir_path}")
                    except OSError:
                        pass  # Directory not empty or permission issue
                        
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        
        return removed_count