#!/usr/bin/env python3
"""
Remove Duplicates from Property Details JSON
This script removes duplicate entries from property_details.json file,
keeping only the latest entry for each URL.
"""

import json
import os
from datetime import datetime
from collections import OrderedDict

class DuplicateRemover:
    def __init__(self, input_file="property_details.json", output_file="property_listings.json"):
        self.input_file = input_file
        self.output_file = output_file
        self.original_data = []
        self.cleaned_data = []
        self.duplicates_removed = 0
        self.total_entries = 0
        
    def load_json_data(self):
        """Load data from the input JSON file"""
        if not os.path.exists(self.input_file):
            print(f"❌ Error: Input file '{self.input_file}' not found!")
            return False
            
        try:
            with open(self.input_file, 'r', encoding='utf-8') as file:
                self.original_data = json.load(file)
                self.total_entries = len(self.original_data)
                print(f"✅ Loaded {self.total_entries} entries from {self.input_file}")
                return True
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in {self.input_file}: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Error loading file: {str(e)}")
            return False
    
    def find_duplicates(self):
        """Find and count duplicate URLs"""
        url_count = {}
        duplicate_urls = []
        
        for entry in self.original_data:
            url = entry.get('url', '')
            if url:
                if url in url_count:
                    url_count[url] += 1
                else:
                    url_count[url] = 1
        
        # Find URLs that appear more than once
        for url, count in url_count.items():
            if count > 1:
                duplicate_urls.append((url, count))
        
        if duplicate_urls:
            print(f"\n📊 Found {len(duplicate_urls)} URLs with duplicates:")
            for url, count in sorted(duplicate_urls, key=lambda x: x[1], reverse=True)[:10]:
                print(f"   - {url}: {count} entries")
            
            if len(duplicate_urls) > 10:
                print(f"   ... and {len(duplicate_urls) - 10} more duplicate URLs")
        else:
            print(f"\n✅ No duplicates found!")
        
        return duplicate_urls
    
    def remove_duplicates(self):
        """Remove duplicates, keeping only the last occurrence of each URL"""
        # Use OrderedDict to maintain order while removing duplicates
        # Process in reverse order so the last occurrence is kept
        url_to_entry = OrderedDict()
        
        print(f"\n🔄 Processing entries to remove duplicates...")
        
        # Process entries in order, so later entries overwrite earlier ones
        for i, entry in enumerate(self.original_data):
            url = entry.get('url', '')
            
            if url:
                # Check if this URL already exists
                if url in url_to_entry:
                    self.duplicates_removed += 1
                    scraped_at_old = url_to_entry[url].get('scraped_at', 'unknown')
                    scraped_at_new = entry.get('scraped_at', 'unknown')
                    print(f"   🔄 Replacing duplicate for URL: {url}")
                    print(f"      Old entry scraped at: {scraped_at_old}")
                    print(f"      New entry scraped at: {scraped_at_new}")
                
                # Store or update the entry (keeps the last occurrence)
                url_to_entry[url] = entry
            else:
                # Handle entries without URLs (shouldn't happen, but just in case)
                print(f"   ⚠️ Entry at index {i} has no URL, including it anyway")
                # Use index as a unique key for entries without URLs
                url_to_entry[f"_no_url_{i}"] = entry
        
        # Convert back to list
        self.cleaned_data = list(url_to_entry.values())
        
        print(f"\n📊 Duplicate Removal Summary:")
        print(f"   Original entries: {self.total_entries}")
        print(f"   Duplicates removed: {self.duplicates_removed}")
        print(f"   Final unique entries: {len(self.cleaned_data)}")
        print(f"   Reduction: {self.total_entries - len(self.cleaned_data)} entries ({((self.total_entries - len(self.cleaned_data)) / self.total_entries * 100):.1f}%)")
    
    def save_cleaned_data(self):
        """Save the cleaned data to output JSON file"""
        try:
            # Create backup of output file if it exists
            if os.path.exists(self.output_file):
                backup_file = f"{self.output_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(self.output_file, backup_file)
                print(f"\n📁 Created backup: {backup_file}")
            
            # Save cleaned data
            with open(self.output_file, 'w', encoding='utf-8') as file:
                json.dump(self.cleaned_data, file, indent=2, ensure_ascii=False)
            
            print(f"✅ Successfully saved {len(self.cleaned_data)} unique entries to {self.output_file}")
            
            # Calculate file sizes
            original_size = os.path.getsize(self.input_file)
            new_size = os.path.getsize(self.output_file)
            size_reduction = original_size - new_size
            
            print(f"\n📊 File Size Comparison:")
            print(f"   Original file: {original_size:,} bytes ({original_size / 1024 / 1024:.2f} MB)")
            print(f"   New file: {new_size:,} bytes ({new_size / 1024 / 1024:.2f} MB)")
            print(f"   Size reduction: {size_reduction:,} bytes ({size_reduction / original_size * 100:.1f}%)")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving cleaned data: {str(e)}")
            return False
    
    def analyze_data_quality(self):
        """Analyze the quality of data after cleaning"""
        print(f"\n📊 Data Quality Analysis:")
        
        # Count entries with various fields
        with_description = sum(1 for entry in self.cleaned_data if entry.get('description', '').strip())
        with_price = sum(1 for entry in self.cleaned_data if entry.get('price', '').strip())
        with_address = sum(1 for entry in self.cleaned_data if entry.get('address', '').strip())
        completed_status = sum(1 for entry in self.cleaned_data if entry.get('scraping_status') == 'completed')
        error_status = sum(1 for entry in self.cleaned_data if entry.get('scraping_status') == 'fatal_error')
        
        print(f"   Total unique properties: {len(self.cleaned_data)}")
        print(f"   With description: {with_description} ({with_description / len(self.cleaned_data) * 100:.1f}%)")
        print(f"   With price: {with_price} ({with_price / len(self.cleaned_data) * 100:.1f}%)")
        print(f"   With address: {with_address} ({with_address / len(self.cleaned_data) * 100:.1f}%)")
        print(f"   Successfully scraped: {completed_status} ({completed_status / len(self.cleaned_data) * 100:.1f}%)")
        print(f"   Failed to scrape: {error_status} ({error_status / len(self.cleaned_data) * 100:.1f}%)")
        
        # Show sample of cleaned data
        print(f"\n📋 Sample of cleaned data (first 3 entries):")
        for i, entry in enumerate(self.cleaned_data[:3]):
            print(f"\n   Entry {i + 1}:")
            print(f"   URL: {entry.get('url', 'N/A')}")
            print(f"   Address: {entry.get('address', 'N/A')[:80]}{'...' if len(entry.get('address', '')) > 80 else ''}")
            print(f"   Price: {entry.get('price', 'N/A')}")
            print(f"   Status: {entry.get('scraping_status', 'N/A')}")
            print(f"   Scraped at: {entry.get('scraped_at', 'N/A')}")
    
    def run(self):
        """Main method to run the duplicate removal process"""
        print("🚀 Starting duplicate removal process...")
        print("=" * 60)
        
        # Load data
        if not self.load_json_data():
            return False
        
        # Find duplicates
        self.find_duplicates()
        
        # Remove duplicates
        self.remove_duplicates()
        
        # Save cleaned data
        if not self.save_cleaned_data():
            return False
        
        # Analyze data quality
        self.analyze_data_quality()
        
        print("\n✅ Duplicate removal process completed successfully!")
        print("=" * 60)
        
        return True

def main():
    """Main function to run the duplicate remover"""
    # Configuration
    INPUT_FILE = "property_details.json"
    OUTPUT_FILE = "property_listings.json"
    
    # Ensure we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print(f"📂 Working directory: {os.getcwd()}")
    print(f"📄 Input file: {INPUT_FILE}")
    print(f"📄 Output file: {OUTPUT_FILE}")
    print()
    
    # Initialize and run duplicate remover
    remover = DuplicateRemover(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE
    )
    
    try:
        success = remover.run()
        if success:
            print(f"\n✅ You can now use '{OUTPUT_FILE}' which contains unique property listings!")
        else:
            print(f"\n❌ Process failed. Please check the errors above.")
            
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()