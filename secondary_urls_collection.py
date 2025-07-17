import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from driver import get_driver
from bs4 import BeautifulSoup
import re
import csv

def calculate_total_pages(driver):
    """
    Calculate total number of pages by finding pagination buttons.
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        int: Total number of pages
    """
    try:
        # Find all pagination buttons
        pagination_buttons = driver.find_elements("xpath", "//button[contains(@aria-label, 'Go to page')]")
        
        if not pagination_buttons:
            return 1  # Only one page if no pagination buttons
        
        # Count total elements and apply formula: (count / 2) + 1
        total_elements = len(pagination_buttons)
        total_pages = (total_elements // 2) + 1
        
        print(f"Found {total_elements} pagination buttons, calculated {total_pages} pages")
        return total_pages
        
    except Exception as e:
        print(f"Error calculating total pages: {e}")
        return 1

def extract_urls_from_page(html_content, base_url="https://www.foxtons.co.uk"):
    """
    Extract URLs from a single page's HTML content.
    
    Args:
        html_content (str): HTML content of the page
        base_url (str): Base URL to prepend to relative paths
    
    Returns:
        list: List of extracted URLs
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    urls = []
    
    for link in soup.find_all('a', href=True):
        href = str(link.get('href', '')).strip()  # type: ignore
        if href.startswith('/'):
            full_url = base_url + href
            urls.append(full_url)
        elif href.startswith('http'):
            urls.append(href)
    
    url_pattern = r'\(([^)]+)\)'
    matches = re.findall(url_pattern, html_content)
    
    for match in matches:
        clean_path = match.strip()
        if clean_path.startswith('/'):
            full_url = base_url + clean_path
            urls.append(full_url)
        elif clean_path.startswith('http'):
            urls.append(clean_path)
    
    unique_urls = []
    seen = set()
    for url in urls:
        if url not in seen:
            unique_urls.append(url)
            seen.add(url)
    
    return unique_urls

def filter_property_urls(urls):
    """
    Filter URLs to only include property-related URLs with specific conditions.
    
    Args:
        urls (list): List of all extracted URLs
    
    Returns:
        list: Filtered list of property-related URLs
    """
    property_keywords = [
        '/properties-for-sale',
        '/properties-to-rent',
        '/houses-for-sale',
        '/flats-for-sale',
        '/apartments-for-sale',
        '/houses-to-rent',
        '/flats-to-rent',
        '/apartments-to-rent',
        '/new-homes',
        '/auction',
        '/locations',
        '/area-guides'
    ]
    
    filtered_urls = []
    for url in urls:
        if any(keyword in url for keyword in property_keywords):
            if 'for-sale/' in url and 'sold=only' not in url:
                filtered_urls.append(url)
    
    return filtered_urls

def scrape_page(page_number, base_url="https://www.foxtons.co.uk/properties-for-sale/battersea"):
    """
    Scrape a single page and extract URLs.
    
    Args:
        page_number (int): Page number to scrape
        base_url (str): Base URL for the property search
    
    Returns:
        list: List of URLs found on this page
    """
    driver = None
    try:
        driver = get_driver()
        
        if page_number == 1:
            url = base_url
        else:
            url = f"{base_url}?page={page_number}"
        
        print(f"Scraping page {page_number}: {url}")
        driver.get(url)
        
        time.sleep(3)
        
        html_content = driver.page_source
        
        all_urls = extract_urls_from_page(html_content)
        
        property_urls = filter_property_urls(all_urls)
        
        print(f"Page {page_number}: Found {len(property_urls)} property URLs")
        return property_urls
        
    except Exception as e:
        print(f"Error scraping page {page_number}: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def fetch_secondary_urls(url):
    """
    Main function to fetch all secondary URLs from Foxtons property pages.
    
    Args:
        url (str): The URL to scrape
    
    Returns:
        list: All extracted property URLs
    """
    driver = None
    try:
        driver = get_driver()

        driver.get(url)
        time.sleep(3)
        
        total_pages = calculate_total_pages(driver)
        print(f"Total pages to scrape: {total_pages}")
        
        max_threads = 5
        print(f"Using {max_threads} threads per batch")
        
        all_urls = []
        
        # Process pages in batches of 5 threads
        for batch_start in range(1, total_pages + 1, max_threads):
            batch_end = min(batch_start + max_threads - 1, total_pages)
            print(f"Processing batch: pages {batch_start} to {batch_end}")
            
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                future_to_page = {
                    executor.submit(scrape_page, page_num, url): page_num 
                    for page_num in range(batch_start, batch_end + 1)
                }
                
                for future in as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        page_urls = future.result()
                        all_urls.extend(page_urls)
                        print(f"Completed page {page_num}")
                    except Exception as e:
                        print(f"Page {page_num} generated an exception: {e}")
        
        unique_urls = []
        seen = set()
        for url in all_urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        
        print(f"Total unique URLs extracted: {len(unique_urls)}")
        return unique_urls
        
    except Exception as e:
        print(f"Error in fetch_secondary_urls: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def save_urls_to_csv(urls, filename="foxtons_secondary_urls_collection.csv"):
    """
    Save extracted URLs to a CSV file, checking for duplicates.
    
    Args:
        urls (list): List of URLs to save
        filename (str): Output CSV filename
    """
    # Read existing URLs to avoid duplicates
    existing_urls = set()
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader, None)  # Skip header
            for row in reader:
                if row:
                    existing_urls.add(row[0])
    except FileNotFoundError:
        pass  # File doesn't exist yet, start with empty set
    
    # Filter URLs and add new ones
    new_urls = []
    for url in urls:
        if 'bedroom' not in url and 'london' not in url and '?' not in url:
            if url.endswith('1') or url.endswith('2') or url.endswith('3') or url.endswith('4') or url.endswith('5') or url.endswith('6') or url.endswith('7') or url.endswith('8') or url.endswith('9') or url.endswith('0'):
                if url not in existing_urls:
                    new_urls.append(url)
                    existing_urls.add(url)
    
    # Append new URLs to CSV
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header only if file is empty
        if csvfile.tell() == 0:
            writer.writerow(['URL'])
        for url in new_urls:
            writer.writerow([url])
    
    print(f"Added {len(new_urls)} new URLs to {filename} (skipped {len(urls) - len(new_urls)} duplicates)")

if __name__ == "__main__":
    print("Starting Foxtons URL extraction...")
    start_time = time.time()
    
    # Extract URLs from href attributes
    with open('foxtons_initial_url_collection.csv', 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row[0] == 'URL':
                continue
            url = row[0]
            urls = fetch_secondary_urls(url)
            
            if urls:
                save_urls_to_csv(urls)
                
                print("\nSample URLs:")
                for i, url in enumerate(urls[:10], 1):
                    print(f"{i}. {url}")
    
    end_time = time.time()
    print(f"\nTotal execution time: {end_time - start_time:.2f} seconds")


