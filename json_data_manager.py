import json
import os
import shutil
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JSONDataManager:
    """
    Comprehensive JSON data manager for property scraping data.
    Handles loading, saving, validation, backup, and data integrity.
    """
    
    def __init__(self, file_path: str, backup_dir: str = "backups", max_backups: int = 10):
        """
        Initialize the JSON data manager.
        
        Args:
            file_path: Path to the main JSON file
            backup_dir: Directory for backup files
            max_backups: Maximum number of backup files to keep
        """
        self.file_path = file_path
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            logger.info(f"📁 Created backup directory: {self.backup_dir}")
        
        self.data = []
        self.stats = {
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'successful_saves': 0,
            'failed_saves': 0,
            'backups_created': 0
        }
        
        logger.info(f"🔧 JSON Data Manager initialized for: {self.file_path}")
    
    def validate_property_data(self, property_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate individual property data structure.
        
        Args:
            property_data: Property data dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields check
        required_fields = ['url', 'property_id', 'scraped_at', 'scraping_status']
        for field in required_fields:
            if field not in property_data:
                errors.append(f"Missing required field: {field}")
            elif not property_data[field]:
                errors.append(f"Empty required field: {field}")
        
        # Data type validation
        if 'scraped_at' in property_data:
            try:
                datetime.fromisoformat(property_data['scraped_at'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                errors.append("Invalid scraped_at datetime format")
        
        # Scraping status validation
        valid_statuses = ['completed', 'failed', 'fatal_error', 'pending']
        if property_data.get('scraping_status') not in valid_statuses:
            errors.append(f"Invalid scraping_status. Must be one of: {valid_statuses}")
        
        # Rooms validation
        rooms = property_data.get('rooms', {})
        if rooms and not isinstance(rooms, dict):
            errors.append("rooms field must be a dictionary")
        
        # Images validation
        images = property_data.get('images', [])
        if images and not isinstance(images, list):
            errors.append("images field must be a list")
        else:
            for i, img in enumerate(images):
                if not isinstance(img, dict):
                    errors.append(f"Image {i} must be a dictionary")
                elif 'original_url' not in img:
                    errors.append(f"Image {i} missing original_url")
        
        # API posting validation
        api_posting = property_data.get('api_posting', {})
        if api_posting and not isinstance(api_posting, dict):
            errors.append("api_posting field must be a dictionary")
        elif api_posting:
            valid_api_statuses = ['success', 'error', 'disabled', 'pending', 'skipped']
            if api_posting.get('status') not in valid_api_statuses:
                errors.append(f"Invalid api_posting status. Must be one of: {valid_api_statuses}")
        
        return len(errors) == 0, errors
    
    def validate_data_structure(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate the entire data structure.
        
        Args:
            data: List of property data dictionaries
            
        Returns:
            Validation report dictionary
        """
        if not isinstance(data, list):
            return {
                'is_valid': False,
                'total_records': 0,
                'valid_records': 0,
                'invalid_records': 1,
                'errors': ['Data must be a list'],
                'property_errors': {}
            }
        
        total_records = len(data)
        valid_records = 0
        invalid_records = 0
        property_errors = {}
        global_errors = []
        
        # Check for duplicate URLs
        urls_seen = set()
        for i, item in enumerate(data):
            if isinstance(item, dict):
                url = item.get('url')
                if url in urls_seen:
                    global_errors.append(f"Duplicate URL found at index {i}: {url}")
                else:
                    urls_seen.add(url)
                
                # Validate individual property
                is_valid, errors = self.validate_property_data(item)
                if is_valid:
                    valid_records += 1
                else:
                    invalid_records += 1
                    property_errors[i] = errors
            else:
                invalid_records += 1
                property_errors[i] = ["Item is not a dictionary"]
        
        return {
            'is_valid': invalid_records == 0 and len(global_errors) == 0,
            'total_records': total_records,
            'valid_records': valid_records,
            'invalid_records': invalid_records,
            'errors': global_errors,
            'property_errors': property_errors
        }
    
    def clean_data_for_serialization(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean data to ensure JSON serialization compatibility.
        
        Args:
            data: Raw data list
            
        Returns:
            Cleaned data list
        """
        cleaned_data = []
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            cleaned_item = {}
            for key, value in item.items():
                try:
                    # Convert non-serializable objects to strings
                    if isinstance(value, (str, int, float, bool, type(None))):
                        cleaned_item[key] = value
                    elif isinstance(value, list):
                        cleaned_item[key] = [
                            self._clean_value(v) for v in value
                        ]
                    elif isinstance(value, dict):
                        cleaned_item[key] = {
                            k: self._clean_value(v) for k, v in value.items()
                        }
                    else:
                        cleaned_item[key] = str(value)
                except Exception as e:
                    logger.warning(f"⚠️ Error cleaning field {key}: {str(e)}")
                    cleaned_item[key] = str(value)
            
            cleaned_data.append(cleaned_item)
        
        return cleaned_data
    
    def _clean_value(self, value: Any) -> Any:
        """Clean individual value for JSON serialization"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, list):
            return [self._clean_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._clean_value(v) for k, v in value.items()}
        else:
            return str(value)
    
    def create_backup(self) -> Optional[str]:
        """
        Create a backup of the current data file.
        
        Returns:
            Backup file path if successful, None otherwise
        """
        if not os.path.exists(self.file_path):
            logger.info("📄 No existing file to backup")
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{Path(self.file_path).stem}_backup_{timestamp}.json"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            shutil.copy2(self.file_path, backup_path)
            logger.info(f"💾 Backup created: {backup_path}")
            
            self.stats['backups_created'] += 1
            self._cleanup_old_backups()
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Error creating backup: {str(e)}")
            return None
    
    def _cleanup_old_backups(self):
        """Remove old backup files beyond the maximum limit"""
        try:
            backup_files = []
            for file in os.listdir(self.backup_dir):
                if file.startswith(f"{Path(self.file_path).stem}_backup_") and file.endswith(".json"):
                    backup_path = os.path.join(self.backup_dir, file)
                    backup_files.append((backup_path, os.path.getctime(backup_path)))
            
            # Sort by creation time (newest first)
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old files beyond max_backups
            for backup_path, _ in backup_files[self.max_backups:]:
                try:
                    os.remove(backup_path)
                    logger.info(f"🗑️ Removed old backup: {os.path.basename(backup_path)}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not remove old backup {backup_path}: {str(e)}")
                    
        except Exception as e:
            logger.warning(f"⚠️ Error during backup cleanup: {str(e)}")
    
    def load_data(self, validate: bool = True) -> bool:
        """
        Load data from the JSON file.
        
        Args:
            validate: Whether to validate the loaded data
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(self.file_path):
            logger.info(f"📝 No existing file found: {self.file_path}")
            self.data = []
            return True
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"📖 Loading data from {self.file_path} (attempt {attempt + 1})")
                
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                
                if not isinstance(raw_data, list):
                    logger.error("❌ Data file must contain a JSON array")
                    return False
                
                # Validate data if requested
                if validate:
                    validation = self.validate_data_structure(raw_data)
                    
                    if not validation['is_valid']:
                        logger.warning(f"⚠️ Data validation issues found:")
                        logger.warning(f"  Valid records: {validation['valid_records']}")
                        logger.warning(f"  Invalid records: {validation['invalid_records']}")
                        
                        # Log first few errors
                        for error in validation['errors'][:5]:
                            logger.warning(f"    - {error}")
                        
                        if len(validation['errors']) > 5:
                            logger.warning(f"    ... and {len(validation['errors']) - 5} more errors")
                    
                    self.stats.update({
                        'total_records': validation['total_records'],
                        'valid_records': validation['valid_records'],
                        'invalid_records': validation['invalid_records']
                    })
                
                self.data = raw_data
                logger.info(f"✅ Successfully loaded {len(self.data)} records")
                return True
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                    
            except (IOError, OSError) as e:
                logger.error(f"❌ File I/O error (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Unexpected error loading data (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
        
        logger.error(f"❌ Failed to load data after {max_retries} attempts")
        return False
    
    def save_data(self, data: Optional[List[Dict[str, Any]]] = None, create_backup: bool = True) -> bool:
        """
        Save data to the JSON file with backup and validation.
        
        Args:
            data: Data to save (uses self.data if None)
            create_backup: Whether to create a backup before saving
            
        Returns:
            True if successful, False otherwise
        """
        if data is None:
            data = self.data
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"💾 Saving {len(data)} records (attempt {attempt + 1})")
                
                # Create backup before saving
                if create_backup:
                    self.create_backup()
                
                # Clean data for serialization
                cleaned_data = self.clean_data_for_serialization(data)
                
                # Validate that data can be serialized
                json_str = json.dumps(cleaned_data, indent=2, ensure_ascii=False, default=str)
                
                # Write to temporary file first
                temp_file = f"{self.file_path}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                
                # Verify the temporary file
                with open(temp_file, 'r', encoding='utf-8') as f:
                    verification_data = json.load(f)
                
                if len(verification_data) != len(cleaned_data):
                    raise ValueError("Data verification failed after save")
                
                # If verification passes, replace the main file
                if os.path.exists(self.file_path):
                    shutil.move(self.file_path, f"{self.file_path}.old")
                
                shutil.move(temp_file, self.file_path)
                
                # Remove old file if save was successful
                if os.path.exists(f"{self.file_path}.old"):
                    os.remove(f"{self.file_path}.old")
                
                self.data = cleaned_data
                self.stats['successful_saves'] += 1
                logger.info(f"✅ Successfully saved {len(cleaned_data)} records to {self.file_path}")
                return True
                
            except (json.JSONEncodeError, TypeError) as e:
                logger.error(f"❌ JSON serialization error (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    self.stats['failed_saves'] += 1
                    return False
                    
            except (IOError, OSError) as e:
                logger.error(f"❌ File I/O error (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    self.stats['failed_saves'] += 1
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Unexpected error saving data (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    self.stats['failed_saves'] += 1
                    return False
        
        return False
    
    def add_record(self, record: Dict[str, Any], validate: bool = True) -> bool:
        """
        Add a new record to the data.
        
        Args:
            record: Property record to add
            validate: Whether to validate the record
            
        Returns:
            True if successful, False otherwise
        """
        if validate:
            is_valid, errors = self.validate_property_data(record)
            if not is_valid:
                logger.error(f"❌ Invalid record: {errors}")
                return False
        
        self.data.append(record)
        logger.debug(f"✅ Record added. Total records: {len(self.data)}")
        return True
    
    def get_scraped_urls(self) -> set:
        """Get set of already scraped URLs to avoid duplicates"""
        scraped_urls = set()
        for item in self.data:
            if isinstance(item, dict) and 'url' in item and item['url']:
                scraped_urls.add(item['url'])
        return scraped_urls
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get data manager statistics"""
        stats = self.stats.copy()
        stats['current_records'] = len(self.data)
        return stats
    
    def repair_data(self) -> int:
        """
        Attempt to repair common data issues.
        
        Returns:
            Number of records repaired
        """
        repaired_count = 0
        
        for record in self.data:
            if not isinstance(record, dict):
                continue
            
            repaired = False
            
            # Fix missing required fields
            if 'scraped_at' not in record or not record['scraped_at']:
                record['scraped_at'] = datetime.now().isoformat()
                repaired = True
            
            if 'scraping_status' not in record:
                record['scraping_status'] = 'completed' if record.get('address') else 'failed'
                repaired = True
            
            # Fix data types
            if 'rooms' in record and not isinstance(record['rooms'], dict):
                record['rooms'] = {}
                repaired = True
            
            if 'images' in record and not isinstance(record['images'], list):
                record['images'] = []
                repaired = True
            
            if 'key_features' in record and not isinstance(record['key_features'], list):
                record['key_features'] = []
                repaired = True
            
            if 'further_details' in record and not isinstance(record['further_details'], dict):
                record['further_details'] = {}
                repaired = True
            
            if 'nearest_stations' in record and not isinstance(record['nearest_stations'], list):
                record['nearest_stations'] = []
                repaired = True
            
            if repaired:
                repaired_count += 1
        
        if repaired_count > 0:
            logger.info(f"🔧 Repaired {repaired_count} records")
        
        return repaired_count


def create_data_manager(file_path: str, **kwargs) -> JSONDataManager:
    """
    Create and initialize a JSON data manager.
    
    Args:
        file_path: Path to the JSON data file
        **kwargs: Additional arguments for JSONDataManager
        
    Returns:
        Configured JSONDataManager instance
    """
    manager = JSONDataManager(file_path, **kwargs)
    
    # Load existing data
    if manager.load_data():
        stats = manager.get_statistics()
        logger.info(f"📊 Data Manager Statistics:")
        logger.info(f"  Current records: {stats['current_records']}")
        logger.info(f"  Valid records: {stats['valid_records']}")
        logger.info(f"  Invalid records: {stats['invalid_records']}")
    
    return manager


# Example usage
if __name__ == "__main__":
    # Test the data manager
    manager = create_data_manager("property_details.json")
    
    # Print statistics
    stats = manager.get_statistics()
    print("📊 Data Manager Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Test validation
    if manager.data:
        validation = manager.validate_data_structure(manager.data)
        print(f"\n✅ Data Validation:")
        print(f"  Valid: {validation['is_valid']}")
        print(f"  Total: {validation['total_records']}")
        print(f"  Valid: {validation['valid_records']}")
        print(f"  Invalid: {validation['invalid_records']}")
        
        if validation['errors']:
            print(f"  Errors: {len(validation['errors'])}")
            for error in validation['errors'][:3]:
                print(f"    - {error}") 