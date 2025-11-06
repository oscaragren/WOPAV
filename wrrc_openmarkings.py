# Python script for scraping and structuring WRRC competition results

import requests
from bs4 import BeautifulSoup
import json
import os
import re

def sanitize_filename(text, use_hyphens=True):
    """
    Sanitize text for use in a filename by replacing spaces with hyphens
    and removing invalid filename characters while preserving Unicode characters.
    
    Args:
        text: String to sanitize
        use_hyphens: If True, replace spaces with hyphens; if False, use underscores
    
    Returns:
        Sanitized string safe for use in filenames
    """
    if not text:
        return "Unknown"
    
    # Replace spaces with hyphens (for words within the same field)
    # or underscores (for field separation)
    if use_hyphens:
        text = text.replace(' ', '-')
    else:
        text = text.replace(' ', '_')
    
    # Replace common separators with hyphens
    text = text.replace('/', '-').replace('\\', '-')
    
    # Remove invalid filename characters (Windows and Unix)
    # Characters that are problematic in filenames: < > : " | ? * \ / 
    text = re.sub(r'[<>:"|?*\\/]', '', text)
    
    # Remove any control characters and other problematic characters
    # But preserve Unicode letters, numbers, underscores, hyphens
    # \w in Python 3 includes Unicode word characters (letters, digits, underscore)
    text = re.sub(r'[^\w\-]', '', text)
    
    # Remove multiple consecutive hyphens/underscores (normalize to single)
    text = re.sub(r'[-]+', '-', text)
    text = re.sub(r'[_]+', '_', text)
    
    # Remove leading/trailing hyphens and underscores
    text = text.strip('_-')
    
    # Limit length to avoid filesystem issues
    if len(text) > 100:  # Reasonable limit for each field
        text = text[:100]
    
    return text if text else "Unknown"

def format_date_for_filename(date_str):
    """
    Format a date string (e.g., "23.08.2025") to filename format (e.g., "23-08-25").
    
    Args:
        date_str: Date string in format like "23.08.2025" or "DD.MM.YYYY"
    
    Returns:
        Formatted date string like "23-08-25"
    """
    if not date_str:
        return "Unknown"
    
    # Try to match DD.MM.YYYY or DD-MM-YYYY format
    # Match patterns like "23.08.2025" or "23-08-2025" or "23/08/2025"
    date_match = re.match(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})', date_str)
    if date_match:
        day, month, year = date_match.groups()
        # Pad day and month to 2 digits if needed
        day = day.zfill(2)
        month = month.zfill(2)
        # Use last 2 digits of year
        year_short = year[-2:]
        return f"{day}-{month}-{year_short}"
    
    # Try to match DD.MM.YY format (already short year)
    date_match = re.match(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2})', date_str)
    if date_match:
        day, month, year = date_match.groups()
        day = day.zfill(2)
        month = month.zfill(2)
        return f"{day}-{month}-{year}"
    
    # If format doesn't match expected patterns, just sanitize
    return sanitize_filename(date_str, use_hyphens=True)

def parse_score_cell(cell):
    """
    Parse a score cell that contains:
    - First line: aggregated score (e.g., "5,46")
    - Second line: pipe-separated judge scores (e.g., "3,75|5,25|5,25|6,75|6|5,25|6,75")
    
    This function handles an arbitrary number of judges - it will parse all pipe-separated
    scores from the second line, regardless of how many judges there are.
    
    Returns a dict with 'aggregated' score and 'judge_scores' list (which can contain
    any number of scores)
    """
    if not cell:
        return {"aggregated": None, "judge_scores": []}
    
    # Get text from cell, handling <br> tags which BeautifulSoup converts to newlines
    # Use get_text with separator to preserve line breaks
    cell_text = cell.get_text(separator='\n', strip=True)
    
    if not cell_text or not cell_text.strip():
        return {"aggregated": None, "judge_scores": []}
    
    # Split by newline to separate aggregated score from judge scores
    lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
    
    # First line is the aggregated score
    aggregated = lines[0] if lines else None
    if aggregated:
        # Keep comma as decimal separator (European format) - don't convert to dot
        aggregated = aggregated.strip()
    
    # Second line contains pipe-separated judge scores
    # This can contain any number of judge scores - we parse all of them dynamically
    judge_scores = []
    if len(lines) > 1:
        judge_scores_str = lines[1]
        # Split by pipe to get all individual judge scores (handles any number of judges)
        judge_score_parts = judge_scores_str.split('|')
        for score in judge_score_parts:
            score = score.strip()
            if score:
                # Keep comma as decimal separator (European format)
                judge_scores.append(score)
    
    return {
        "aggregated": aggregated,
        "judge_scores": judge_scores  # List can contain any number of scores
    }

