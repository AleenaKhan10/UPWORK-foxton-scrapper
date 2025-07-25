import json
from profile import run
import pymssql
import re
import sys
from typing import Dict, List, Tuple, Optional
from db_config import DB_CONFIG, TABLE_SCHEMAS

class DatabaseUpdater:
    def __init__(self):
        self.connection = None
        self.property_data = []
        self.property_types = {}
        self.postal_codes = {}
        
    def connect_to_database(self):
        """Establish connection to Azure SQL Database using pymssql"""
        try:
            print(f"Connecting to {DB_CONFIG['server']}...")
            print(f"Database: {DB_CONFIG['database']}")
            print(f"Username: {DB_CONFIG['username']}")
            
            # Connect using pymssql
            self.connection = pymssql.connect(
                server=DB_CONFIG['server'],
                database=DB_CONFIG['database'],
                user=DB_CONFIG['username'],
                password=DB_CONFIG['password'],
                port=DB_CONFIG['port']
            )
            print("✓ Successfully connected to Azure SQL Database")
            return True
        except Exception as e:
            print(f"✗ Error connecting to database: {e}")
            return False
    
    def load_property_data(self):
        """Load property details from JSON file"""
        try:
            with open('property_details.json', 'r', encoding='utf-8') as file:
                self.property_data = json.load(file)
            print(f"Loaded {len(self.property_data)} properties from JSON file")
        except Exception as e:
            print(f"Error loading property data: {e}")
            return False
        return True
    
    def load_property_types(self):
        """Load property types from database"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT PropertyTypeId, Name FROM [dbo].[PropertyType]")
            rows = cursor.fetchall()
            
            for row in rows:
                property_type_id = row[0]  # PropertyTypeId
                property_type_name = row[1]  # Name
                self.property_types[property_type_name.lower()] = property_type_id
            
            print(f"✓ Loaded {len(self.property_types)} property types")
            cursor.close()
        except Exception as e:
            print(f"✗ Error loading property types: {e}")
            return False
        return True
    
    def load_postal_codes(self):
        """Load postal codes from database"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT PostalCodeId, Code FROM [dbo].[PostalCodes]")
            rows = cursor.fetchall()
            
            for row in rows:
                postal_code_id = row[0]  # PostalCodeId
                postal_code = row[1]  # Code
                self.postal_codes[postal_code] = postal_code_id
            
            print(f"✓ Loaded {len(self.postal_codes)} postal codes")
            cursor.close()
        except Exception as e:
            print(f"✗ Error loading postal codes: {e}")
            return False
        return True
    
    def get_listings_to_update(self) -> List[Tuple]:
        """Get all listings that need to be updated"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT ListingId, Description, PropertyTypeId, PostalCodeId, PostalCodeText FROM [dbo].[Listings] ORDER BY CreatedDate DESC")
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"✗ Error fetching listings: {e}")
            return []

    def get_property_type_id(self) -> List[Tuple]:
        """Get all listings that need to be updated"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM [dbo].[PropertyType]")
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"✗ Error fetching listings: {e}")
            return []

    def get_postal_code_id(self) -> List[Tuple]:
        """Get all listings that need to be updated"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM [dbo].[PostalCodes]")
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"✗ Error fetching listings: {e}")
            return []

    def get_state_id(self) -> List[Tuple]:
        """Get all listings that need to be updated"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM [dbo].[States]")
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"✗ Error fetching listings: {e}")
            return []
    
    def update_listing(self, listing_id: int, property_type_id: Optional[int], postal_code_id: Optional[int], tenure: Optional[str], lease_expires: Optional[str], ground_rent: Optional[str], service_charge: Optional[str], stamp_duty: Optional[str], council_tax: Optional[str], local_authority: Optional[str], total_sq_ft: Optional[str], references: Optional[str], state_id: Optional[int]):
        """Update a single listing with new property type and postal code IDs"""
        try:
            cursor = self.connection.cursor()
            
            query = f"UPDATE [dbo].[Listings] SET PropertyTypeId = %s, PostalCodeId = %s, Tenure = %s, Lease_Expires = %s, Ground_Rent = %s, Service_Charge = %s, Stamp_Duty = %s, Council_Tax = %s, StateId = %s WHERE ListingId = %s"
            cursor.execute(query, (property_type_id, postal_code_id, tenure, lease_expires, ground_rent, service_charge, stamp_duty, council_tax, state_id, listing_id))
            self.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"Error updating listing {listing_id}: {e}")
            return False
    
    def process_listings(self):
        """Main processing function"""
        print("Starting listing update process...")
        
        listings_table = self.get_listings_to_update()
        property_type_table = self.get_property_type_id()
        postal_code_table = self.get_postal_code_id()
        state_table = self.get_state_id()
        listing_id_data = None
        property_type_id_data = None
        postal_code_id_data = None
        state_id_data = None

        with open('property_details.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        for runs in data:
            scrapped_description = runs['description']
            scrapped_property_type = runs['property_type']
            scrapped_further_details = runs.get('further_details', {})

            for listing_table_row in listings_table:
                if listing_table_row[1] == scrapped_description:
                    listing_id_data = listing_table_row[0]
                    postal_code_data_string = str(listing_table_row[4]).replace('0','').replace('1','').replace('2','').replace('3','').replace('4','').replace('5','').replace('6','').replace('7','').replace('8','').replace('9','')

                
                    for property_type_table_row in property_type_table:
                        if property_type_table_row[1] == scrapped_property_type:
                            property_type_id_data = property_type_table_row[0]
                            break

                    for postal_code_table_row in postal_code_table:
                        if postal_code_table_row[2] == postal_code_data_string:
                            postal_code_id_data = postal_code_table_row[0]
                            break

                    tenure = scrapped_further_details.get('Tenure', None)
                    lease_expires = scrapped_further_details.get('Lease Expires', None)
                    ground_rent = scrapped_further_details.get('Ground Rent', None)
                    service_charge = scrapped_further_details.get('Service Charge', None)
                    stamp_duty = scrapped_further_details.get('Stamp Duty', None)
                    council_tax = scrapped_further_details.get('Council Tax', None)
                    local_authority = scrapped_further_details.get('Local Authority', None)
                    total_sq_ft = scrapped_further_details.get('Total Sq Ft', None)
                    references = scrapped_further_details.get('References', None)

                    if local_authority:
                        if '(' in local_authority:
                            local_authority = local_authority.split(' ')[0]
                        if 'The City of' in local_authority:
                            local_authority = local_authority.split(' ')[3]

                    for state_table_row in state_table:
                        if state_table_row[1] == local_authority:
                            state_id_data = state_table_row[0]
                            break

                    if listing_id_data is not None and property_type_id_data is not None and postal_code_id_data is not None:
                        import time
                        time.sleep(2)
                        print(f"Updating listing {listing_id_data} with property type {property_type_id_data}, postal code {postal_code_id_data}, state {state_id_data}, tenure {tenure}, lease expires {lease_expires}, ground rent {ground_rent}, service charge {service_charge}, stamp duty {stamp_duty}, council tax {council_tax}, local authority {local_authority}, total sq ft {total_sq_ft}, references {references}")
                        self.update_listing(listing_id_data, property_type_id_data, postal_code_id_data, tenure, lease_expires, ground_rent, service_charge, stamp_duty, council_tax, local_authority, total_sq_ft, references, state_id_data)
                        listing_id_data = None
                        property_type_id_data = None
                        postal_code_id_data = None
                        state_id_data = None
                        postal_code_data_string = None
                        break
                    else:
                        print(f"No matching listing found for address: {scrapped_description}")


    def close_connection(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("Database connection closed")

def main():
    """Main function to run the update process"""
    updater = DatabaseUpdater()
    
    try:
        # Connect to database
        if not updater.connect_to_database():
            return
        
        # Load data
        if not updater.load_property_data():
            return
        
        if not updater.load_property_types():
            return
        
        if not updater.load_postal_codes():
            return
        
        # Process listings
        updater.process_listings()
        
    except Exception as e:
        print(f"Error in main process: {e}")
    finally:
        updater.close_connection()

def test_connection():
    """Test database connection"""
    print("Testing connection to Azure SQL Database...")
    print(f"Server: {DB_CONFIG['server']}")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"Username: {DB_CONFIG['username']}")
    print(f"Password: {'*' * len(DB_CONFIG['password'])} (hidden)")
    
    updater = DatabaseUpdater()
    try:
        if updater.connect_to_database():
            print("✓ Connection test successful!")
            
            # Test basic queries
            cursor = updater.connection.cursor()
            
            # Test Listings table
            print("\n--- Testing Listings Table ---")
            cursor.execute("SELECT TOP 3 ListingId, StreetAddress, PropertyTypeId, PostalCodeId FROM [dbo].[Listings] ORDER BY CreatedDate DESC")
            listings = cursor.fetchall()
            print(f"✓ Found {len(listings)} sample listings")
            if listings:
                print("Sample listings:")
                for i, row in enumerate(listings):
                    print(f"  Row {i+1}: ListingId={row[0]}, StreetAddress='{row[1]}', PropertyTypeId={row[2]}, PostalCodeId={row[3]}")
            
            # Test PropertyType table
            print("\n--- Testing PropertyType Table ---")
            cursor.execute("SELECT TOP 5 PropertyTypeId, Name FROM [dbo].[PropertyType]")
            property_types = cursor.fetchall()
            print(f"✓ Found {len(property_types)} property types")
            if property_types:
                print("Sample property types:")
                for i, row in enumerate(property_types):
                    print(f"  Row {i+1}: PropertyTypeId={row[0]}, Name='{row[1]}'")
            
            # Test PostalCodes table
            print("\n--- Testing PostalCodes Table ---")
            cursor.execute("SELECT TOP 5 PostalCodeId, Code FROM [dbo].[PostalCodes]")
            postal_codes = cursor.fetchall()
            print(f"✓ Found {len(postal_codes)} postal codes")
            if postal_codes:
                print("Sample postal codes:")
                for i, row in enumerate(postal_codes):
                    print(f"  Row {i+1}: PostalCodeId={row[0]}, Code='{row[1]}'")
            
            cursor.close()
            updater.close_connection()
            return True
        else:
            print("✗ Connection test failed!")
            print("\nPossible issues:")
            print("1. Password might be incorrect")
            print("2. Username might be wrong")
            print("3. Database name might be incorrect")
            print("4. IP address not allowed in Azure firewall")
            print("5. Server name might be wrong")
            return False
    except Exception as e:
        print(f"✗ Error in connection test: {e}")
        return False

if __name__ == "__main__":
    # Check command line argument
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_connection()
    else:
        main() 