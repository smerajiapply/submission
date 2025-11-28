"""Storage utilities for saving files and data"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
from src.config.base_config import settings
from src.utils.logger import log


class StorageManager:
    """Manages file storage for offers, logs, and metadata"""
    
    def __init__(self):
        self.offers_dir = settings.offers_dir
        self.logs_dir = settings.logs_dir
    
    def save_offer(
        self, 
        school_name: str, 
        application_id: str, 
        file_content: bytes,
        extension: str = "pdf"
    ) -> Path:
        """Save an offer letter file"""
        
        # Create school-specific directory
        school_dir = self.offers_dir / school_name.lower().replace(" ", "_")
        school_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{application_id}_{timestamp}.{extension}"
        file_path = school_dir / filename
        
        # Save file
        file_path.write_bytes(file_content)
        log.info(f"Saved offer to: {file_path}")
        
        return file_path
    
    def save_screenshot(
        self,
        screenshot_data: bytes,
        prefix: str = "screenshot"
    ) -> Path:
        """Save a screenshot"""
        
        screenshots_dir = self.logs_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.png"
        file_path = screenshots_dir / filename
        
        file_path.write_bytes(screenshot_data)
        log.debug(f"Saved screenshot to: {file_path}")
        
        return file_path
    
    def save_metadata(
        self,
        school_name: str,
        application_id: str,
        metadata: Dict[str, Any]
    ) -> Path:
        """Save metadata for an application check"""
        
        school_dir = self.offers_dir / school_name.lower().replace(" ", "_")
        school_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{application_id}_{timestamp}_metadata.json"
        file_path = school_dir / filename
        
        # Add timestamp to metadata
        metadata["saved_at"] = timestamp
        
        file_path.write_text(json.dumps(metadata, indent=2))
        log.info(f"Saved metadata to: {file_path}")
        
        return file_path
    
    def load_school_config(self, school_name: str) -> Path:
        """Get path to school config file"""
        config_file = settings.config_dir / f"{school_name}.yaml"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        return config_file


# Global storage manager instance
storage = StorageManager()