def get_judges_for_category(base_url, dance, class_name):
    """
    Retrieve judges for a specific dance and class from the turnir_naslov.htm page.
    
    Args:
        base_url: Base URL of the competition
        dance: Dance name (e.g., "Boogie Woogie")
        class_name: Class name (e.g., "Main Class", "Juniors", "Senior")
    
    Returns:
        list: List of dictionaries with judge information (letter and name) for the specified category
    """
    if not base_url.endswith('/'):
        base_url += '/'
    
    turnir_url = base_url + 'turnir_naslov.htm'
    
    try:
        response = requests.get(turnir_url)
        response.raise_for_status()
        
        # Ensure proper encoding handling for special characters
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find the judges table
        tables = soup.find_all('table', class_='tur_main')
        judges_table = None
        for table in tables:
            # Look for table with "Judges" header
            header_cells = table.find_all('td', class_='tur_labela')
            for cell in header_cells:
                if 'Judges' in cell.get_text(strip=True):
                    judges_table = table
                    break
            if judges_table:
                break
        
        if not judges_table:
            return []
        
        # Build the category string to match (e.g., "Boogie Woogie-Main Class")
        category_to_match = f"{dance}-{class_name}"
        
        # Parse judges from the table
        judges = []
        current_judge = None
        current_categories = []
        
        rows = judges_table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            
            # Check if this is a judge letter row (class="tur_slovo")
            judge_letter_cell = None
            for cell in cells:
                if 'tur_slovo' in cell.get('class', []):
                    judge_letter_cell = cell
                    break
            
            if judge_letter_cell:
                # Save previous judge if they judge this category
                if current_judge and any(category_to_match in cat for cat in current_categories):
                    judges.append({
                        "letter": current_judge["letter"],
                        "name": current_judge["name"],
                        "country": current_judge.get("country")
                    })
                
                # Start new judge
                judge_letter = judge_letter_cell.get_text(strip=True)
                judge_name = None
                judge_country = None
                
                # Find judge name in the same row (class="tur_polje")
                for cell in cells:
                    if 'tur_polje' in cell.get('class', []):
                        judge_name_raw = cell.get_text(strip=True)
                        # Format: "Lastname Firstname / Country" -> "Firstname Lastname"
                        if judge_name_raw:
                            # Split by "/" to separate name and country
                            name_parts = judge_name_raw.split('/', 1)
                            name = name_parts[0].strip()
                            judge_country = name_parts[1].strip() if len(name_parts) > 1 else None
                            
                            # Split name by spaces and reverse (assumes "Lastname Firstname")
                            name_components = name.split()
                            if len(name_components) >= 2:
                                # Reverse: take first component as lastname, rest as firstname(s)
                                lastname = name_components[0]
                                firstname = ' '.join(name_components[1:])
                                judge_name = f"{firstname} {lastname}"
                            else:
                                # If only one part, keep as is
                                judge_name = name
                        break
                
                current_judge = {
                    "letter": judge_letter,
                    "name": judge_name,
                    "country": judge_country
                }
                current_categories = []
            
            # Check if this is a category row (class="tur_kategorija")
            for cell in cells:
                if 'tur_kategorija' in cell.get('class', []):
                    category = cell.get_text(strip=True)
                    if category:
                        current_categories.append(category)
        
        # Don't forget the last judge
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

