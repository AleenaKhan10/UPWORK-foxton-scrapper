import requests
import re
from bs4 import BeautifulSoup

def fetch_first_listing_by_location():
    url = "https://www.foxtons.co.uk/locations"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def extract_urls_from_html(html_content, base_url="https://www.foxtons.co.uk"):
    """
    Extract URLs from HTML content using regex and append them to base URL.
    
    Args:
        html_content (str): The HTML content containing URLs in parentheses
        base_url (str): The base URL to prepend to extracted paths
    
    Returns:
        list: List of complete URLs
    """
    url_pattern = r'\(([^)]+)\)'
    
    matches = re.findall(url_pattern, html_content)
    
    urls = []
    for match in matches:
        clean_path = match.strip()
        if clean_path.startswith('/'):
            full_url = base_url + clean_path
            urls.append(full_url)
        elif clean_path.startswith('http'):
            urls.append(clean_path)
    
    return urls

def extract_urls_from_html_links(html_content, base_url="https://www.foxtons.co.uk"):
    """
    Extract URLs from HTML href attributes and other link sources.
    
    Args:
        html_content (str): The HTML content
        base_url (str): The base URL to prepend to relative paths
    
    Returns:
        list: List of complete URLs
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
    
    for tag in soup.find_all(['img', 'script', 'link'], src=True):
        src = str(tag.get('src', '')).strip()  # type: ignore
        if src.startswith('/'):
            full_url = base_url + src
            urls.append(full_url)
        elif src.startswith('http'):
            urls.append(src)
    
    for tag in soup.find_all(attrs={'data-url': True}):
        data_url = str(tag.get('data-url', '')).strip()  # type: ignore
        if data_url.startswith('/'):
            full_url = base_url + data_url
            urls.append(full_url)
        elif data_url.startswith('http'):
            urls.append(data_url)
    
    return urls

def process_foxtons_html(html_content):
    """
    Process Foxtons HTML content and extract all URLs.
    
    Args:
        html_content (str): The HTML content from Foxtons website
    
    Returns:
        list: List of all extracted URLs
    """
    all_urls = []
    
    paren_urls = extract_urls_from_html(html_content)
    all_urls.extend(paren_urls)
    
    link_urls = extract_urls_from_html_links(html_content)
    all_urls.extend(link_urls)
    
    unique_urls = []
    seen = set()
    for url in all_urls:
        if url not in seen:
            unique_urls.append(url)
            seen.add(url)
    
    return unique_urls

def save_urls_to_csv(urls, filename="foxtons_urls.csv"):
    """
    Save extracted URLs to a CSV file.
    
    Args:
        urls (list): List of URLs to save
        filename (str): Output CSV filename
    """
    import csv
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL'])  # Header
        for url in urls:
            writer.writerow([url])
    
    print(f"Saved {len(urls)} URLs to {filename}")

def filter_foxtons_property_urls(urls):
    """
    Filter URLs to only include Foxtons property-related URLs.
    
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

def main():
    """Main function to demonstrate the URL extraction process"""
    html_data = fetch_first_listing_by_location()
    
    if html_data:
        all_urls = process_foxtons_html(html_data)
        
        property_urls = filter_foxtons_property_urls(all_urls)
        
        print(f"Extracted {len(all_urls)} total URLs")
        print(f"Found {len(property_urls)} property-related URLs:")
        
        for i, url in enumerate(property_urls[:10], 1):
            print(f"{i}. {url}")
        
        if len(property_urls) > 10:
            print(f"... and {len(property_urls) - 10} more URLs")
        
        save_urls_to_csv(property_urls, "foxtons_initial_url_collection.csv")
        
        return property_urls
    else:
        print("Failed to fetch data from Foxtons")
        return []

if __name__ == "__main__":
    main() 