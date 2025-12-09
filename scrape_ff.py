# Scrape final and first round (that have both slow and fast)

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import sys

def sanitize_filename(text, use_hyphens=True):
    """
    Sanitize text for use in a filename by replacing spaces with hyphens
    and removing invalid filename characters while preserving Unicode characters.
    """
    if not text:
        return "Unknown"
    
    if use_hyphens:
        text = text.replace(' ', '-')
    else:
        text = text.replace(' ', '_')
    
    text = text.replace('/', '-').replace('\\', '-')
    text = re.sub(r'[<>:"|?*\\/]', '', text)
    text = re.sub(r'[^\w\-]', '', text)
    text = re.sub(r'[-]+', '-', text)
    text = re.sub(r'[_]+', '_', text)
    text = text.strip('_-')
    
    if len(text) > 100:
        text = text[:100]
    
    return text if text else "Unknown"

def format_date_for_filename(date_str):
    """Format a date string (e.g., "23.08.2025") to filename format (e.g., "23-08-25")."""
    if not date_str:
        return "Unknown"
    
    date_match = re.match(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})', date_str)
    if date_match:
        day, month, year = date_match.groups()
        day = day.zfill(2)
        month = month.zfill(2)
        year_short = year[-2:]
        return f"{day}-{month}-{year_short}"
    
    date_match = re.match(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2})', date_str)
    if date_match:
        day, month, year = date_match.groups()
        day = day.zfill(2)
        month = month.zfill(2)
        return f"{day}-{month}-{year}"
    
    return sanitize_filename(date_str, use_hyphens=True)

def parse_score_cell(cell):
    """
    Parse a score cell that contains:
    - First line: aggregated score (e.g., "2,68")
    - Second line: pipe-separated judge scores (e.g., "3|3|2,625|3,375|1,875|2,625|2,25")
    """
    if not cell:
        return {"aggregated": None, "judge_scores": []}
    
    cell_text = cell.get_text(separator='\n', strip=True)
    
    if not cell_text or not cell_text.strip():
        return {"aggregated": None, "judge_scores": []}
    
    lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
    
    aggregated = lines[0] if lines else None
    if aggregated:
        aggregated = aggregated.strip()
    
    judge_scores = []
    if len(lines) > 1:
        judge_scores_str = lines[1]
        judge_score_parts = judge_scores_str.split('|')
        for score in judge_score_parts:
            score = score.strip()
            if score:
                judge_scores.append(score)
    
    return {
        "aggregated": aggregated,
        "judge_scores": judge_scores
    }

def get_competition_info(base_url):
    """Retrieve the location and date of the competition from the WRRC results page."""
    if not base_url.endswith('/'):
        base_url += '/'
    
    naslov_url = base_url + 'naslov.htm'
    
    try:
        response = requests.get(naslov_url)
        response.raise_for_status()
        
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'

        soup = BeautifulSoup(response.text, "html.parser")
        
        title_cell = soup.find('td', class_='tur_main_naslov')
        
        if not title_cell:
            return {"location": None, "date": None}
        
        text = title_cell.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return {"location": None, "date": None}
        
        first_line = lines[0]
        
        location = None
        if ' - ' in first_line:
            parts = first_line.split(' - ')
            location = parts[-1].strip() if parts else None
        elif ' -' in first_line:
            parts = first_line.split(' -')
            location = parts[-1].strip() if parts else None
        elif '-' in first_line:
            parts = first_line.split('-')
            location = parts[-1].strip() if parts else None
        
        date = None
        if len(lines) > 1:
            date = lines[1].strip()
        
        return {
            "location": location,
            "date": date
        }
        
    except Exception as e:
        print(f"Error retrieving competition info: {e}")
        return {"location": None, "date": None}