def get_competition_info(base_url):
    """
    Retrieve the location and date of the competition from the WRRC results page.
    
    Args:
        base_url: Base URL of the competition (e.g., "https://www.wrrc.org/results/2025-3459/")
    
    Returns:
        dict: Dictionary containing 'location' and 'date', or None if not found
    """
    # Ensure URL ends with a slash for proper path construction
    if not base_url.endswith('/'):
        base_url += '/'
    
    # The location and date are in naslov.htm file
    naslov_url = base_url + 'naslov.htm'
    
    try:
        response = requests.get(naslov_url)
        response.raise_for_status()
        
        # Ensure proper encoding handling for special characters
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find the cell with class 'tur_main_naslov' which contains the competition info
        title_cell = soup.find('td', class_='tur_main_naslov')
        
        if not title_cell:
            return {"location": None, "date": None}
        
        # Get all text, preserving line breaks
        text = title_cell.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return {"location": None, "date": None}
        
        # First line contains the competition name and location
        # Format is typically: "World cup Boogie Woogie Main Class - Stuttgart"
        first_line = lines[0]
        
        # Extract location (usually after the last dash)
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
        
        # Second line contains the date
        # Format is typically: "23.08.2025"
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

def scrape_couple_names(base_url, rez_filename):
    """
    Scrape couple names from the results page (rez_*.htm) and return a dictionary
    mapping start numbers to competitor names.
    
    Args:
        base_url: Base URL of the competition
        rez_filename: Filename of the results page (e.g., "rez_2010.htm")
    
    Returns:
        dict: Dictionary mapping start_number (as string) to competitor names (as string)
    """
    if not base_url.endswith('/'):
        base_url += '/'
    
    rez_url = base_url + rez_filename
    
    try:
        response = requests.get(rez_url)
        response.raise_for_status()
        
        # Ensure proper encoding handling for special characters
        if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
            response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find the results table
        results_table = soup.find('table', class_='entrylist_table')
        if not results_table:
            return {}
        
        # Dictionary to store start_number -> competitor names
        couple_names = {}
        
        # Find all data rows (skip header row)
        rows = results_table.find_all('tr')[1:]  # Skip first row (header)
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            # The structure is: Pos, Stn, Competitor, Country (img), Country (text), Result, Qual, Cards
            # Start number is in the second cell (index 1)
            # Competitor name is in the cell with class "competitor" or "competitor_out"
            start_number = None
            competitor_name = None
            
            # Start number is typically in the second cell (index 1)
            if len(cells) > 1:
                start_number_cell = cells[1]
                start_number_text = start_number_cell.get_text(strip=True)
                if start_number_text.isdigit():
                    start_number = start_number_text
            
            # Look for competitor name in any cell with class "competitor"
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                cell_class = cell.get('class', [])
                cell_class_str = ' '.join(cell_class) if isinstance(cell_class, list) else str(cell_class)
                
                # Look for competitor name - cell with class "competitor" or "competitor_out"
                if 'competitor' in cell_class_str:
                    competitor_name = cell_text
                    # Format is typically "LASTNAME Firstname - LASTNAME Firstname"
                    # Transform to "Firstname Lastname & Firstname Lastname"
                    if ' - ' in competitor_name:
                        parts = competitor_name.split(' - ')
                        formatted_parts = []
                        for part in parts:
                            part = part.strip()
                            # Split name by spaces and reverse (assumes "Lastname Firstname")
                            name_components = part.split()
                            if len(name_components) >= 2:
                                # Reverse: take first component as lastname, rest as firstname(s)
                                lastname = name_components[0]
                                firstname = ' '.join(name_components[1:])
                                formatted_name = f"{firstname} {lastname}"
                            else:
                                # If only one part, keep as is
                                formatted_name = part
                            formatted_parts.append(formatted_name)
                        competitor_name = " & ".join(formatted_parts)
                    break
            
            # If we found both, store the mapping
            if start_number and competitor_name:
                couple_names[start_number] = competitor_name
        
        return couple_names
        
    except Exception as e:
        print(f"Error scraping couple names from {rez_url}: {e}")
        return {}

