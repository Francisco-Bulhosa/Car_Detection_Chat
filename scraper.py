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




# Insert into database

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



def get_next_image_index(year, make, model):
    # Combine year, make, and model into a single string, replacing spaces with underscores
    prefix = f"{year}_{make}_{model}_"
    # Get a list of all existing files that match this prefix
    existing_files = Path("images").glob(f"{prefix}*.jpg")
    # Extract the image indices from these filenames, and find the highest index
    existing_indices = [int(f.stem.split('_')[-1]) for f in existing_files]
    next_index = max(existing_indices, default=0) + 1
    return next_index



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



# SCRAPER RESILIENCE

#region


# Initialize a UserAgent object
ua = UserAgent()

def get_random_user_agent():
    return ua.random

def random_delay():
    delay = random.uniform(4, 17)  # Random delay between 2 and 10 seconds
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

            # Assume year, make, and model are obtained as before
            year, make, model = scraped_data["year"], scraped_data["make"], scraped_data["model"]

            # Ensure the images directory exists
            if not os.path.exists('images'):
                os.makedirs('images')


            gallery_slides = details_soup.find('gallery-slides')
            image_tags = gallery_slides.find_all('img', limit=10) if gallery_slides else []

            for index, img_tag in enumerate(image_tags, start=1):
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
                    img = Image.open(img_data)

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
                    
                    
                    # Get the next available image index for this car model
                    next_index = get_next_image_index(year, make, model)
                    filename = f"images/{year}_{make}_{model}_{next_index}.jpg"
                    img_cropped.save(filename)
                else:
                    logging.error(f"Failed to retrieve image {img_url}")

                    
            return scraped_data

        else:
            logging.info(f"Failed to retrieve details page with status code {response.status_code}")
            return None
        

#endregion

 