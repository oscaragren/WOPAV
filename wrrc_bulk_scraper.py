#!/usr/bin/env python3
"""
Bulk WRRC Competition Scraper with Interactive Filters

This script allows users to scrape multiple competitions based on filters:
- Dance (e.g., "BW" for Boogie Woogie)
- Class (e.g., "Main Class")
- Round (e.g., "Semi Final")
- Year range (e.g., "2022-2025")
"""

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from wrrc_openmarkings import (
    scrape_wrrc_results, 
    get_competition_info,
    sanitize_filename,
    format_date_for_filename
)
import os
import json
from tqdm import tqdm


def check_competition_exists(base_url):
    """Check if a competition base URL exists."""
    if not base_url.endswith('/'):
        base_url += '/'
    try:
        response = requests.get(base_url + 'naslov.htm', timeout=5)
        return response.status_code == 200
    except:
        return False


def find_valid_competitions(year, max_workers=20):
    """
    Find all valid competition IDs for a given year by testing all 4-digit combinations.
    Uses parallel threading for faster discovery.
    
    Args:
        year: Year to search (e.g., 2025)
        max_workers: Maximum number of concurrent thread workers (default 20 for I/O-bound operations)
    
    Returns:
        list: List of valid competition IDs (4-digit strings)
    """
    valid_competitions = []
    base_url_template = f"https://www.wrrc.org/results/{year}-{{id}}/"
    
    def check_id(comp_id):
        comp_id_str = f"{comp_id:04d}"
        base_url = base_url_template.format(id=comp_id_str)
        if check_competition_exists(base_url):
            return comp_id_str
        return None
    
    print(f"\nSearching for valid competitions in year {year}...")
    print("This may take a while (testing 10,000 combinations)...\n")
    
    # Use ThreadPoolExecutor for parallel checking
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(check_id, i): i for i in range(10000)}
        
        # Collect results with tqdm progress bar
        with tqdm(total=10000, desc=f"Year {year}", unit="checks") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result:
                    valid_competitions.append(result)
                    tqdm.write(f"  ✓ Found valid competition: {year}-{result}")
                
                # Update progress bar
                pbar.update(1)
    
    print(f"\n✓ Found {len(valid_competitions)} valid competitions for year {year}\n")
    return valid_competitions


def discover_rounds_for_competition(year, comp_id, max_round_id=3000, max_workers=10):
    """
    Discover rounds for a competition by trying round IDs.
    Uses parallel threading for faster discovery.
    
    Args:
        year: Year of competition
        comp_id: 4-digit competition ID
        max_round_id: Maximum round ID to try (default 3000)
        max_workers: Maximum number of concurrent thread workers (default 10)
    
    Returns:
        list: List of round URLs that exist
    """
    base_url = f"https://www.wrrc.org/results/{year}-{comp_id}/"
    rounds = []
    
    def check_round_id(round_id):
        round_url = f"{base_url}ocj_{round_id}.htm"
        try:
            response = requests.get(round_url, timeout=3)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.find('table') and ('Position' in response.text or 'Stn.' in response.text):
                    return round_url
        except:
            pass
        return None
    
    # Use parallel processing for faster discovery
    round_ids = list(range(1000, max_round_id + 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_round_id, rid): rid for rid in round_ids}
        with tqdm(total=len(round_ids), desc=f"  {year}-{comp_id}", unit="rounds", leave=False) as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result:
                    rounds.append(result)
                pbar.update(1)
    
    return rounds


def matches_filters(round_url, dance_filter=None, class_filter=None, round_filter=None):
    """
    Check if a round URL matches the given filters.
    
    Args:
        round_url: URL of the round to check
        dance_filter: Filter for dance (case-insensitive, partial match)
        class_filter: Filter for class (case-insensitive, partial match)
        round_filter: Filter for round name (case-insensitive, partial match)
    
    Returns:
        dict or None: Round info dict if matches, None otherwise
    """
    try:
        results = scrape_wrrc_results(round_url)
        comp_info = results.get("competition_info", {})
        
        dance = comp_info.get("dance", "").lower()
        class_name = comp_info.get("class", "").lower()
        round_name = comp_info.get("round", "").lower()
        
        # Check filters
        if dance_filter and dance_filter.lower() not in dance:
            return None
        if class_filter and class_filter.lower() not in class_name:
            return None
        if round_filter and round_filter.lower() not in round_name:
            return None
        
        return {
            "url": round_url,
            "competition_info": comp_info,
            "num_couples": len(results.get("couples", []))
        }
    except Exception as e:
        return None


