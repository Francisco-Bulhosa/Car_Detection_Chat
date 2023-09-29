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


            heading = details_soup.find('h1', {'data-cmp': 'heading', 'class': 'text-bold'})
            if heading:
                text_content = heading.get_text(strip=True)
                words = text_content.split()
                if len(words) > 2:
                    scraped_data["year"] = words[1]
                    scraped_data["make"] = words[2]
                    scraped_data["model"] = ' '.join(words[3:])
                else:
                    logging.error(f'Failed to extract make, model, and year from heading: {text_content}')
                    return None  # Return None if extraction fails
                
            # Find the span tag containing the listing price
            price_tag = details_soup.find('span', {'class': 'first-price', 'data-cmp': 'firstPrice'})
            if price_tag:
                # Check for the presence of MSRP
                if "MSRP" in price_tag.get_text():
                    logging.info(f'Skipping {details_url} due to presence of MSRP.')
                    return None  # Return None to indicate that this listing should not be scraped
                
                # If MSRP is not present, proceed to extract the price
                price_text = price_tag.get_text(strip=True)
                # Remove commas, if any, to convert to integer later
                scraped_data['listing_price'] = price_text.replace(',', '')
            else:
                logging.warning(f'Failed to extract listing price from {details_url}')

            # Find the div tag containing the mileage
            mileage_div = details_soup.find('div', {'class': 'col-xs-10', 'class': 'margin-bottom-0'})
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



# Create a function to check if a listing is inactive based on the provided HTML snippet

def is_listing_inactive(soup):
    inactive_div = soup.find('div', {'data-cmp': 'heading', 'class': 'text-bold'})
    if inactive_div:
        return "This car is no longer available." in inactive_div.get_text()
    return False






#region  # Main
if __name__ == "__main__":
    initialize_database()
    logging.basicConfig(level=logging.INFO)


    # Starting URL
    start_url = "https://www.kbb.com/cars-for-sale/vehicle/{}"


    # Counter for the number of listings scraped
    count = 0
    max_count = 500  # Maximum number of listings to scrape

        # Counter for the number of failed attempts to fetch next page
    failed_next_page_count = 0
    max_failed_next_page_count = 5  # Maximum number of failed attempts

    inactive_listing_ids = set()

    # Load cached inactive listing IDs (if any) from a file
    try:
        with open('inactive_listing_ids.txt', 'r') as file:
            inactive_listing_ids = set(file.read().splitlines())
    except FileNotFoundError:
        pass  # It's okay if the file doesn't exist yet


    while start_url and count < max_count:  # Modified this line to include count < max_count
    # while start_url:
        for listing_id in range(685000000, 699000000 + 1):
            if str(listing_id) in inactive_listing_ids:
                continue
            
            listing_url = start_url.format(listing_id)
            try:
                response = requests.get(listing_url)
            except requests.RequestException as e:
                logging.warning(f"Failed to retrieve listing {listing_id}: {e}")
                continue  # Skip to the next listing_id if a network error occurs

            if response.status_code == 200:

                soup = BeautifulSoup(response.content, 'html.parser')

                if is_listing_inactive(soup):
                    logging.info(f"Listing {listing_id} is inactive. Caching and skipping.")
                    inactive_listing_ids.add(str(listing_id))  # Cache inactive listing ID
                    continue  # Skip to the next listing_id

                details_data = scrape_details(listing_url)
            
                if details_data:  # Check if details were successfully scraped
                    insert_into_database(details_data)  # Insert data into the database
                    
                    # Increase the count for each listing processed
                    count += 1
                    
                    if count > max_count:  # New condition
                        break  # Break the loop if maximum count reached

                        # Print the scraped details
                        print(details_data)
                else:
                    logging.info("Failed to scrape details for this listing.")


        if count >= max_count:  # New condition
            logging.info(f"Reached the maximum count of {max_count}. Exiting.")
            break  # Break the loop if maximum count reached

        # Sleep for a short time to respect the website's rate-limiting
        time.sleep(8)

    else:
        logging.info("Failed to retrieve the webpage")
        start_url = None

    # Save cached inactive listing IDs
    with open('inactive_listing_ids.txt', 'w') as file:
        for listing_id in inactive_listing_ids:
            file.write(f"{listing_id}\n")


#endregion