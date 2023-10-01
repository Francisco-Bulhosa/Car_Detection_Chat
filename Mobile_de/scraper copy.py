import requests
from bs4 import BeautifulSoup
import time
import logging
import sqlite3 
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor
from fake_useragent import UserAgent
import random
from PIL import Image
from io import BytesIO
import os
from pathlib import Path


#region # DATABASE

def url_exists(url):
    try:
        conn = sqlite3.connect("C:\\Users\\franc\\Documents\\GitHub\\Car_Detection_Chat\\Mobile_de\\car_mobile_listings.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM car_mobile_listings WHERE url = ?", (url,))
        result = cursor.fetchone()
        
        conn.close()
        
        return result is not None
    except Exception as e:
        logging.error(f"Failed to check URL existence: {e}")
        return False  # Assume URL does not exist in case of an error



def initialize_database():
    try: 
        conn = sqlite3.connect("C:\\Users\\franc\\Documents\\GitHub\\Car_Detection_Chat\\Mobile_de\\car_mobile_listings.db")
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_mobile_listings (
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




# Insert into database

def insert_into_database(data):
    conn = sqlite3.connect("car_mobile_listings.db")
    cursor = conn.cursor()
    # Query the database to check for duplicate listings
    cursor.execute("""
    SELECT * FROM car_mobile_listings WHERE 
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
        INSERT INTO car_mobile_listings (
            make, model, year, mileage, listing_price, url)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get('make'), data.get('model'), data.get('year'), data.get('mileage'), data.get('listing_price'), 
            data.get('url')
        ))
        conn.commit()
    
    conn.close()

#endregion



def get_next_image_index(year, make, model):
    # Replace spaces in make and model names
    make = make.replace(' ', '_')
    model = model.replace(' ', '_')

    # Combine year, make, and model into a single string, replacing spaces with underscores
    prefix = f"{year}_{make}_{model}_"

    # Log the prefix to ensure it's formatted correctly
    logging.info(f"Prefix: {prefix}")

    # Get a list of all existing files that match this prefix
    existing_files = list(Path("images").glob(f"{prefix}*.jpg"))
    # Log the existing files to check if glob is working correctly
    logging.info(f"Existing files: {existing_files}")

    # Extract the image indices from these filenames, and find the highest index
    existing_indices = [int(f.stem.split('_')[-1]) for f in existing_files]
    next_index = max(existing_indices, default=0) + 1
    logging.info(f'Existing files for {prefix}: {list(existing_files)}')
    logging.info(f'Next image index for {year}_{make}_{model}: {next_index}')
    return next_index



def get_next_page_url(soup):
    next_page_btn = soup.find('span', {'id': 'page-forward'})
    if next_page_btn and 'data-href' in next_page_btn.attrs:
        return next_page_btn['data-href']
    return None


def get_listings(soup):
    listings = []

    # Look for div elements that have either 'cBox-body cBox-body--resultitem' or 'cBox-body cBox-body--eyeCatcher' as their class

    vehicle_cards = soup.find_all('div', class_=['cBox-body cBox-body--resultitem', 'cBox-body cBox-body--eyeCatcher'])
    
    for vehicle_card in vehicle_cards:
        a_tag = vehicle_card.find('a', {'class': 'link--muted no--text--decoration result-item'})
        if a_tag and 'href' in a_tag.attrs:
            listing_url = a_tag['href']
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



# SCRAPER RESILIENCE

#region


# Initialize a UserAgent object
ua = UserAgent()

def get_random_user_agent():
    return ua.random

def random_delay():
    delay = random.uniform(3, 12)  # Random delay between 2 and 10 seconds
    time.sleep(delay)

# Initialize a requests session
session = requests.Session()

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

            scraped_data['url'] = details_url

        
            heading = details_soup.find('h1', {'class': 'h2 u-text-break-word'})
            if heading:
                text_content = heading.get_text(strip=True)
                words = text_content.split()
                if len(words) > 2:
                    scraped_data["make"] = words[0]
                    scraped_data["model"] = ' '.join(words[1:])
                else:
                    logging.error(f'Failed to extract make and model from heading: {text_content}')
                    return None  # Return None if extraction fails

            year_div = details_soup.find('div', {'class': 'key-feature__value'})
            if year_div:
                year_text = year_div.get_text(strip=True)
                # Assuming the year is always in the format MM/YYYY, split by '/' and take the second part
                year = year_text.split('/')[1]
                scraped_data["year"] = year
            else:
                logging.error('Failed to extract year')
                # Handle the error or set a default value
                scraped_data["year"] = None

                
            # Assuming the conversion rate from Euro to Dollar is 1.06
            conversion_rate = 1.06

            # Update the selector to match the class and data-testid attributes
            price_tag = details_soup.find('span', {'class': 'h3', 'data-testid': 'prime-price'})
            if price_tag:
                price_text = price_tag.get_text(strip=True)
                # Remove commas and the Euro symbol, if any, to convert to float later
                price_euro = price_text.replace(',', '').replace('€', '')
                try:
                    # Convert the price to float (or integer if you prefer)
                    price_euro = float(price_euro)
                    # Convert the price to Dollars
                    price_dollar = price_euro * conversion_rate
                    # Store the dollar price in your data dictionary
                    scraped_data['listing_price'] = price_dollar
                except ValueError:
                    logging.error(f'Failed to convert price to number: {price_text}')
                    return None  # or handle the error in some other way
            else:
                logging.warning(f'Failed to extract listing price from {details_url}')


            # Conversion factor from kilometers to miles
            km_to_miles_conversion_factor = 0.621371

            # Update the selector to match the id attribute
            mileage_div = details_soup.find('div', {'id': 'mileage-v'})
            if mileage_div:
                # Replace HTML non-breaking space with normal space, and commas if any
                mileage_text = mileage_div.get_text(strip=True).replace('\xa0', ' ').replace(',', '')
                # Extract only the numeric value using regex
                mileage_match = re.search(r'(\d+)', mileage_text)
                if mileage_match:
                    mileage_km = int(mileage_match.group(1))
                    # Convert the mileage to miles
                    mileage_miles = mileage_km * km_to_miles_conversion_factor
                    scraped_data['mileage'] = int(mileage_miles) 
                else:
                    logging.warning(f'Failed to extract mileage integer from {mileage_text}')
            else:
                logging.warning(f'Failed to extract mileage from {details_url}')


            # Assume year, make, and model are obtained as before
            year, make, model = scraped_data["year"], scraped_data["make"], scraped_data["model"]

            # Ensure the images directory exists
            if not os.path.exists('images'):
                os.makedirs('images')


            # Find all div elements with a class of 'gallery-img-wrapper'
            gallery_wrappers = details_soup.find_all('div', class_='gallery-img-wrapper', limit=10)





            for index, gallery_wrapper in enumerate(gallery_wrappers, start=1):
                img_tag = gallery_wrapper.find('img')  # Find the img element within the div
                if img_tag and 'src' in img_tag.attrs:
                    img_url = img_tag['src']

                    try:
                        response = requests.get(img_url)
                        response.raise_for_status()
                    except requests.RequestException as e:
                        logging.error(f"Failed to retrieve image {img_url}: {e}")
                        continue  # Skip to the next image if an error occurs
                    
                    # To help avoid rate limiting, add a delay between requests
                    random_delay()  # Randomized delay here
                    
                    if response.status_code == 200:
                        img_data = BytesIO(response.content)  # Save image data as binary
                        try:
                            img = Image.open(img_data)
                        except UnidentifiedImageError:
                            logging.warning(f"Unidentified image format from URL {img_url}. Skipping...")
                            continue

                        # ... rest of your image processing and saving code ...
                    else:
                        logging.error(f"Failed to retrieve image {img_url}")
                else:
                    logging.warning(f"No 'src' attribute found for image {index}.")

                if index >= 10:
                    break  # Exit the loop after processing 10 images

                    # Determine the aspect ratio
                    width, height = img.size
                    aspect_ratio = width / height

                    # Resize the image so the smallest side is 224 pixels
                    if width < height:
                        new_width = 224
                        new_height = int(224 / aspect_ratio)
                    else:
                        new_height = 224
                        new_width = int(224 * aspect_ratio)
                    img_resized = img.resize((new_width, new_height), Image.ANTIALIAS)

                    # Determine the position for the crop
                    left = (img_resized.width - 224)/2
                    top = (img_resized.height - 224)/2
                    right = (img_resized.width + 224)/2
                    bottom = (img_resized.height + 224)/2

                    # Crop to 224x224
                    img_cropped = img_resized.crop((left, top, right, bottom))
                    
                    # Convert RGBA to RGB if necessary before saving as JPEG
                    if img_cropped.mode == 'RGBA':
                        img_cropped = img_cropped.convert('RGB')
                    
                    # Get the next available image index for this car model
                    next_index = get_next_image_index(year, make, model)

                    # Replace spaces and slashes in make and model names
                    make_model = f"{make}_{model}".replace(' ', '_').replace('/', '')

                    # Construct the filename
                    filename = f"images/{year}_{make_model}_{next_index}.jpg"
                    
                    img_cropped.save(filename)
                else:
                    logging.error(f"Failed to retrieve image {img_url}")

                    
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
    start_url = "https://suchen.mobile.de/fahrzeuge/search.html?dam=0&isSearchRequest=true&od=down&p=90000%3A&ref=srp&refId=74a5a299-da39-e4c6-0037-f53f20e7ebb6&s=Car&sb=p&vc=Car"


    # Counter for the number of listings scraped
    count = 0
    max_count = 3000  # Maximum number of listings to scrape

        # Counter for the number of failed attempts to fetch next pages
    failed_next_page_count = 0
    max_failed_next_page_count = 5  # Maximum number of failed attempts

    current_url = start_url

    while current_url and count < max_count:  # Modified this line to include count < max_count

        # Set a random User-Agent for each request
        session.headers['User-Agent'] = get_random_user_agent()


        try:
            response = requests.get(current_url)
            response.raise_for_status()  # Will raise HTTPError for bad responses (4xx and 5xx)
        except requests.RequestException as e:
            logging.warning(f"Failed to retrieve page {current_url}: {e}")
            failed_next_page_count += 1
            if failed_next_page_count >= max_failed_next_page_count:
                logging.error("Max failed attempts reached. Exiting.")
                break
            random_delay()  # Randomized delay here
            continue

        if response.status_code == 200:

            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get the listing URLs from the current page
            listing_urls = get_listings(soup)

            for listing_url in listing_urls:
                if count >= max_count:
                    break  # Break the loop if maximum count reached

                # Check if the URL already exists in the database
                if url_exists(listing_url):
                    logging.info(f"Skipping already scraped URL: {listing_url}")
                    continue  # Skip to the next URL

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
            next_button = soup.find('li', {'id': 'page-forward'})
            if next_button and 'data-href' in next_button.attrs:
                current_url = next_button['data-href']
            else:
                logging.info("No more pages to scrape. Exiting.")
                break
        
        random_delay()  # Randomized delay here

    # Sleep for a short time to respect the website's rate-limiting
    time.sleep(12)

else:
    logging.info("Failed to retrieve the webpage")


# endregion

# import sqlite3

# # Connect to database
# conn = sqlite3.connect('car_listings.db')

# # Create a cursor
# c = conn.cursor()

# # Execute DELETE command
# c.execute("DELETE FROM car_listings WHERE id > 26")

# # Commit changes
# conn.commit()

# # Close the connection
# conn.close()