def scrape_wrrc_results(url):
    """
    Scrape WRRC competition results from the given URL
    Returns structured data as a dictionary
    """
    response = requests.get(url)
    response.raise_for_status()
    
    # Ensure proper encoding handling for special characters
    if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
        response.encoding = response.apparent_encoding or 'utf-8'

    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find the main results table
    # The table structure may vary, so let's look for tables with relevant headers
    tables = soup.find_all('table')
    
    # Extract base URL for getting competition info
    # If URL contains a filename (like .htm), extract the directory path
    # Otherwise use the URL as-is if it ends with /
    if url.endswith('/'):
        base_url = url
    elif '/' in url:
        # If URL has a filename, get the directory
        base_url = url.rsplit('/', 1)[0] + '/'
    else:
        base_url = url + '/'
    
    results = {
        "competition_info": {},
        "couples": []
    }
    
    # Get competition location and date
    competition_info = get_competition_info(base_url)
    results["competition_info"]["location"] = competition_info.get("location")
    results["competition_info"]["date"] = competition_info.get("date")
    
    # Try to find competition title/header
    title_elem = soup.find('strong') or soup.find('h1') or soup.find('h2')
    if title_elem:
        title_text = title_elem.get_text(strip=True)
        results["competition_info"]["title"] = title_text
        
        # Also try to extract round/dance/class from title if not found in columns
        if 'round' not in results["competition_info"] and '>>' in title_text:
            parts = title_text.split('>>')
            if len(parts) == 2:
                round_name = parts[0].strip()
                dance_class_part = parts[1].strip()
                
                if '-' in dance_class_part:
                    dance_class_split = dance_class_part.rsplit('-', 1)
                    if len(dance_class_split) == 2:
                        dance = dance_class_split[0].strip()
                        class_name = dance_class_split[1].strip()
                        
                        results["competition_info"]["round"] = round_name
                        results["competition_info"]["dance"] = dance
                        results["competition_info"]["class"] = class_name
                        # No class specified, just round and dance
                        results["competition_info"]["round"] = round_name
                        results["competition_info"]["dance"] = dance_class_part
    
    # Find the main results table
    main_table = None
    for table in tables:
        headers = table.find_all(['th', 'td'])
        header_texts = [h.get_text(strip=True) for h in headers[:10]]  # Check first few headers
        if 'Stn.' in header_texts or 'Position' in header_texts:
            main_table = table
            break
    
    if not main_table:
        # Fallback: try to find any table with multiple rows
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) > 5:  # Likely the main table if it has many rows
                main_table = table
                break
    
    if not main_table:
        return {"error": "Could not find results table"}
    
    # Extract header row to understand column structure
    header_row = main_table.find('tr')
    has_type_column = False
    type_column_idx = -1
    
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        # Check if there's a "Type" column (indicates slow/fast format)
        for idx, header in enumerate(headers):
            if header.strip().lower() == 'type':
                has_type_column = True
                type_column_idx = idx
                break
        
        # Look for round/dance/class information in the headers
        # Format is typically: "Round>>Dance-Class" (e.g., "Semi Final>>Boogie Woogie-Main Class")
        for header in headers:
            if '>>' in header:
                # Parse the format: "Round>>Dance-Class"
                parts = header.split('>>')
                if len(parts) == 2:
                    round_name = parts[0].strip()
                    dance_class_part = parts[1].strip()
                    
                    # Split dance and class (separated by dash)
                    # Format: "Boogie Woogie-Main Class"
                    if '-' in dance_class_part:
                        dance_class_split = dance_class_part.rsplit('-', 1)
                        if len(dance_class_split) == 2:
                            dance = dance_class_split[0].strip()
                            class_name = dance_class_split[1].strip()
                            
                            results["competition_info"]["round"] = round_name
                            results["competition_info"]["dance"] = dance
                            results["competition_info"]["class"] = class_name
                    else:
                        # No class specified, just round and dance
                        results["competition_info"]["round"] = round_name
                        results["competition_info"]["dance"] = dance_class_part
    
    # Extract data rows (skip header row)
    data_rows = main_table.find_all('tr')[1:] if header_row else main_table.find_all('tr')
    
    # Get judges for the specific dance and class if we have that information
    # (This should happen after both title parsing and header parsing are done)
    if results["competition_info"].get("dance") and results["competition_info"].get("class"):
        dance = results["competition_info"]["dance"]
        class_name = results["competition_info"]["class"]
        judges = get_judges_for_category(base_url, dance, class_name)
        results["competition_info"]["judges"] = judges
    elif results["competition_info"].get("dance"):
        # If we only have dance but no class, try to get judges anyway
        dance = results["competition_info"]["dance"]
        judges = get_judges_for_category(base_url, dance, "")
        if judges:
            results["competition_info"]["judges"] = judges
    
    # Category mappings
    category_map = {
        'BBW': 'Boogie Woogie Basics - Woman',
        'BBM': 'Boogie Woogie Basics - Man',
        'LF': 'Lead and follow, basic dancing, harmony, dance performance',
        'DF': 'Dance Figures (how do they present)',
        'MI': 'Music Interpretation (what do they present)'
    }
    
    # Variables to track slow/fast format rowspan values
    current_start_number = None
    current_position = None
    current_teor = None
    current_total = None
    
    for row in data_rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 7:  # Skip rows that don't have enough columns
            continue
        
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        
        # Check if this is a slow/fast format page
        if has_type_column:
            # Find Type column by checking cell text
            type_value = None
            type_cell_idx = -1
            for idx, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                if cell_text == "Slow:" or cell_text == "Fast:":
                    type_value = cell_text
                    type_cell_idx = idx
                    break
            
            # If it's a slow round row, extract the shared values (rowspan="2" columns)
            if type_value == "Slow:":
                # Store the rowspan values for the fast round row
                # First cell with rowspan="2" is start_number
                # Second cell with rowspan="2" is position
                # Third cell with rowspan="2" is teor
                # Last cell with rowspan="2" is total
                rowspan_cells = []
                for cell in cells:
                    rowspan_attr = cell.get('rowspan')
                    if rowspan_attr == '2' or rowspan_attr == 2:
                        rowspan_cells.append(cell)
                
                if len(rowspan_cells) >= 3:
                    # Start number, position, teor are first 3 rowspan cells
                    current_start_number = rowspan_cells[0].get_text(strip=True)
                    current_position = rowspan_cells[1].get_text(strip=True)
                    current_teor = rowspan_cells[2].get_text(strip=True)
                    
                    # Total is the last rowspan cell
                    if len(rowspan_cells) >= 4:
                        current_total = rowspan_cells[-1].get_text(strip=True)
                continue  # Skip slow round rows, only process fast round
            
            # Only process fast round rows; skip if type_value is None or not "Fast:"
            if type_value != "Fast:":
                continue
            
            # For fast rows, Type cell should always be at index 0 (rowspan cells not in list)
            # If it's not at index 0, something is wrong - skip this row
            if type_cell_idx != 0:
                continue
        else:
            type_cell_idx = -1  # Not relevant for non-slow/fast format
        
        # Extract couple information
        couple_data = {
            "start_number": None,
            "position": None,
            "teor": None,
            "categories": {},
            "observer": None,
            "sum": None,
            "total": None
        }
        
        # For slow/fast format, use the stored rowspan values
        if has_type_column:
            couple_data["start_number"] = current_start_number
            couple_data["position"] = current_position
            couple_data["teor"] = current_teor
            couple_data["total"] = current_total
            
            # Explicitly verify first cell is "Fast:" for fast rows
            # This ensures we're processing the correct row structure
            if len(cells) == 0 or cells[0].get_text(strip=True) != "Fast:":
                continue  # Skip this row if first cell is not "Fast:"
            
            # Category scores start after Type column (index 0)
            # Categories are at indices 1 (BBW), 2 (BBM), 3 (LF), 4 (DF), 5 (MI)
            category_start_idx = 1
        else:
            # Standard format: Stn, Position, Teor, BBW, BBM, LF, DF, MI, Obs, Sum, Total
            couple_data["start_number"] = cell_texts[0] if len(cell_texts) > 0 else None
            couple_data["position"] = cell_texts[1] if len(cell_texts) > 1 else None
            couple_data["teor"] = cell_texts[2] if len(cell_texts) > 2 else None
            category_start_idx = 3
        
        # Extract category scores (BBW, BBM, LF, DF, MI)
        category_names = ['BBW', 'BBM', 'LF', 'DF', 'MI']
        
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
        
        # Extract observer (Obs.), Sum, and Total
        if has_type_column:
            # For slow/fast format: Type column, then categories, then Obs, Sum
            # Total is stored from rowspan in the slow row
            # Observer is after categories (5 categories), Sum is the last cell
            obs_idx = category_start_idx + 5  # After 5 categories
            if obs_idx < len(cell_texts):
                couple_data["observer"] = cell_texts[obs_idx] if len(cell_texts) > obs_idx else None
            couple_data["sum"] = cell_texts[-1] if len(cell_texts) >= 1 else None  # Last cell (Total is from rowspan)
        else:
            # Standard format
            if len(cells) >= 9:  # Stn, Pos, Teor, BBW, BBM, LF, DF, MI, Obs, Sum, Total
                couple_data["observer"] = cell_texts[8] if len(cell_texts) > 8 else None
                couple_data["sum"] = cell_texts[-2] if len(cell_texts) >= 2 else None
                couple_data["total"] = cell_texts[-1] if len(cell_texts) >= 1 else None
            elif len(cells) >= 2:
                couple_data["sum"] = cell_texts[-2] if len(cell_texts) >= 2 else None
                couple_data["total"] = cell_texts[-1] if len(cell_texts) >= 1 else None
        
        # Only add couples with valid start_number numbers
        if couple_data["start_number"] and couple_data["start_number"].isdigit():
            results["couples"].append(couple_data)
    
    # Try to get couple names from the results page (rez_*.htm)
    # Extract the filename from the URL and convert ocj_*.htm to rez_*.htm
    url_filename = url.split('/')[-1]  # Get filename from URL
    if url_filename.startswith('ocj_'):
        rez_filename = url_filename.replace('ocj_', 'rez_', 1)
        couple_names = scrape_couple_names(base_url, rez_filename)
        
        # Match names to couples by start_number
        for couple in results["couples"]:
            start_num = couple.get("start_number")
            if start_num and start_num in couple_names:
                couple["competitor_names"] = couple_names[start_num]
    
    return results

