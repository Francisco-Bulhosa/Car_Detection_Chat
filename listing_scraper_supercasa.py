import requests
from bs4 import BeautifulSoup
import time
import logging
import sqlite3 
from SQLite_db import initialize_database
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

#region # Create Database

def initialize_database():
    conn = sqlite3.connect("listings.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (strftime('%Y-%m-%d %H:00', 'now')),
        address TEXT,
        zone TEXT,
        thumbnail TEXT,
        listing_price TEXT,
        listing_date TEXT,
        property_type TEXT,
        construction_year INTEGER,
        url TEXT,
        square_meters_built REAL,
        total_sq_meter REAL,
        price_per_sq_meter REAL,
        number_of_rooms INTEGER,
        number_of_baths INTEGER,
        with_elevator INTEGER DEFAULT 0, 
        with_garage INTEGER DEFAULT 0,
        living_rooms INTEGER,
        kitchens INTEGER,
        latitude INTEGER,
        longitude INTEGER,
        description TEXT
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
        address = ? AND 
        listing_price = ? AND 
        property_type = ? AND 
        square_meters_built = ?
    """, (
        data.get('address'), 
        data.get('listing_price'), 
        data.get('property_type'), 
        data.get('square_meters_built')
    ))
    
    # Fetch the result to see if a duplicate exists
    duplicate = cursor.fetchone()
    
    # If no duplicate is found, insert the data
    if not duplicate:
        cursor.execute("""
        INSERT INTO listings (
            address, zone, thumbnail, listing_price, listing_date, property_type, construction_year,
            url, square_meters_built, total_sq_meter, price_per_sq_meter,
            number_of_rooms, number_of_baths, with_elevator, with_garage, living_rooms, kitchens, latitude, longitude, description
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('address'), data.get('zone'), data.get('thumbnail'), data.get('listing_price'), 
            data.get('listing_date'), data.get('property_type'), data.get('construction_year'), 
            data.get('url'), data.get('square_meters_built'),
            data.get('total_sq_meter'), data.get('price_per_sq_meter'), data.get('number_of_rooms'),
            data.get('number_of_baths'), data.get('with_elevator', 0),
            data.get('with_garage', 0), data.get('living_rooms'), data.get('kitchens'), data.get('latitude'),
            data.get('longitude'), data.get('description')
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

            # Scrape description
            description_element = details_soup.find("div", class_="detail-info-description-txt")
            if description_element:
                description_text = description_element.get_text(strip=True)
                scraped_data["description"] = description_text


            # Locate the div element with class "detail-info-map-info"
            address_div = details_soup.find("div", class_="detail-info-map-info")


            # List of predefined zones
            zones = [
                "Costa da Caparica",
                "Caparica e Trafaria",
                "Charneca de Caparica e Sobreda",
                "Laranjeiro e Feijó",
                "Almada, Cova da Piedade, Pragal e Cacilhas"
            ]

            # Check if the address div was found
            if address_div:
                # Replace <br> tags with commas
                for br in address_div.find_all("br"):
                    br.replace_with(", ")

                # Extract the text from the address div
                address_text = address_div.get_text(strip=True)

                # Store the complete address in the scraped_data dictionary
                scraped_data["address"] = address_text

                # Check for a matching zone in the scraped address
                matched_zone = "Almada"  # default value
                for potential_zone in zones:
                    if potential_zone in address_text:
                        matched_zone = potential_zone
                        break

                # Store the matched or default zone in the scraped_data dictionary
                scraped_data["zone"] = matched_zone

            else:
                # Log an error message if address extraction fails
                logging.error("Failed to extract address from the page.")


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


            from datetime import datetime
            import re

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



            # Scrape property type
            property_type = details_soup.find("div", class_="property-type")
            if property_type:
                scraped_data["property_type"] = property_type.text.strip()


            # Scrape URL 
            scraped_data["url"] = details_url

            # Find all the <span> elements under <div class="property-features">
            info_features = details_soup.find("div", class_="property-features")
            if info_features:
                feature_spans = info_features.find_all("span")
                for feature in feature_spans:
                    feature_text = feature.text.strip()
                    
                    # For square_meters_built
                    if "Área bruta" in feature_text and "m²" in feature_text:
                        try:
                            square_meters_built = float(feature_text.replace("Área bruta", "").replace("m²", "").strip())
                            scraped_data["square_meters_built"] = square_meters_built
                        except ValueError:
                            logging.error("Failed to convert square_meters_built to float.")
                    
                    # For number_of_rooms
                    elif "quartos" in feature_text:
                        try:
                            number_of_rooms = int(feature_text.replace(" quartos", "").strip())
                            scraped_data["number_of_rooms"] = number_of_rooms
                        except ValueError:
                            logging.error("Failed to convert number_of_rooms to int.")
                    
                    # For construction_year
                    elif "Ano construção:" in feature_text:
                        try:
                            construction_year = int(feature_text.replace("Ano construção:", "").strip())
                            scraped_data["construction_year"] = construction_year
                        except ValueError:
                            logging.error("Failed to convert construction_year to int.")



            # Scrape Extended details 
            # Initialize to None before the loop
            scraped_data["with_elevator"] = None
            scraped_data["with_garage"] = None

            # Find all the <span> elements under <div class="info-features">
            info_features_extended = details_soup.find("div", class_="property-features highlights")
            if info_features_extended:
                feature_spans_extended = info_features_extended.find_all("span")
                for feature_extended in feature_spans_extended:
                    feature_text_extended = feature_extended.text.strip()
                    if "Com elevador" in feature_text_extended:
                        scraped_data["with_elevator"] = True  # If it has or not an elevator
                    elif "Com garagem" in feature_text_extended:
                        scraped_data["with_garage"] = True  # if it has a garage
                    else:
                        scraped_data["with_elevator"] = None
                        scraped_data["with_garage"] = None
                        logging.error("Failed to extract extended details from the page.")    
            # Check if data for "Com elevador" and "Com garagem" was not scraped
            if scraped_data["with_elevator"] is None or scraped_data["with_garage"] is None:
                logging.error("Failed to extract extended details for 'Com elevador' or 'Com garagem'.")
            



            # Scrape total square meter
            import re
            total_sq_meter = None  # Initialize the variable
            area_bruta_element = details_soup.find("li", class_="key-feature", string=re.compile("Área Bruta"))
            if area_bruta_element:
                area_bruta_text = area_bruta_element.text.strip()
                try:
                    total_sq_meter = float(area_bruta_text.replace("Área Bruta :", "").replace("m2", "").replace("m²", "").strip())
                    scraped_data["total_sq_meter"] = total_sq_meter
                except ValueError:
                    # Log an error message if conversion to float fails
                    logging.error("Failed to convert total sq/meter to float.")
            else:
                scraped_data["total_sq_meter"] = None
                # Log an error message if total sq meter extraction fails
                logging.error("Failed to extract total sq/meter from the page.")


            # Calculate price per square meter
            if listing_price is not None and total_sq_meter is not None:
                logging.info(f"Listing Price: {listing_price}, Total Sq Meter: {total_sq_meter}")
                price_per_sq_meter = listing_price / total_sq_meter
                scraped_data["price_per_sq_meter"] = price_per_sq_meter
            else:
                price_per_sq_meter = None
                # Log an error message if total sq meter extraction fails
                logging.error("Failed to extract price_per_sq_meter from the page.")



            # Locate the div element containing detail-info-features-list
            features_list_div = details_soup.find("div", class_="detail-info-features-list")
            if features_list_div:
                logging.info("Found 'detail-info-features-list' div.")
                
                divisoes_ul = None
                for ul in features_list_div.find_all("ul"):
                    feature_title_li = ul.find("li", class_="feature-title")
                    if feature_title_li and feature_title_li.text.strip() == "Divisões":
                        divisoes_ul = ul
                        logging.info("Found 'Divisões' ul.")
                        break
                else:
                    logging.error("Failed to find 'Divisões' ul.")
                
                if divisoes_ul:
                    key_features = divisoes_ul.find_all("li", class_="key-feature")
                    if key_features:
                        logging.info("Found key features under 'Divisões'.")
                        for feature in key_features:
                            feature_text = feature.text.strip()
                            
                            # For Casa(s) de Banho
                            if "Casa(s) de Banho :" in feature_text:
                                try:
                                    number_of_baths = int(feature_text.replace("Casa(s) de Banho :", "").strip())
                                    scraped_data["number_of_baths"] = number_of_baths
                                except ValueError:
                                    logging.error("Failed to convert number_of_baths to int.")
                            
                            # For Sala(s)
                            elif "Sala(s) :" in feature_text:
                                try:
                                    living_rooms = int(feature_text.replace("Sala(s) :", "").strip())
                                    scraped_data["living_rooms"] = living_rooms
                                except ValueError:
                                    logging.error("Failed to convert living_rooms to int.")
                            
                            # For Cozinha(s)
                            elif "Cozinha(s) :" in feature_text:
                                try:
                                    kitchens = int(feature_text.replace("Cozinha(s) :", "").strip())
                                    scraped_data["kitchens"] = kitchens
                                except ValueError:
                                    logging.error("Failed to convert kitchens to int.")
                    else:
                        logging.error("Failed to find any key features under 'Divisões'.")
            else:
                logging.error("Failed to find 'detail-info-features-list' div.")




            # Scrape days in market
            days_in_market = details_soup.find("p", class_="property-lastupdate")
            if days_in_market:
                days_text = days_in_market.text.strip()  # Gets "Anúncio atualizado no dia 30 de agosto"
                
                # Extract the date from the text
                date_str = days_text.split(" no dia ")[-1]
                
                # Parse the date using a datetime format that matches the text format
                from datetime import datetime
                date = datetime.strptime(date_str, "%d de %B")
                
                # Calculate the days difference between the scraped date and today's date
                days_difference = (datetime.now() - date).days
                
                scraped_data["days_in_market"] = days_difference  # Stores it in the dictionary
                
                
        
            # Logging to show the scraped data
            logging.info("Scraped Data:")
            for key, value in scraped_data.items():
                logging.info(f"{key}: {value}")


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


    # Initialize Nominatim geolocator
    geolocator = Nominatim(user_agent="geoapiExercises")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=2)

    # Function to get latitude and longitude from address
    def get_lat_lon(address):
        try:
            location = geocode(address)
            if location:
                return location.latitude, location.longitude
        except:
            return None, None
        return None, None



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