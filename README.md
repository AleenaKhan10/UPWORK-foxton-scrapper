# Foxtons Property Scraper - Azure Functions

This project is a comprehensive property scraping solution for Foxtons.co.uk, implemented as Azure Functions with headless browser automation using PyVirtualDisplay.

## Project Structure

```
├── functions/
│   ├── initial_urls_collection/     # Step 1: Collect initial URLs from locations page
│   ├── secondary_urls_collection/   # Step 2: Extract property URLs from each location
│   ├── listing_details/            # Step 3: Extract detailed property information
│   └── main_orchestrator/          # Orchestrates all three functions
├── shared/
│   └── driver.py                   # Shared browser management with PyVirtualDisplay
├── requirements.txt                # Python dependencies
├── host.json                       # Azure Functions configuration
├── local.settings.json             # Local development settings
└── README.md                       # This file
```

## Features

- **Headless Browser Automation**: Uses PyVirtualDisplay for proper rendering in Linux environments
- **Multi-threaded Processing**: Processes multiple pages concurrently (max 5 threads)
- **Batch Processing**: Handles large page counts efficiently
- **Duplicate Prevention**: Prevents duplicate URLs and listings
- **Comprehensive Data Extraction**: Extracts detailed property information
- **Azure Functions Ready**: Deployable to Azure Functions

## Setup

### Prerequisites

- Python 3.8+
- Azure Functions Core Tools
- Chrome/Chromium browser

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd foxtons-scraper-azure
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Azure Functions Core Tools**
   ```bash
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```

4. **For Linux environments, install additional dependencies**
   ```bash
   sudo apt-get update
   sudo apt-get install -y xvfb x11-xserver-utils
   ```

## Local Development

### Running Locally

1. **Start the Azure Functions runtime**
   ```bash
   func start
   ```

2. **Test individual functions**
   ```bash
   # Initial URLs collection
   curl -X POST http://localhost:7071/api/initial_urls_collection
   
   # Secondary URLs collection
   curl -X POST http://localhost:7071/api/secondary_urls_collection
   
   # Listing details extraction
   curl -X POST http://localhost:7071/api/listing_details
   ```

3. **Run the complete pipeline**
   ```bash
   curl -X POST http://localhost:7071/api/main_orchestrator
   ```

## Azure Deployment

### Deploy to Azure Functions

1. **Create Azure Function App**
   ```bash
   az functionapp create --name foxtons-scraper --storage-account <storage-account> --consumption-plan-location <location> --runtime python --runtime-version 3.9 --functions-version 4
   ```

2. **Deploy the functions**
   ```bash
   func azure functionapp publish foxtons-scraper
   ```

3. **Configure environment variables**
   ```bash
   az functionapp config appsettings set --name foxtons-scraper --resource-group <resource-group> --settings FUNCTION_APP_URL=https://foxtons-scraper.azurewebsites.net
   ```

### Azure Function URLs

After deployment, your functions will be available at:
- `https://foxtons-scraper.azurewebsites.net/api/initial_urls_collection`
- `https://foxtons-scraper.azurewebsites.net/api/secondary_urls_collection`
- `https://foxtons-scraper.azurewebsites.net/api/listing_details`
- `https://foxtons-scraper.azurewebsites.net/api/main_orchestrator`

## Function Details

### 1. Initial URLs Collection (`/api/initial_urls_collection`)

- **Purpose**: Extracts initial property URLs from Foxtons locations page
- **Input**: None
- **Output**: CSV file with initial URLs
- **Features**: 
  - Filters for property-related URLs
  - Excludes non-relevant pages
  - Removes duplicates

### 2. Secondary URLs Collection (`/api/secondary_urls_collection`)

- **Purpose**: Processes each initial URL to extract individual property listings
- **Input**: Reads from `foxtons_initial_url_collection.csv`
- **Output**: CSV file with property URLs
- **Features**:
  - Multi-threaded processing (max 5 threads)
  - Batch processing for large page counts
  - Pagination handling
  - Duplicate prevention
  - Filters for property URLs ending with numbers

### 3. Listing Details (`/api/listing_details`)

- **Purpose**: Extracts detailed information from each property listing
- **Input**: Reads from `foxtons_secondary_urls_collection.csv`
- **Output**: CSV file with detailed property information
- **Features**:
  - Uses PyVirtualDisplay for proper rendering
  - Extracts comprehensive property details
  - Handles various data formats
  - Duplicate prevention

### 4. Main Orchestrator (`/api/main_orchestrator`)

- **Purpose**: Runs all three functions in sequence
- **Input**: None
- **Output**: Summary of all operations
- **Features**:
  - Sequential execution
  - Error handling
  - Progress tracking
  - Execution time monitoring

## Data Output

### CSV Files Generated

1. **`foxtons_initial_url_collection.csv`**
   - Column: URL
   - Contains: Initial property category URLs

2. **`foxtons_secondary_urls_collection.csv`**
   - Column: URL
   - Contains: Individual property listing URLs

3. **`foxtons_listing_details.csv`**
   - Columns: url, title, price, address, bedrooms, bathrooms, property_type, description, features, agent, agent_phone, agent_email, images, floor_plan, epc_rating, council_tax, tenure, postcode, area, extracted_at

## Browser Configuration

The project uses a custom browser manager that:

- **Supports PyVirtualDisplay**: Essential for Linux/Azure environments
- **Headless Mode**: Optimized for server environments
- **Performance Optimized**: Disabled unnecessary features
- **Memory Efficient**: Configured for Azure Functions constraints
- **Anti-Detection**: Includes measures to avoid bot detection

## Error Handling

- **Graceful Degradation**: Individual failures don't stop the entire process
- **Retry Logic**: Built-in retry mechanisms for transient failures
- **Logging**: Comprehensive logging for debugging
- **Timeout Handling**: Proper timeout management for long-running operations

## Performance Considerations

- **Concurrent Processing**: Up to 5 threads for secondary URL collection
- **Batch Processing**: Handles large datasets efficiently
- **Memory Management**: Optimized for Azure Functions memory limits
- **Resource Cleanup**: Proper cleanup of browser instances

## Monitoring and Logging

All functions include comprehensive logging:
- Function entry/exit
- Processing progress
- Error details
- Performance metrics
- Data extraction statistics

## Troubleshooting

### Common Issues

1. **Chrome Driver Issues**
   - Ensure Chrome/Chromium is installed
   - Check webdriver-manager installation

2. **PyVirtualDisplay Issues**
   - Install xvfb on Linux: `sudo apt-get install xvfb`
   - Ensure X11 forwarding is available

3. **Memory Issues**
   - Reduce concurrent threads
   - Increase Azure Function memory allocation

4. **Timeout Issues**
   - Increase function timeout settings
   - Reduce batch sizes

### Debug Mode

Enable debug logging by setting the log level:
```bash
az functionapp config appsettings set --name foxtons-scraper --resource-group <resource-group> --settings FUNCTIONS_WORKER_RUNTIME_LOG_LEVEL=DEBUG
```

## License

This project is for educational purposes. Please ensure compliance with Foxtons' terms of service and applicable laws. 