def check_competition_exists(base_url):
    """Check if a competition base URL exists."""
    if not base_url.endswith('/'):
        base_url += '/'
    try:
        response = requests.get(base_url + 'naslov.htm', timeout=5)
        return response.status_code == 200
    except:
        return False

def discover_rounds_smart(year, comp_id):
    """Discover rounds for a competition by trying round IDs."""
    base_url = f"https://www.wrrc.org/results/{year}-{comp_id}/"
    rounds = []
    for round_id in range(1000, 10000):
        round_url = f"{base_url}ocj_{round_id}.htm"
        try:
            response = requests.get(round_url, timeout=3)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.find('table') and ('Position' in response.text or 'Stn.' in response.text):
                    rounds.append(round_url)
        except:
            pass
    return rounds

def matches_filters(round_url, dance_filter=None, class_filter=None, round_filter=None):
    """Check if a round matches filters."""
    try:
        results = scrape_wrrc_results(round_url)
        comp_info = results.get("competition_info", {})
        dance = comp_info.get("dance", "").lower()
        class_name = comp_info.get("class", "").lower()
        round_name = comp_info.get("round", "").lower()
        if dance_filter and dance_filter.lower() not in dance:
            return None
        if class_filter and class_filter.lower() not in class_name:
            return None
        if round_filter and round_filter.lower() not in round_name:
            return None
        return {"url": round_url, "competition_info": comp_info, "num_couples": len(results.get("couples", []))}
    except:
        return None