def scrape_matching_rounds(year_start, year_end, dance_filter=None, class_filter=None, 
                           round_filter=None, max_workers=10):
    """
    Scrape all rounds matching the given filters across all years and competitions.
    Uses parallel threading for faster discovery and filtering.
    
    Args:
        year_start: Starting year
        year_end: Ending year (inclusive)
        dance_filter: Filter for dance
        class_filter: Filter for class
        round_filter: Filter for round name
        max_workers: Maximum number of concurrent thread workers (default 10)
    
    Returns:
        list: List of scraped results
    """
    all_results = []
    
    # Find valid competitions for each year (with higher parallelism)
    all_competitions = []
    for year in range(year_start, year_end + 1):
        print(f"\n{'='*60}")
        print(f"Processing year {year}")
        print(f"{'='*60}")
        comp_ids = find_valid_competitions(year, max_workers=max_workers * 2)  # More workers for competition discovery
        for comp_id in comp_ids:
            all_competitions.append((year, comp_id))
    
    print(f"\n{'='*60}")
    print(f"Found {len(all_competitions)} total competitions")
    print(f"{'='*60}\n")
    
    # Discover rounds for each competition (parallel across competitions)
    print("Discovering rounds for all competitions...")
    all_rounds = []
    
    def discover_rounds_wrapper(comp_tuple):
        year, comp_id = comp_tuple
        return discover_rounds_for_competition(year, comp_id, max_workers=max_workers)
    
    # Use parallel processing to discover rounds for multiple competitions simultaneously
    with ThreadPoolExecutor(max_workers=min(5, len(all_competitions))) as executor:
        round_futures = {executor.submit(discover_rounds_wrapper, comp): comp for comp in all_competitions}
        for future in tqdm(as_completed(round_futures), total=len(all_competitions), desc="Discovering rounds", unit="competition"):
            rounds = future.result()
            all_rounds.extend(rounds)
            time.sleep(0.05)  # Small delay to be respectful
    
    print(f"\n✓ Discovered {len(all_rounds)} total rounds\n")
    
    # Filter rounds based on criteria (parallel filtering)
    print("Filtering rounds based on criteria...")
    matching_rounds = []
    
    def filter_round_wrapper(round_url):
        return matches_filters(round_url, dance_filter, class_filter, round_filter)
    
    # Use parallel processing for filtering
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        filter_futures = {executor.submit(filter_round_wrapper, url): url for url in all_rounds}
        for future in tqdm(as_completed(filter_futures), total=len(all_rounds), desc="Filtering rounds", unit="round"):
            match_info = future.result()
            if match_info:
                matching_rounds.append(match_info)
                tqdm.write(f"  ✓ Match: {match_info['url']}")
    
    print(f"\n✓ Found {len(matching_rounds)} matching rounds\n")
    
    # Scrape all matching rounds (sequential to avoid overwhelming the server)
    print("Scraping matching rounds...")
    for i, match_info in enumerate(tqdm(matching_rounds, desc="Scraping rounds", unit="round"), 1):
        round_url = match_info["url"]
        tqdm.write(f"\n[{i}/{len(matching_rounds)}] Scraping: {round_url}")
        try:
            results = scrape_wrrc_results(round_url)
            all_results.append(results)
            
            # Save individual file
            comp_info = results.get("competition_info", {})
            location = sanitize_filename(comp_info.get("location", "Unknown"), use_hyphens=True)
            date = format_date_for_filename(comp_info.get("date", "Unknown"))
            class_name = sanitize_filename(comp_info.get("class", "Unknown"), use_hyphens=True)
            round_name = sanitize_filename(comp_info.get("round", "Unknown"), use_hyphens=True)
            
            output_filename = f"results_{location}_{date}_{class_name}_{round_name}.json"
            results_dir = "results"
            os.makedirs(results_dir, exist_ok=True)
            output_file = os.path.join(results_dir, output_filename)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            tqdm.write(f"  ✓ Saved to: {output_file}")
        except Exception as e:
            tqdm.write(f"  ✗ Error scraping {round_url}: {e}")
    
    return all_results


def main():
    """Interactive main function for bulk scraping."""
    print("="*60)
    print("WRRC Bulk Competition Scraper")
    print("="*60)
    print("\nThis tool will help you scrape competitions based on filters.\n")
    
    # Get user input for filters
    print("Enter filters (press Enter to skip any filter):")
    print("-"*60)
    
    dance_filter = input("1. Dance filter (e.g., 'BW' or 'Boogie Woogie'): ").strip()
    if not dance_filter:
        dance_filter = None
    
    class_filter = input("2. Class filter (e.g., 'Main Class' or 'Juniors'): ").strip()
    if not class_filter:
        class_filter = None
    
    round_filter = input("3. Round filter (e.g., 'Semi Final' or 'Final'): ").strip()
    if not round_filter:
        round_filter = None
    
    year_range = input("4. Year range (e.g., '2022-2025'): ").strip()
    if not year_range:
        print("\nError: Year range is required!")
        return
    
    # Parse year range
    try:
        if '-' in year_range:
            year_start, year_end = year_range.split('-')
            year_start = int(year_start.strip())
            year_end = int(year_end.strip())
        else:
            year_start = year_end = int(year_range.strip())
    except ValueError:
        print("\nError: Invalid year range format! Use format like '2022-2025'")
        return
    
    # Show summary
    print("\n" + "="*60)
    print("Scraping Summary")
    print("="*60)
    print(f"Dance filter: {dance_filter or '(none)'}")
    print(f"Class filter: {class_filter or '(none)'}")
    print(f"Round filter: {round_filter or '(none)'}")
    print(f"Year range: {year_start}-{year_end}")
    print("="*60)
    
    confirm = input("\nProceed with scraping? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Scraping cancelled.")
        return
    
    # Optional: Configure number of workers
    workers_input = input("\nNumber of parallel workers (default 10, press Enter to use default): ").strip()
    if workers_input:
        try:
            max_workers = int(workers_input)
            if max_workers < 1:
                max_workers = 10
                print("Invalid number, using default 10")
        except ValueError:
            max_workers = 10
            print("Invalid input, using default 10")
    else:
        max_workers = 10
    
    print(f"Using {max_workers} parallel workers for discovery and filtering.\n")
    
    # Start scraping
    print("\nStarting bulk scrape...\n")
    results = scrape_matching_rounds(
        year_start, 
        year_end, 
        dance_filter=dance_filter,
        class_filter=class_filter,
        round_filter=round_filter,
        max_workers=max_workers
    )
    
    print(f"\n{'='*60}")
    print(f"Scraping complete! Scraped {len(results)} rounds.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