def get_judges_for_category(base_url, dance, class_name):
    """Retrieve judges for a specific dance and class from the turnir_naslov.htm page."""
    if not base_url.endswith('/'):
        base_url += '/'
    
    turnir_url = base_url + 'turnir_naslov.htm'
    
    try:
        response = requests.get(turnir_url)
        response.raise_for_status()
        
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        tables = soup.find_all('table', class_='tur_main')
        judges_table = None
        for table in tables:
            header_cells = table.find_all('td', class_='tur_labela')
            for cell in header_cells:
                if 'Judges' in cell.get_text(strip=True):
                    judges_table = table
                    break
            if judges_table:
                break
        
        if not judges_table:
            return []
        
        category_to_match = f"{dance}-{class_name}"
        
        judges = []
        current_judge = None
        current_categories = []
        
        rows = judges_table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            
            judge_letter_cell = None
            for cell in cells:
                if 'tur_slovo' in cell.get('class', []):
                    judge_letter_cell = cell
                    break
            
            if judge_letter_cell:
                if current_judge and any(category_to_match in cat for cat in current_categories):
                    judges.append({
                        "letter": current_judge["letter"],
                        "name": current_judge["name"],
                        "country": current_judge.get("country")
                    })
                
                judge_letter = judge_letter_cell.get_text(strip=True)
                judge_name = None
                judge_country = None
                
                for cell in cells:
                    if 'tur_polje' in cell.get('class', []):
                        judge_name_raw = cell.get_text(strip=True)
                        if judge_name_raw:
                            name_parts = judge_name_raw.split('/', 1)
                            name = name_parts[0].strip()
                            judge_country = name_parts[1].strip() if len(name_parts) > 1 else None
                            
                            name_components = name.split()
                            if len(name_components) >= 2:
                                lastname = name_components[0]
                                firstname = ' '.join(name_components[1:])
                                judge_name = f"{firstname} {lastname}"
                            else:
                                judge_name = name
                        break
                
                current_judge = {
                    "letter": judge_letter,
                    "name": judge_name,
                    "country": judge_country
                }
                current_categories = []
            
            for cell in cells:
                if 'tur_kategorija' in cell.get('class', []):
                    category = cell.get_text(strip=True)
                    if category:
                        current_categories.append(category)
        
        if current_judge and any(category_to_match in cat for cat in current_categories):
            judges.append({
                "letter": current_judge["letter"],
                "name": current_judge["name"],
                "country": current_judge.get("country")
            })
        
        return judges
        
    except Exception as e:
        print(f"Error retrieving judges from {turnir_url}: {e}")
        return []

def scrape_couple_names(base_url, rez_filename):
    """Scrape couple names from the results page (rez_*.htm) and return a dictionary."""
    if not base_url.endswith('/'):
        base_url += '/'
    
    rez_url = base_url + rez_filename
    
    try:
        response = requests.get(rez_url)
        response.raise_for_status()
        
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        results_table = soup.find('table', class_='entrylist_table')
        if not results_table:
            return {}
        
        couple_names = {}
        
        rows = results_table.find_all('tr')[1:]
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            start_number = None
            competitor_name = None
            
            if len(cells) > 1:
                start_number_cell = cells[1]
                start_number_text = start_number_cell.get_text(strip=True)
                if start_number_text.isdigit():
                    start_number = start_number_text
            
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                cell_class = cell.get('class', [])
                cell_class_str = ' '.join(cell_class) if isinstance(cell_class, list) else str(cell_class)
                
                if 'competitor' in cell_class_str:
                    competitor_name = cell_text
                    if ' - ' in competitor_name:
                        parts = competitor_name.split(' - ')
                        formatted_parts = []
                        for part in parts:
                            part = part.strip()
                            name_components = part.split()
                            if len(name_components) >= 2:
                                lastname = name_components[0]
                                firstname = ' '.join(name_components[1:])
                                formatted_name = f"{firstname} {lastname}"
                            else:
                                formatted_name = part
                            formatted_parts.append(formatted_name)
                        competitor_name = " & ".join(formatted_parts)
                    break
            
            if start_number and competitor_name:
                couple_names[start_number] = competitor_name
        
        return couple_names
        
    except Exception as e:
        print(f"Error scraping couple names from {rez_url}: {e}")
        return {}

