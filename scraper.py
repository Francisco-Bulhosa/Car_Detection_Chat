import requests
from bs4 import BeautifulSoup
import time
import logging
import sqlite3 
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor
from fake_useragent import UserAgent



#region # Create Database

def initialize_database():
    try: 
        conn = sqlite3.connect("C:\\Users\\franc\\Documents\\GitHub\\Car_Detection_Chat\\car_listings.db")
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (strftime('%Y-%m-%d %H:00', 'now')),
            make TEXT,
            model TEXT,
            year TEXT,
            mileage INT,
            listing_price TEXT,
            url TEXT
        );
        """)
        
        conn.commit()
        print("Database initialized successfully.")

    except Exception as e:
        print(f"Failed to initialize database: {e}")

    finally:
        conn.close()

#endregion


#region # Insert into database

def insert_into_database(data):
    conn = sqlite3.connect("car_listings.db")
    cursor = conn.cursor()
    # Query the database to check for duplicate listings
    cursor.execute("""
    SELECT * FROM car_listings WHERE 
        url = ? AND 
        listing_price = ?
    """, (
        data.get('url'), 
        data.get('listing_price')
    ))
    
    # Fetch the result to see if a duplicate exists
    duplicate = cursor.fetchone()
    
    # If no duplicate is found, insert the data
    if not duplicate:
        cursor.execute("""
        INSERT INTO car_listings (
            make, model, year, mileage, listing_price, url)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get('make'), data.get('model'), data.get('year'), data.get('mileage'), data.get('listing_price'), 
            data.get('url')
        ))
        conn.commit()
    
    conn.close()

#endregion




#region # Detail Scraper

def scrape_details(details_url):
        try:
            response = requests.get(url = details_url, timeout=10)
        except requests.exceptions.RequestException as e:
            logging.error('Failed to fetch URL: {}'.format(e))
            return  # Skip to the next iteration of the loop
        
        if response.status_code == 200:
            details_soup = BeautifulSoup(response.text, 'html.parser')

            # Initialize a dictionary to store scraped data
            scraped_data = {}


            heading = details_soup.find('h1', {'class': 'listing-title'})
            if heading:
                text_content = heading.get_text(strip=True)
                words = text_content.split()
                if len(words) > 2:
                    scraped_data["year"] = words[0]
                    scraped_data["make"] = words[1]
                    scraped_data["model"] = ' '.join(words[2:])
                else:
                    logging.error(f'Failed to extract make, model, and year from heading: {text_content}')
                    return None  # Return None if extraction fails
                
            # Find the span tag containing the listing price
            price_tag = details_soup.find('span', {'class': 'primary-price'})
            if price_tag:
                price_text = price_tag.get_text(strip=True)
                # Remove commas, if any, to convert to integer later
                scraped_data['listing_price'] = price_text.replace(',', '').replace('$', '')
            else:
                logging.warning(f'Failed to extract listing price from {details_url}')

            # Find the div tag containing the mileage
            mileage_div = details_soup.find('div', {'class': 'listing-mileage'})
            if mileage_div:
                mileage_text = mileage_div.get_text(strip=True).replace(',', '')  # Remove commas
                # Extract only the integer value using regex
                mileage_match = re.search(r'(\d+)', mileage_text)
                if mileage_match:
                    scraped_data['mileage'] = int(mileage_match.group(1))
                else:
                    logging.warning(f'Failed to extract mileage integer from {mileage_text}')
            else:
                logging.warning(f'Failed to extract mileage from {details_url}')


            scraped_data['url'] = details_url

                
            return scraped_data

        else:
            logging.info(f"Failed to retrieve details page with status code {response.status_code}")
            return None
        

#endregion

def get_next_page_url(soup):
    next_page_btn = soup.find('a', {'aria-label': 'Next page', 'class': 'sds-button'})
    if next_page_btn and 'href' in next_page_btn.attrs:
        return f"https://www.cars.com{next_page_btn['href']}"
    return None

def get_listings(soup):
    listings = []
    vehicle_cards = soup.find_all('div', {'class': 'vehicle-card'})
    for vehicle_card in vehicle_cards:
        a_tag = vehicle_card.find('a', {'class': 'image-gallery-link vehicle-card-visited-tracking-link'})
        if a_tag and 'href' in a_tag.attrs:
            listing_url = f"https://www.cars.com{a_tag['href']}"
            listings.append(listing_url)
    return listings


def process_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    listings = get_listings(soup)
    for listing_url in listings:
        details_data = scrape_details(listing_url)
        if details_data:
            insert_into_database(details_data)
            print(details_data)  # Print scraped details
        else:
            logging.info(f"Failed to scrape details for {listing_url}")
        time.sleep(2)  # Respectful delay between requests

    # Get the URL of the next page
    next_page_url = get_next_page_url(soup)
    return next_page_url





#region  # Main
if __name__ == "__main__":
    initialize_database()
    logging.basicConfig(level=logging.INFO)


    # Starting URL
    start_url = "https://www.cars.com/shopping/results/?dealer_id=&keyword=&list_price_max=&list_price_min=90000&makes[]=&maximum_distance=30&mileage_max=&monthly_payment=&page_size=20&sort=list_price_desc&stock_type=used&year_max=&year_min=&zip=#vehicle-card-d42a7308-dd43-4ce2-a138-a42d1fa8ec3f"


    # Counter for the number of listings scraped
    count = 0
    max_count = 500  # Maximum number of listings to scrape

        # Counter for the number of failed attempts to fetch next page
    failed_next_page_count = 0
    max_failed_next_page_count = 5  # Maximum number of failed attempts

    current_url = start_url

    while current_url and count < max_count:  # Modified this line to include count < max_count
    # while start_url:
        try:
            response = requests.get(current_url)
            response.raise_for_status()  # Will raise HTTPError for bad responses (4xx and 5xx)
        except requests.RequestException as e:
            logging.warning(f"Failed to retrieve page {current_url}: {e}")
            failed_next_page_count += 1
            if failed_next_page_count >= max_failed_next_page_count:
                logging.error("Max failed attempts reached. Exiting.")
                break
            continue

        if response.status_code == 200:

            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get the listing URLs from the current page
            listing_urls = get_listings(soup)

            for listing_url in listing_urls:
                if count >= max_count:
                    break  # Break the loop if maximum count reached

                details_data = scrape_details(listing_url)
        
                if details_data:  # Check if details were successfully scraped
                    insert_into_database(details_data)  # Insert data into the database
                
                    # Increase the count for each listing processed
                    count += 1
                    print(details_data)  # Print the scraped details
                else:
                    logging.info(f"Failed to scrape details for {listing_url}")
                
            if count >= max_count:
                logging.info(f"Reached the maximum count of {max_count}. Exiting.")
                break
            
            # Get the URL of the next page
            next_button = soup.find('a', {'id': 'next_paginate'})
            if next_button and 'href' in next_button.attrs:
                current_url = f"https://www.cars.com{next_button['href']}"
            else:
                logging.info("No more pages to scrape. Exiting.")
                break

    # Sleep for a short time to respect the website's rate-limiting
    time.sleep(12)

else:
    logging.info("Failed to retrieve the webpage")


#endregion