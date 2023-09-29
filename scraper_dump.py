



import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent

# Initialize the UserAgent object for user agent rotation
user_agent = UserAgent()

# Initialize the session for session management
session = requests.Session()

# Define a function to scrape a single listing
def scrape_listing(listing_id):
    try:
        listing_url = start_url.format(listing_id)
        headers = {'User-Agent': user_agent.random}  # Randomize user agent
        response = session.get(listing_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        if is_listing_inactive(soup):
            logging.info(f"Listing {listing_id} is inactive. Caching and skipping.")
            inactive_listing_ids.add(str(listing_id))  # Cache inactive listing ID
            return None  # Skip to the next listing_id

        details_data = scrape_details(listing_url)

        if details_data:  # Check if details were successfully scraped
            insert_into_database(details_data)  # Insert data into the database

            # Increase the count for each listing processed
            count += 1

            if count >= max_count:  # New condition
                return None  # Break the loop if maximum count reached

            # Print the scraped details
            print(details_data)
        else:
            logging.info("Failed to scrape details for this listing.")
    
    except requests.RequestException as e:
        logging.warning(f"Failed to retrieve listing {listing_id}: {e}")

    return None

if __name__ == "__main__":
    initialize_database()
    logging.basicConfig(level=logging.INFO)

    # Starting URL
    start_url = "https://www.kbb.com/cars-for-sale/vehicle/{}"

    # Counter for the number of listings scraped
    count = 0
    max_count = 500  # Maximum number of listings to scrape

    # Counter for the number of failed attempts to fetch the next page
    failed_next_page_count = 0
    max_failed_next_page_count = 5  # Maximum number of failed attempts

    inactive_listing_ids = set()

    # Load cached inactive listing IDs (if any) from a file
    try:
        with open('inactive_listing_ids.txt', 'r') as file:
            inactive_listing_ids = set(file.read().splitlines())
    except FileNotFoundError:
        pass  # It's okay if the file doesn't exist yet

    # Create a pool of worker threads for concurrent scraping
    with ThreadPoolExecutor(max_workers=4) as executor:
        while start_url and count < max_count:  # Modified this line to include count < max_count
            for listing_id in random.sample(range(685000000, 699000000 + 1), 10):  # Random permutation
                if str(listing_id) in inactive_listing_ids:
                    continue

                # Submit the scraping task to the thread pool
                future = executor.submit(scrape_listing, listing_id)

                # Wait a random time before submitting the next task
                time.sleep(random.uniform(2, 5))

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



"""
In this modified code:

A thread pool is created using ThreadPoolExecutor to allow concurrent scraping of listings.

User agents are randomized for each request to achieve user agent rotation.

A random sleep time is added between listing requests to introduce randomized delays.

The random.sample function is used to generate a random permutation of listing IDs.

The code continues to scrape until the maximum count is reached.

A session object (session) is used for session management to maintain cookies and session state.


"""