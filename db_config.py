# Database Configuration
DB_CONFIG = {
    'server': 'laddrsqlsrvr.database.windows.net',  # Azure SQL Database server
    'database': 'LaddrDevelopment',  # Correct database name
    'username': 'raeeswaqar',  # Updated to match SSMS login
    'password': 'prod#@3P012db',  # Correct password
    'port': 1433,  # Default SQL Server port
}

# Table column mappings using column names (much better than indices)
TABLE_SCHEMAS = {
    'listings': {
        'id_column': 'ListingId',  # ListingId column name
        'address_column': 'StreetAddress',  # StreetAddress column name
        'property_type_id_column': 'PropertyTypeId',  # PropertyTypeId column name
        'postal_code_id_column': 'PostalCodeId'  # PostalCodeId column name
    },
    'property_types': {
        'id_column': 'PropertyTypeId',  # PropertyTypeId column name
        'name_column': 'Name'  # Name column name
    },
    'postal_codes': {
        'id_column': 'PostalCodeId',  # PostalCodeId column name
        'code_column': 'Code'  # Code column name
    }
} 