def scrape_wrrc_results_slow_fast(url):
    """
    Scrape WRRC competition results from slow/fast format pages.
    Returns two dictionaries: one for slow rounds, one for fast rounds.
    """
    response = requests.get(url)
    response.raise_for_status()
    
    if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
        response.encoding = response.apparent_encoding or 'utf-8'

    soup = BeautifulSoup(response.text, "html.parser")
    
    tables = soup.find_all('table')
    
    if url.endswith('/'):
        base_url = url
    elif '/' in url:
        base_url = url.rsplit('/', 1)[0] + '/'
    else:
        base_url = url + '/'
    
    results_slow = {
        "competition_info": {},
        "couples": []
    }
    
    results_fast = {
        "competition_info": {},
        "couples": []
    }
    
    competition_info = get_competition_info(base_url)
    results_slow["competition_info"]["location"] = competition_info.get("location")
    results_slow["competition_info"]["date"] = competition_info.get("date")
    results_fast["competition_info"]["location"] = competition_info.get("location")
    results_fast["competition_info"]["date"] = competition_info.get("date")
    
    title_elem = soup.find('strong') or soup.find('h1') or soup.find('h2')
    if title_elem:
        title_text = title_elem.get_text(strip=True)
        results_slow["competition_info"]["title"] = title_text
        results_fast["competition_info"]["title"] = title_text
        
        if '>>' in title_text:
            parts = title_text.split('>>')
            if len(parts) == 2:
                round_name = parts[0].strip()
                dance_class_part = parts[1].strip()
                
                if '-' in dance_class_part:
                    dance_class_split = dance_class_part.rsplit('-', 1)
                    if len(dance_class_split) == 2:
                        dance = dance_class_split[0].strip()
                        class_name = dance_class_split[1].strip()
                        
                        results_slow["competition_info"]["round"] = round_name
                        results_slow["competition_info"]["dance"] = dance
                        results_slow["competition_info"]["class"] = class_name
                        results_fast["competition_info"]["round"] = round_name
                        results_fast["competition_info"]["dance"] = dance
                        results_fast["competition_info"]["class"] = class_name
    
    main_table = None
    for table in tables:
        headers = table.find_all(['th', 'td'])
        header_texts = [h.get_text(strip=True) for h in headers[:10]]
        if 'Stn.' in header_texts or 'Position' in header_texts:
            main_table = table
            break
    
    if not main_table:
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > 5:
                main_table = table
                break
    
    if not main_table:
        return {"error": "Could not find results table"}, {"error": "Could not find results table"}
    
    header_row = main_table.find('tr')
    has_type_column = False
    type_column_idx = -1
    
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        for idx, header in enumerate(headers):
            if header.strip().lower() == 'type':
                has_type_column = True
                type_column_idx = idx
                break
        
        for header in headers:
            if '>>' in header:
                parts = header.split('>>')
                if len(parts) == 2:
                    round_name = parts[0].strip()
                    dance_class_part = parts[1].strip()
                    
                    if '-' in dance_class_part:
                        dance_class_split = dance_class_part.rsplit('-', 1)
                        if len(dance_class_split) == 2:
                            dance = dance_class_split[0].strip()
                            class_name = dance_class_split[1].strip()
                            
                            results_slow["competition_info"]["round"] = round_name
                            results_slow["competition_info"]["dance"] = dance
                            results_slow["competition_info"]["class"] = class_name
                            results_fast["competition_info"]["round"] = round_name
                            results_fast["competition_info"]["dance"] = dance
                            results_fast["competition_info"]["class"] = class_name
    
    if results_slow["competition_info"].get("dance") and results_slow["competition_info"].get("class"):
        dance = results_slow["competition_info"]["dance"]
        class_name = results_slow["competition_info"]["class"]
        judges = get_judges_for_category(base_url, dance, class_name)
        results_slow["competition_info"]["judges"] = judges
        results_fast["competition_info"]["judges"] = judges
    
    category_map = {
        'BBW': 'Boogie Woogie Basics - Woman',
        'BBM': 'Boogie Woogie Basics - Man',
        'LF': 'Lead and follow, basic dancing, harmony, dance performance',
        'DF': 'Dance Figures (how do they present)',
        'MI': 'Music Interpretation (what do they present)'
    }
    
    data_rows = main_table.find_all('tr')[1:] if header_row else main_table.find_all('tr')
    
    # Debug: print table structure info
    #print(f"  Debug: Found {len(data_rows)} data rows")
    #print(f"  Debug: has_type_column = {has_type_column}")
    
    current_start_number = None
    current_position = None
    current_teor = None
    current_total = None
    
    for row_idx, row in enumerate(data_rows):
        cells = row.find_all(['td', 'th'])
        #if len(cells) < 7:
        #    if row_idx < 3:  # Debug first few skipped rows
        #        print(f"  Debug: Row {row_idx} skipped - only {len(cells)} cells")
        #    continue
        
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        
        # Check if this row contains "Slow:" or "Fast:" - this indicates slow/fast format
        # even if the header doesn't have "Type" column
        type_value = None
        type_cell_idx = -1
        for idx, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            if cell_text == "Slow:" or cell_text == "Fast:":
                type_value = cell_text
                type_cell_idx = idx
                # If we found Slow/Fast, this is definitely a slow/fast format table
                if not has_type_column:
                    has_type_column = True
                break
        
        #if row_idx < 3:  # Debug first few rows
        #    print(f"  Debug: Row {row_idx}: {len(cells)} cells, type_value={type_value}, first few cells: {cell_texts[:5]}")
        
        if type_value == "Slow:":
            rowspan_cells = []
            for cell in cells:
                rowspan_attr = cell.get('rowspan')
                if rowspan_attr == '2' or rowspan_attr == 2:
                    rowspan_cells.append(cell)
            
            if len(rowspan_cells) >= 3:
                current_start_number = rowspan_cells[0].get_text(strip=True)
                current_position = rowspan_cells[1].get_text(strip=True)
                current_teor = rowspan_cells[2].get_text(strip=True)
                
                if len(rowspan_cells) >= 4:
                    current_total = rowspan_cells[-1].get_text(strip=True)
            
            # Process slow round data
            couple_data = {
                "start_number": current_start_number,
                "position": current_position,
                "teor": current_teor,
                "categories": {},
                "observer": None,
                "sum": None,
                "total": current_total
            }
            
            # For Slow row, cells include rowspan cells: Stn, Position, Teor, Type, BBW, BBM, LF, DF, MI, Obs, Sum, Total
            # Find Type column index first
            type_idx = -1
            for idx, cell in enumerate(cells):
                if cell.get_text(strip=True) == "Slow:":
                    type_idx = idx
                    break
            
            if type_idx == -1:
                print(f"  Warning: Could not find 'Slow:' in row {row_idx}, skipping")
                continue
            
            category_names = ['BBW', 'BBM', 'LF', 'DF', 'MI']
            category_start_idx = type_idx + 1  # After Type column
            
            for i, category in enumerate(category_names):
                cell_idx = category_start_idx + i
                if cell_idx < len(cells):
                    score_cell = cells[cell_idx]
                    parsed_score = parse_score_cell(score_cell)
                    couple_data["categories"][category] = {
                        "name": category_map.get(category, category),
                        "aggregated": parsed_score["aggregated"],
                        "judge_scores": parsed_score["judge_scores"]
                    }
            
            # Obs is after 5 categories, Sum is before Total (last rowspan cell)
            obs_idx = category_start_idx + 5
            sum_idx = -2  # Second to last (last is Total rowspan cell)
            if obs_idx < len(cell_texts):
                couple_data["observer"] = cell_texts[obs_idx] if len(cell_texts) > obs_idx else None
            if len(cell_texts) >= 2:
                couple_data["sum"] = cell_texts[sum_idx] if abs(sum_idx) <= len(cell_texts) else None
            
            # Validate and add couple data
            if couple_data["start_number"]:
                # Try to clean start_number - remove any non-digit characters
                start_num_clean = ''.join(c for c in couple_data["start_number"] if c.isdigit())
                if start_num_clean:
                    couple_data["start_number"] = start_num_clean
                    results_slow["couples"].append(couple_data)
                else:
                    print(f"  Warning: Invalid start_number '{couple_data['start_number']}' in slow row {row_idx}")
            else:
                print(f"  Warning: No start_number found in slow row {row_idx}")
        
        elif type_value == "Fast:":
            # Process fast round data
            couple_data = {
                "start_number": current_start_number,
                "position": current_position,
                "teor": current_teor,
                "categories": {},
                "observer": None,
                "sum": None,
                "total": current_total
            }
            
            if len(cells) == 0 or cells[0].get_text(strip=True) != "Fast:":
                continue
            
            # For Fast row, rowspan cells are NOT included, so: Type, BBW, BBM, LF, DF, MI, Obs, Sum
            category_names = ['BBW', 'BBM', 'LF', 'DF', 'MI']
            category_start_idx = 1  # After Type column (index 0)
            
            for i, category in enumerate(category_names):
                cell_idx = category_start_idx + i
                if cell_idx < len(cells):
                    score_cell = cells[cell_idx]
                    parsed_score = parse_score_cell(score_cell)
                    couple_data["categories"][category] = {
                        "name": category_map.get(category, category),
                        "aggregated": parsed_score["aggregated"],
                        "judge_scores": parsed_score["judge_scores"]
                    }
            
            # Obs is after 5 categories, Sum is the last cell
            obs_idx = category_start_idx + 5
            if obs_idx < len(cell_texts):
                couple_data["observer"] = cell_texts[obs_idx] if len(cell_texts) > obs_idx else None
            couple_data["sum"] = cell_texts[-1] if len(cell_texts) >= 1 else None
            
            # Validate and add couple data
            if couple_data["start_number"]:
                # Try to clean start_number - remove any non-digit characters
                start_num_clean = ''.join(c for c in couple_data["start_number"] if c.isdigit())
                if start_num_clean:
                    couple_data["start_number"] = start_num_clean
                    results_fast["couples"].append(couple_data)
                else:
                    print(f"  Warning: Invalid start_number '{couple_data['start_number']}' in fast row {row_idx}")
            else:
                print(f"  Warning: No start_number found in fast row {row_idx} (current_start_number={current_start_number})")
        else:
            # Row doesn't have Slow: or Fast: - skip it
            if row_idx < 3:
                print(f"  Debug: Row {row_idx} skipped - no Slow: or Fast: found")
    
    # Get couple names
    url_filename = url.split('/')[-1]
    if url_filename.startswith('ocj_'):
        rez_filename = url_filename.replace('ocj_', 'rez_', 1)
        couple_names = scrape_couple_names(base_url, rez_filename)
        
        for couple in results_slow["couples"]:
            start_num = couple.get("start_number")
            if start_num and start_num in couple_names:
                couple["competitor_names"] = couple_names[start_num]
        
        for couple in results_fast["couples"]:
            start_num = couple.get("start_number")
            if start_num and start_num in couple_names:
                couple["competitor_names"] = couple_names[start_num]
    
    return results_slow, results_fast

