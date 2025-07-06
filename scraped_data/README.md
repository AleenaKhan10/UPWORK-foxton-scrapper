# Property Details Scraper

This Selenium-based scraper extracts detailed information from Foxtons property listings using URLs from a CSV file.

## Features

The scraper extracts the following information from each property:

- **Address**: Property address
- **Description**: Property description
- **Property Type**: Type of property (flat, house, etc.)
- **Rooms**: Parsed room information (beds, baths, etc.) as a dictionary
- **Price**: Property price
- **Key Features**: List of property features
- **Further Details**: Additional property details as key-value pairs
- **Nearest Stations**: Station information including names, links, and details
- **Local Life**: Local area information
- **Images**: Downloads all property images and stores them locally

## Requirements

- Python 3.7+
- Chrome browser installed
- Internet connection

## Installation

1. Install required packages:
```bash
pip install -r requirements.txt
```

2. Ensure you have Chrome browser installed on your system.

## Usage

### Basic Usage

1. Place your CSV file with property URLs in the same directory as the scraper
2. Run the scraper:

```bash
python property_details_scraper.py
```

### Testing with Limited Properties

For testing purposes, you can limit the number of properties to scrape by modifying the main function:

```python
# Test with only 5 properties
scraper.scrape_all_properties(limit=5)
```

### Configuration

You can modify the following settings in the `main()` function:

- `CSV_FILE`: Path to your CSV file (default: "property_listings.csv")
- `IMAGES_DIR`: Directory to save images (default: "property_images")
- `OUTPUT_FILE`: Output JSON file name (default: "property_details.json")

## Input Format

The CSV file should have a header row with at least a "URL" column containing the property URLs to scrape.

Example CSV format:
```csv
URL,Source Page,Timestamp,Page Number
https://www.foxtons.co.uk/properties-for-sale/br1/chpk3889834,https://www.foxtons.co.uk/flats-for-sale/london?page=55,2025-06-13 21:17:48,55
```

## Output

### JSON File
The scraper creates a JSON file (`property_details.json` by default) containing all scraped data with the following structure:

```json
{
  "url": "https://www.foxtons.co.uk/properties-for-sale/...",
  "scraped_at": "2025-01-XX T XX:XX:XX",
  "property_id": "chpk3889834",
  "address": "Property Address",
  "description": "Property description...",
  "property_type": "Flat",
  "rooms": {
    "beds": 2,
    "baths": 1
  },
  "price": "£XXX,XXX",
  "key_features": ["Feature 1", "Feature 2"],
  "further_details": {
    "Detail 1": "Value 1",
    "Detail 2": "Value 2"
  },
  "nearest_stations": [
    {
      "station_info": "Station info",
      "map_link": "https://...",
      "station_name": "Station Name"
    }
  ],
  "local_life": "Local area description...",
  "images": [
    {
      "original_url": "https://...",
      "local_path": "/path/to/downloaded/image.jpg"
    }
  ]
}
```

### Images Directory
Images are downloaded and organized in the following structure:
```
property_images/
├── chpk3889834/
│   ├── image_001.jpg
│   ├── image_002.jpg
│   └── ...
├── chpk3891178/
│   ├── image_001.jpg
│   └── ...
```

## Features

- **Automatic Progress Saving**: Progress is saved every 10 properties
- **Error Handling**: Continues scraping even if individual properties fail
- **Respectful Scraping**: Includes delays between requests
- **Headless Mode**: Runs in headless mode by default (can be disabled)
- **Automatic ChromeDriver Management**: Uses webdriver-manager for automatic driver setup

## Customization

### Browser Options
You can modify the Chrome options in the `__init__` method:

```python
# To see the browser window (remove headless mode)
# self.chrome_options.add_argument("--headless")  # Comment this line

# To change window size
self.chrome_options.add_argument("--window-size=1920,1080")
```

### Delays and Timeouts
You can adjust the timing in the scraper:

```python
# Page load wait time
time.sleep(3)  # Modify this value

# Request delay between properties
time.sleep(2)  # Modify this value

# Image download delay
time.sleep(0.5)  # Modify this value
```

## Troubleshooting

1. **ChromeDriver Issues**: The scraper uses webdriver-manager to automatically handle ChromeDriver installation. If you encounter issues, try updating Chrome browser.

2. **Network Errors**: The scraper includes retry logic for network requests. If you encounter persistent issues, check your internet connection.

3. **Memory Issues**: For large datasets, consider processing in smaller batches by using the `limit` parameter.

4. **XPath Issues**: If elements are not found, the website structure may have changed. Check the XPath selectors in the scraper.

## Legal Considerations

- Ensure you comply with the website's terms of service
- Be respectful with scraping frequency
- The scraper includes delays to avoid overwhelming the server
- Consider the website's robots.txt file

## Support

If you encounter issues:
1. Check that Chrome browser is installed and up to date
2. Verify your CSV file format
3. Ensure you have internet connectivity
4. Check the console output for error messages 