def process_single_url(url, results_dir="results"):
    """
    Process a single URL and save the results to a JSON file.
    
    Args:
        url: URL to scrape
        results_dir: Directory to save results (default: "results")
    
    Returns:
        tuple: (success: bool, output_file: str or None, error_message: str or None)
    """
    try:
        print(f"\nScraping WRRC results from: {url}")
        results = scrape_wrrc_results(url)
        
        # Check if there's an error in results
        if "error" in results:
            error_msg = results["error"]
            print(f"  Error: {error_msg}")
            return False, None, error_msg
        
        # Save to JSON file with descriptive filename
        comp_info = results.get("competition_info", {})
        
        # Extract values for filename (with fallbacks)
        # Use hyphens within each field (for multi-word values)
        location = sanitize_filename(comp_info.get("location", "Unknown"), use_hyphens=True)
        date = format_date_for_filename(comp_info.get("date", "Unknown"))
        class_name = sanitize_filename(comp_info.get("class", "Unknown"), use_hyphens=True)
        round_name = sanitize_filename(comp_info.get("round", "Unknown"), use_hyphens=True)
        
        # Generate filename: results_LOCATION_DATE_CLASS_ROUND.json
        # Using underscores to separate different categories
        output_filename = f"results_{location}_{date}_{class_name}_{round_name}.json"
        
        # Create results directory if it doesn't exist
        os.makedirs(results_dir, exist_ok=True)
        
        # Full path to output file
        output_file = os.path.join(results_dir, output_filename)
        
        # Save results to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        num_couples = len(results.get("couples", []))
        print(f"  ✓ Successfully scraped {num_couples} couples")
        print(f"  ✓ Saved to: {output_file}")
        
        return True, output_file, None
        
    except Exception as e:
        error_msg = str(e)
        print(f"  ✗ Error scraping results: {error_msg}")
        return False, None, error_msg

