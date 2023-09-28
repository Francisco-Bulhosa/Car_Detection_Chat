import requests
from bs4 import BeautifulSoup
import time
import logging
import sqlite3 
from datetime import datetime
import re

#region # Create Database

def initialize_database():
    conn = sqlite3.connect("C:\\Users\\franc\\Documents\\GitHub\\Car_Detection_Chat\\car_listings.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (strftime('%Y-%m-%d %H:00', 'now')),
        make TEXT,
        model TEXT,
        year TEXT,
        listing_price TEXT,
        url TEXT
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
                    year = words[1]
                    make = words[2]
                    model = ' '.join(words[3:])
                    return make, model, year
            return None, None, None  # Return None values if extraction fails
            if make:
                make_text = make.get_text(strip=True)
                scraped_data["make"] = description_text

            if model:
                model_text = model.get_text(strip=True)
                scraped_data["model"] = description_text

            if year:
                year_text = year.get_text(strip=True)
                scraped_data["year"] = description_text



            # # Scrape make
            # make_element = details_soup.find("div", class_="detail-info-description-txt")
            # if make_element:
            #     description_text = make_element.get_text(strip=True)
            #     scraped_data["make"] = description_text


            # # Scrape model
            # model_element = details_soup.find("div", class_="detail-info-description-txt")
            # if model_element:
            #     description_text = model_element.get_text(strip=True)
            #     scraped_data["model"] = description_text

            # # Scrape model
            # year_element = details_soup.find("div", class_="detail-info-description-txt")
            # if year_element:
            #     description_text = year_element.get_text(strip=True)
            #     scraped_data["year"] = description_text


            # # Initialize listing_price to None
            # listing_price = None
            # # Scrape listing price
            # listing_price_element = details_soup.find("div", class_="property-price")
            # if listing_price_element is not None:
            #     # Get the text of the span element
            #     listing_price_text = listing_price_element.get_text(strip=True)
                
            #     # Remove unwanted characters like "€" and "Simular prestação"
            #     listing_price_cleaned = listing_price_text.replace("€", "").replace("Simular prestação", "").strip()
                
            #     # Remove dots and replace commas with dots for conversion to float
            #     listing_price_cleaned = listing_price_cleaned.replace(".", "").replace(",", ".")
                
            #     try:
            #         # Convert the cleaned listing price to a float
            #         listing_price = float(listing_price_cleaned)
                    
            #         # Store the cleaned listing price in the scraped_data dictionary
            #         scraped_data["listing_price"] = listing_price
            #     except ValueError:
            #         logging.error("Failed to convert listing_price to float.")
            # else:
            #     logging.error("Failed to find the listing price element.")




            # # Scrape listing date
            # listing_date_element = details_soup.find("div", class_="property-lastupdate")
            # if listing_date_element:
            #     listing_date_text = listing_date_element.text.strip()
                
            #     # Using regex to find the date pattern in the text
            #     match = re.search(r"(\d+ de \w+)", listing_date_text)
            #     if match:
            #         extracted_date_text = match.group(1)
                    
            #         # Translate month names from Portuguese to English
            #         month_translation = {
            #             'janeiro': 'January',
            #             'fevereiro': 'February',
            #             'março': 'March',
            #             'abril': 'April',
            #             'maio': 'May',
            #             'junho': 'June',
            #             'julho': 'July',
            #             'agosto': 'August',
            #             'setembro': 'September',
            #             'outubro': 'October',
            #             'novembro': 'November',
            #             'dezembro': 'December'
            #         }
                    
            #         day, _, month = extracted_date_text.split(' ')
            #         month_in_english = month_translation[month.lower()]
                    
            #         # Convert to MM-DD format
            #         formatted_date = datetime.strptime(f"{day} {month_in_english}", "%d %B").strftime("%m-%d")
            #         scraped_data["listing_date"] = formatted_date
            #     else:
            #         logging.error("Failed to extract the date from the listing date text.")
            # else:
            #     logging.error("Failed to find the listing date element.")


        #     return scraped_data
        # else:
        #     logging.info(f"Failed to retrieve details page with status code {response.status_code}")
        #     return None
        

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