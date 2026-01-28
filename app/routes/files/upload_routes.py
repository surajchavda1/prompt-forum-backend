"""
File upload routes for standalone file uploads (WYSIWYG editor support)
"""
from fastapi import APIRouter, UploadFile, File, Depends
from app.utils.file_upload import FileUploadService
from app.utils.response import success_response, error_response
from app.routes.auth.dependencies import get_current_user

router = APIRouter(prefix="/files", tags=["File Upload"])


@router.post("/upload")
async def upload_file_for_editor(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a single file for inline embedding in WYSIWYG editor.
    
    This endpoint is designed for rich text editors (Toast UI, TinyMCE, etc.)
    that need to upload images/videos and get back a URL for embedding.
    
    Returns markdown-formatted string for easy insertion into editor.
    
    **Use cases:**
    - User clicks "Insert Image" in editor
    - Editor uploads file to this endpoint
    - Editor inserts returned markdown/URL into content
    
    **Example Response:**
    ```json
    {
      "success": true,
      "data": {
        "url": "http://localhost:8000/uploads/user_123/abc123.png",
        "markdown": "![image.png](http://localhost:8000/uploads/user_123/abc123.png)",
        "filename": "abc123.png",
        "original_filename": "my-image.png",
        "file_type": "image/png"
      }
    }
    ```
    """
    if not current_user:
        return error_response(
            message="Authentication required",
            status_code=401
        )
    
    file_service = FileUploadService()
    user_id = str(current_user["_id"])
    
    try:
        # Save file using existing service
        file_info = await file_service.save_file(file, user_id)
        
        # Generate appropriate markdown based on file type
        if file_info["file_type"].startswith("image"):
            # Image: ![alt](url)
            markdown = f"![{file_info['original_filename']}]({file_info['file_url']})"
        elif file_info["file_type"].startswith("video"):
            # Video: Can use same syntax, will be rendered as video player
            markdown = f"![{file_info['original_filename']}]({file_info['file_url']})"
        else:
            # Other files: [text](url) for download link
            markdown = f"[📎 {file_info['original_filename']}]({file_info['file_url']})"
        
        return success_response(
            message="File uploaded successfully",
            data={
                "url": file_info["file_url"],
                "markdown": markdown,
                "filename": file_info["filename"],
                "original_filename": file_info["original_filename"],
                "file_type": file_info["file_type"],
                "file_size": file_info["file_size"],
                "inline": True  # Indicates this file is meant for inline embedding
            }
        )
        
    except ValueError as e:
        return error_response(
            message=str(e),
            status_code=400
        )
    except Exception as e:
        return error_response(
            message=f"File upload failed: {str(e)}",
            status_code=500
        )
