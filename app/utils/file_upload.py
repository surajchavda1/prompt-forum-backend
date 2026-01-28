import os
import uuid
import re
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get backend URL from environment
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Allowed file types and their MIME types (with browser variants)
ALLOWED_FILE_TYPES = {
    # Images (with all common browser variants)
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/jpg': ['.jpg', '.jpeg'],
    'image/pjpeg': ['.jpg', '.jpeg'],  # IE
    'image/png': ['.png'],
    'image/x-png': ['.png'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp'],
    'image/avif': ['.avif'],  # Modern image format
    'image/svg+xml': ['.svg'],
    'image/svg': ['.svg'],
    'image/bmp': ['.bmp'],  # Bitmap
    'image/x-icon': ['.ico'],  # Icon
    'image/vnd.microsoft.icon': ['.ico'],
    
    # Documents
    'application/pdf': ['.pdf'],
    'application/x-pdf': ['.pdf'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'application/msword': ['.doc'],
    'text/plain': ['.txt'],
    'text/markdown': ['.md'],
    'text/x-markdown': ['.md'],
    'application/rtf': ['.rtf'],
    'text/rtf': ['.rtf'],
    'text/csv': ['.csv'],
    'application/csv': ['.csv'],
    
    # Videos
    'video/mp4': ['.mp4'],
    'video/mpeg': ['.mp4', '.mpeg'],
    'video/webm': ['.webm'],
    'video/quicktime': ['.mov'],
    'video/x-msvideo': ['.avi'],
    
    # Audio
    'audio/mpeg': ['.mp3'],
    'audio/mp3': ['.mp3'],
    'audio/wav': ['.wav'],
    'audio/x-wav': ['.wav'],
    'audio/ogg': ['.ogg'],
    'audio/webm': ['.webm'],
    
    # Code & Configuration Files (with all variants)
    'application/json': ['.json'],
    'text/json': ['.json'],
    'application/xml': ['.xml'],
    'text/xml': ['.xml'],
    'text/html': ['.html', '.htm'],
    'application/xhtml+xml': ['.html', '.htm'],
    'text/css': ['.css'],
    'text/javascript': ['.js', '.jsx'],
    'application/javascript': ['.js', '.jsx'],
    'application/x-javascript': ['.js', '.jsx'],
    'text/x-python': ['.py'],
    'application/x-python': ['.py'],
    'application/x-python-code': ['.py'],
    'text/x-script.python': ['.py'],
    'text/x-java-source': ['.java'],
    'text/x-java': ['.java'],
    'text/x-c': ['.c', '.h'],
    'text/x-csrc': ['.c'],
    'text/x-chdr': ['.h'],
    'text/x-c++': ['.cpp', '.hpp', '.cc', '.cxx'],
    'text/x-c++src': ['.cpp', '.cc', '.cxx'],
    'text/x-c++hdr': ['.hpp'],
    'text/x-csharp': ['.cs'],
    'text/x-php': ['.php'],
    'application/x-php': ['.php'],
    'text/x-ruby': ['.rb'],
    'application/x-ruby': ['.rb'],
    'text/x-go': ['.go'],
    'text/x-rust': ['.rs'],
    'text/rust': ['.rs'],
    'text/x-swift': ['.swift'],
    'text/x-kotlin': ['.kt'],
    'text/x-typescript': ['.ts', '.tsx'],
    'application/typescript': ['.ts', '.tsx'],
    'text/typescript': ['.ts', '.tsx'],
    'text/x-yaml': ['.yml', '.yaml'],
    'application/x-yaml': ['.yml', '.yaml'],
    'text/yaml': ['.yml', '.yaml'],
    'text/x-toml': ['.toml'],
    'application/toml': ['.toml'],
    'text/x-ini': ['.ini'],
    'text/x-sh': ['.sh', '.bash'],
    'application/x-sh': ['.sh', '.bash'],
    'application/x-shellscript': ['.sh', '.bash'],
    'text/x-sql': ['.sql'],
    'application/sql': ['.sql'],
    
    # Archives (with all variants)
    'application/zip': ['.zip'],
    'application/x-zip': ['.zip'],
    'application/x-zip-compressed': ['.zip'],
    'multipart/x-zip': ['.zip'],
    'application/x-rar': ['.rar'],
    'application/x-rar-compressed': ['.rar'],
    'application/vnd.rar': ['.rar'],
    'application/x-7z-compressed': ['.7z'],
    'application/x-tar': ['.tar'],
    'application/x-gtar': ['.tar'],
    'application/gzip': ['.gz'],
    'application/x-gzip': ['.gz'],
    
    # Catch-all for unknown MIME types (will rely on extension check)
    'application/octet-stream': ['.bin'],
}

# File size limits (in bytes)
MAX_FILE_SIZE = {
    'image': 5 * 1024 * 1024,      # 5 MB
    'document': 10 * 1024 * 1024,  # 10 MB
    'video': 50 * 1024 * 1024,     # 50 MB
    'audio': 10 * 1024 * 1024,     # 10 MB
    'code': 2 * 1024 * 1024,       # 2 MB (for code files)
    'archive': 20 * 1024 * 1024,   # 20 MB (for zip files)
}

# Maximum files per upload
MAX_FILES_PER_UPLOAD = 5

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class FileUploadService:
    """Service for handling secure file uploads"""
    
    @staticmethod
    def get_file_category(content_type: str) -> str:
        """Determine file category from content type"""
        if content_type.startswith('image/'):
            return 'image'
        elif content_type.startswith('video/'):
            return 'video'
        elif content_type.startswith('audio/'):
            return 'audio'
        elif content_type in ['application/zip', 'application/x-zip-compressed', 
                              'application/x-rar-compressed', 'application/x-7z-compressed',
                              'application/x-tar', 'application/gzip']:
            return 'archive'
        elif content_type in ['application/json', 'application/xml', 'text/html', 
                              'text/css', 'text/javascript', 'application/javascript',
                              'text/x-python', 'application/x-python-code', 'text/x-java',
                              'text/x-c', 'text/x-c++', 'text/x-csharp', 'text/x-php',
                              'text/x-ruby', 'text/x-go', 'text/x-rust', 'text/x-swift',
                              'text/x-kotlin', 'text/x-typescript', 'text/x-yaml',
                              'text/x-toml', 'text/x-ini', 'text/x-sh', 'application/x-sh',
                              'text/x-sql', 'text/markdown']:
            return 'code'
        else:
            return 'document'
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent directory traversal attacks"""
        # Remove any path components
        filename = os.path.basename(filename)
        
        # Remove any non-alphanumeric characters except dots, underscores, and hyphens
        filename = re.sub(r'[^\w\s.-]', '', filename)
        
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        
        # Limit filename length
        name, ext = os.path.splitext(filename)
        if len(name) > 50:
            name = name[:50]
        
        return f"{name}{ext}"
    
    @staticmethod
    def validate_file_type(filename: str, content_type: str) -> bool:
        """
        Validate file type against allowed types.
        Very lenient approach: primarily checks file extension.
        """
        file_ext = os.path.splitext(filename.lower())[1]
        
        # If no extension, reject
        if not file_ext:
            return False
        
        # Check if extension exists in ANY of the allowed types
        # This is the primary check - extension-based validation
        for mime_type, extensions in ALLOWED_FILE_TYPES.items():
            if file_ext in extensions:
                return True
        
        # Additional safety: Check common extensions that might be missing
        # Allow common safe file extensions
        safe_extensions = [
            '.txt', '.md', '.json', '.xml', '.csv',
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.svg', '.bmp', '.ico',
            '.pdf', '.doc', '.docx',
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.c', '.cpp', '.cs',
            '.html', '.css', '.yml', '.yaml', '.toml', '.ini',
            '.zip', '.tar', '.gz', '.rar', '.7z',
            '.mp4', '.webm', '.mov',
            '.mp3', '.wav', '.ogg'
        ]
        
        if file_ext in safe_extensions:
            return True
        
        return False
    
    @staticmethod
    def validate_file_size(file_size: int, category: str) -> bool:
        """Validate file size against limits"""
        max_size = MAX_FILE_SIZE.get(category, 5 * 1024 * 1024)
        return file_size <= max_size
    
    @staticmethod
    async def save_file(file: UploadFile, user_id: str) -> dict:
        """
        Save uploaded file securely
        
        Returns:
            Dictionary with file information
        """
        # Log file details for debugging
        file_ext = os.path.splitext(file.filename.lower())[1]
        print(f"[FILE UPLOAD DEBUG] Filename: {file.filename}, Extension: {file_ext}, Content-Type: {file.content_type}")
        
        # Validate content type
        if not FileUploadService.validate_file_type(file.filename, file.content_type):
            raise ValueError(
                f"File type not allowed. File: {file.filename}, Extension: {file_ext}, Content-Type: {file.content_type}. "
                f"Please upload files with supported extensions: .jpg, .png, .gif, .webp, .avif, .svg, .bmp, .pdf, .docx, .doc, .txt, .md, "
                f".json, .xml, .html, .css, .js, .py, .java, .cpp, .yml, .zip, .mp4, .mp3, etc."
            )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size
        category = FileUploadService.get_file_category(file.content_type)
        if not FileUploadService.validate_file_size(file_size, category):
            max_size_mb = MAX_FILE_SIZE[category] / (1024 * 1024)
            raise ValueError(
                f"File too large. Maximum size for {category}: {max_size_mb}MB"
            )
        
        # Generate unique filename
        original_filename = FileUploadService.sanitize_filename(file.filename)
        file_ext = os.path.splitext(original_filename)[1]
        unique_filename = f"{uuid.uuid4().hex}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{file_ext}"
        
        # Create user-specific directory
        user_dir = UPLOAD_DIR / user_id
        user_dir.mkdir(exist_ok=True)
        
        # Save file
        file_path = user_dir / unique_filename
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Generate full file URL (complete URL with domain)
        file_url = f"{BACKEND_URL}/uploads/{user_id}/{unique_filename}"
        
        # Return file information as dictionary
        return {
            "filename": unique_filename,
            "original_filename": original_filename,
            "file_type": file.content_type,
            "file_size": file_size,
            "file_url": file_url,
            "uploaded_at": datetime.utcnow()
        }
    
    @staticmethod
    async def delete_file(file_url: str) -> bool:
        """Delete a file from storage"""
        try:
            # Extract path from URL
            file_path = UPLOAD_DIR / file_url.replace('/uploads/', '')
            
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    @staticmethod
    def get_file_info(filename: str, content_type: str, file_size: int, file_url: str) -> dict:
        """
        Get file information dictionary
        
        DEPRECATED: Use save_file() which now returns complete file info dictionary
        """
        return {
            "filename": filename,
            "original_filename": filename,
            "file_type": content_type,
            "file_size": file_size,
            "file_url": file_url,
            "uploaded_at": datetime.utcnow()
        }
