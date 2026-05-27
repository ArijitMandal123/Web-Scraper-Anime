import sys
import json
import os

from main import scrape_data, ScrapeRequest

def main():
    # 2. Prepare the test request (The URL you want to scrape)
    test_url = "https://screenrant.com/log-horizon-best-isekai-anime-worldbuilding/"
    print(f"\n--- Testing Scraper with URL: {test_url} ---")
    print("Scraping data...")
    
    request = ScrapeRequest(url=test_url)
    response = scrape_data(request)
    
    output_path = r"test_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, ensure_ascii=False)
    
    if response.get("status") == "success":
        data = response["data"]
        print("\n--- SCRAPE SUCCESSFUL ---")
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        print("\n--- SCRAPE FAILED ---")
        print(json.dumps(response, indent=2, ensure_ascii=False))

    print(f"\nFull JSON output is also saved to {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()