def process_single_url(url, results_dir="results"):
    """
    Process a single URL and save slow and fast results to separate JSON files.
    """
    try:
        print(f"\nScraping WRRC results from: {url}")
        results_slow, results_fast = scrape_wrrc_results_slow_fast(url)
        
        if "error" in results_slow:
            error_msg = results_slow["error"]
            print(f"  Error: {error_msg}")
            return False, None, None, error_msg
        
        comp_info_slow = results_slow.get("competition_info", {})
        comp_info_fast = results_fast.get("competition_info", {})
        
        location = sanitize_filename(comp_info_slow.get("location", "Unknown"), use_hyphens=True)
        date = format_date_for_filename(comp_info_slow.get("date", "Unknown"))
        class_name = sanitize_filename(comp_info_slow.get("class", "Unknown"), use_hyphens=True)
        round_name = sanitize_filename(comp_info_slow.get("round", "Unknown"), use_hyphens=True)
        
        output_filename_slow = f"results_{location}_{date}_{class_name}_{round_name}_Slow.json"
        output_filename_fast = f"results_{location}_{date}_{class_name}_{round_name}_Fast.json"
        
        os.makedirs(results_dir, exist_ok=True)
        
        output_file_slow = os.path.join(results_dir, output_filename_slow)
        output_file_fast = os.path.join(results_dir, output_filename_fast)
        
        with open(output_file_slow, 'w', encoding='utf-8') as f:
            json.dump(results_slow, f, indent=2, ensure_ascii=False)
        
        with open(output_file_fast, 'w', encoding='utf-8') as f:
            json.dump(results_fast, f, indent=2, ensure_ascii=False)
        
        num_couples_slow = len(results_slow.get("couples", []))
        num_couples_fast = len(results_fast.get("couples", []))
        print(f"  ✓ Successfully scraped {num_couples_slow} couples (slow) and {num_couples_fast} couples (fast)")
        print(f"  ✓ Saved slow to: {output_file_slow}")
        print(f"  ✓ Saved fast to: {output_file_fast}")
        
        return True, output_file_slow, output_file_fast, None
        
    except Exception as e:
        error_msg = f"Error processing URL: {str(e)}"
        print(f"  ✗ {error_msg}")
        return False, None, None, error_msg

