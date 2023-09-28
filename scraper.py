import requests
from bs4 import BeautifulSoup
import time
import logging
import sqlite3 
from SQLite_db import initialize_database
from datetime import datetime
import re

#region # Create Database

def initialize_database():
    conn = sqlite3.connect("listings.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (strftime('%Y-%m-%d %H:00', 'now')),
        make TEXT,
        model TEXT,
        year TEXT,
        listing_price TEXT,
        url TEXT,
    );
    """)
    
    conn.commit()
    conn.close()

#endregion


#region # Insert into database

def insert_into_database(data):
    conn = sqlite3.connect("listings.db")
    cursor = conn.cursor()
    # Query the database to check for duplicate listings
    cursor.execute("""
    SELECT * FROM listings WHERE 
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
        INSERT INTO listings (
            make, model, year, listing_price, url)
        VALUES (?, ?, ?, ?, ?)
        """, (
            data.get('make'), data.get('model'), data.get('year'), data.get('listing_price'), 
            data.get('url')
        ))
        conn.commit()
    
    conn.close()

#endregion


'https://www.kbb.com/cars-for-sale/used/cars-between-10-and-9999999/?isNewSearch=true&sortBy=derivedpriceDESC'













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

            # Scrape make
            make_element = details_soup.find("div", class_="detail-info-description-txt")
            if make_element:
                description_text = make_element.get_text(strip=True)
                scraped_data["make"] = description_text


            # Scrape make
            make_element = details_soup.find("div", class_="detail-info-description-txt")
            if make_element:
                description_text = make_element.get_text(strip=True)
                scraped_data["make"] = description_text


            # Initialize listing_price to None
            listing_price = None
            # Scrape listing price
            listing_price_element = details_soup.find("div", class_="property-price")
            if listing_price_element is not None:
                # Get the text of the span element
                listing_price_text = listing_price_element.get_text(strip=True)
                
                # Remove unwanted characters like "€" and "Simular prestação"
                listing_price_cleaned = listing_price_text.replace("€", "").replace("Simular prestação", "").strip()
                
                # Remove dots and replace commas with dots for conversion to float
                listing_price_cleaned = listing_price_cleaned.replace(".", "").replace(",", ".")
                
                try:
                    # Convert the cleaned listing price to a float
                    listing_price = float(listing_price_cleaned)
                    
                    # Store the cleaned listing price in the scraped_data dictionary
                    scraped_data["listing_price"] = listing_price
                except ValueError:
                    logging.error("Failed to convert listing_price to float.")
            else:
                logging.error("Failed to find the listing price element.")




            # Scrape listing date
            listing_date_element = details_soup.find("div", class_="property-lastupdate")
            if listing_date_element:
                listing_date_text = listing_date_element.text.strip()
                
                # Using regex to find the date pattern in the text
                match = re.search(r"(\d+ de \w+)", listing_date_text)
                if match:
                    extracted_date_text = match.group(1)
                    
                    # Translate month names from Portuguese to English
                    month_translation = {
                        'janeiro': 'January',
                        'fevereiro': 'February',
                        'março': 'March',
                        'abril': 'April',
                        'maio': 'May',
                        'junho': 'June',
                        'julho': 'July',
                        'agosto': 'August',
                        'setembro': 'September',
                        'outubro': 'October',
                        'novembro': 'November',
                        'dezembro': 'December'
                    }
                    
                    day, _, month = extracted_date_text.split(' ')
                    month_in_english = month_translation[month.lower()]
                    
                    # Convert to MM-DD format
                    formatted_date = datetime.strptime(f"{day} {month_in_english}", "%d %B").strftime("%m-%d")
                    scraped_data["listing_date"] = formatted_date
                else:
                    logging.error("Failed to extract the date from the listing date text.")
            else:
                logging.error("Failed to find the listing date element.")


            # Scrape URL 
            scraped_data["url"] = details_url

            return scraped_data
        else:
            logging.info(f"Failed to retrieve details page with status code {response.status_code}")
            return None
        

#endregion




















#region  # Main
if __name__ == "__main__":
    initialize_database()
    logging.basicConfig(level=logging.INFO)


    # Starting URL
    start_url = "https://supercasa.pt/comprar-casas/almada"


    # Counter for the number of listings scraped
    count = 0
    max_count = 500  # Maximum number of listings to scrape

        # Counter for the number of failed attempts to fetch next page
    failed_next_page_count = 0
    max_failed_next_page_count = 5  # Maximum number of failed attempts



    while start_url and count < max_count:  # Modified this line to include count < max_count
    # while start_url:
        # Make a request to the Idealista website
        response = requests.get(start_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find listings based on the article tag and classes
            listings = soup.find_all("div", class_="property-info")
            
            # Debugging with intermediate variables
            num_listings = len(listings)
            logging.info(f"Found {num_listings} listings on this page.")




            for listing in listings:

                # Extract link to details page
                details_link_element = listing.find("h2", class_="property-list-title")
                if details_link_element:
                    details_link = details_link_element.find("a")

                    if details_link:
                        details_link = details_link.get("href")
                        # Check for None
                        if details_link is not None:
                            # Debugging with intermediate variable
                            logging.info(f"Fetching details from {details_link}")
                            
                            full_details_link = "https://supercasa.pt" + details_link
                            details_data = scrape_details(full_details_link)

                            # Get latitude and longitude for the address in details_data
                            if 'address' in details_data:
                                lat, lon = get_lat_lon(details_data['address'])
                                details_data['latitude'] = lat
                                details_data['longitude'] = lon
                            
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

                else:
                    logging.warning(f"No <a> tag found in details link element: {details_link_element}")

            else:
                logging.warning(f"No details link element found in listing:\n{listing}")
 



        if count >= max_count:  # New condition
            logging.info(f"Reached the maximum count of {max_count}. Exiting.")
            break  # Break the loop if maximum count reached


        
       # Find the next page link
        next_page_element = soup.find("a", {"class": "list-pagination-next", "title": "Seguinte"})

        if next_page_element is not None:
            next_page = next_page_element["href"]
            start_url = "https://supercasa.pt" + next_page
            failed_next_page_count = 0  # Reset the counter for failed attempts
        else:
            logging.info("Next page not found. Exiting.")
            failed_next_page_count += 1  # Increment the counter for failed attempts

            # Exit the script if reached maximum number of failed attempts
            if failed_next_page_count >= max_failed_next_page_count:
                logging.info(f"Failed to find next page {max_failed_next_page_count} times. Exiting.")
                break

        # Sleep for a short time to respect the website's rate-limiting
        time.sleep(8)
    else:
        logging.info("Failed to retrieve the webpage")
        start_url = None


#endregion