def load_urls_from_file(filename):
    """
    Load URLs from a text file (one URL per line).
    
    Args:
        filename: Path to the file containing URLs
    
    Returns:
        list: List of URLs (empty lines and whitespace-only lines are filtered out)
    """
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:  # Skip empty lines
                    urls.append(url)
        return urls
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return []
    except Exception as e:
        print(f"Error reading file '{filename}': {e}")
        return []

def main():
    # Default filename for URLs
    urls_file = "urls_openmarkings_noff_2025"
    
    # Load URLs from file
    print(f"Loading URLs from: {urls_file}")
    urls = load_urls_from_file(urls_file)
    
    if not urls:
        print("No URLs found in file. Exiting.")
        return
    
    print(f"Found {len(urls)} URL(s) to process.\n")
    
    # Process each URL
    successful = 0
    failed = 0
    output_files = []
    
    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{len(urls)}] Processing URL...")
        success, output_file, error = process_single_url(url)
        
        if success:
            successful += 1
            if output_file:
                output_files.append(output_file)
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("SCRAPING SUMMARY")
    print("=" * 60)
    print(f"Total URLs processed: {len(urls)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"\nResults saved to 'results' directory:")
    for output_file in output_files:
        print(f"  - {output_file}")

if __name__ == "__main__":
    main()