def load_urls_from_file(filename):
    """Load URLs from a text file (one URL per line)."""
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
    except FileNotFoundError:
        print(f"File {filename} not found.")
    except Exception as e:
        print(f"Error reading file {filename}: {e}")
    
    return urls

def main():
    """Main function to scrape slow/fast rounds."""
    if len(sys.argv) > 1:
        # If URL provided as command line argument
        url = sys.argv[1]
        process_single_url(url)
    else:
        # Try to load from default file
        urls_file = "urls_openmarkings_ff"
        print(f"Loading URLs from: {urls_file}")
        urls = load_urls_from_file(urls_file)
        
        if not urls:
            print("No URLs found. Usage: python scrape_ff.py <URL>")
            print("Or create a file 'urls_openmarkings_ff' with one URL per line.")
            return
        
        print(f"Found {len(urls)} URL(s) to process.\n")
        
        successful = 0
        failed = 0
        output_files_slow = []
        output_files_fast = []
        
        for idx, url in enumerate(urls, 1):
            print(f"\n[{idx}/{len(urls)}] Processing URL...")
            success, output_file_slow, output_file_fast, error = process_single_url(url)
            
            if success:
                successful += 1
                if output_file_slow:
                    output_files_slow.append(output_file_slow)
                if output_file_fast:
                    output_files_fast.append(output_file_fast)
            else:
                failed += 1
        
        print("\n" + "=" * 60)
        print("SCRAPING SUMMARY")
        print("=" * 60)
        print(f"Total URLs processed: {len(urls)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"\nResults saved to 'results' directory:")
        print("\nSlow rounds:")
        for output_file in output_files_slow:
            print(f"  - {output_file}")
        print("\nFast rounds:")
        for output_file in output_files_fast:
            print(f"  - {output_file}")

if __name__ == "__main__":
    main()
