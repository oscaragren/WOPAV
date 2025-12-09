# WOPAV - WRRC Open Markings Analyzer and Visualizer

A comprehensive tool for scraping, analyzing, and visualizing competition results from the World Rock'n'Roll Confederation (WRRC) website. WOPAV allows you to extract competition data, save it in structured JSON format, and explore it through an interactive web dashboard.

## Features

### 🔍 Data Scraping
- **Single Competition Scraper** (`wrrc_openmarkings.py`): Scrape individual competition rounds from WRRC results pages
- **Bulk Scraper** (`wrrc_bulk_scraper.py`): Discover and scrape multiple competitions based on filters:
  - Dance type (e.g., "Boogie Woogie")
  - Class (e.g., "Main Class", "Juniors", "Senior")
  - Round type (e.g., "Semi Final", "Final")
  - Year range (e.g., "2022-2025")
- Parallel processing for efficient bulk scraping
- Automatic discovery of competition IDs and round numbers

### 📊 Data Visualization
- **Interactive Dashboard** (`Main_Dashboard.py`): Streamlit-based web application with:
  - **Leaderboard Charts**: Visualize final rankings with total scores
  - **Category Comparison**: Radar charts comparing scores across 5 categories:
    - BBW (Boogie Woogie Basics - Woman)
    - BBM (Boogie Woogie Basics - Man)
    - LF (Lead and Follow)
    - DF (Dance Figures)
    - MI (Music Interpretation)
  - **Normalized Comparisons**: Percentage-based radar charts for fair category comparison
  - **Category Breakdown**: Individual category score analysis
  - **Judge Scores Analysis**: Detailed breakdown of scores from each judge
  - **Detailed Results Table**: Sortable table with all competition data
  - **Judge Information**: Display of judges and their countries

### 📁 Data Management
- Structured JSON output with competition metadata
- Automatic filename generation based on location, date, class, and round
- Organized storage in `results/` directory
- Support for multiple competitions and years

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### Setup

1. Clone or download this repository:
```bash
git clone <repository-url>
cd WOPAV
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Single Competition Scraping

Use `wrrc_openmarkings.py` to scrape a single competition round:

1. Create a text file (e.g., `urls_openmarkings_noff_2025`) with one URL per line:
```
https://www.wrrc.org/results/2025-3459/ocj_2010.htm
https://www.wrrc.org/results/2025-3459/ocj_2011.htm
```

2. Run the scraper:
```bash
python wrrc_openmarkings.py
```

The script will:
- Load URLs from the default file (`urls_openmarkings_noff_2025`)
- Scrape each competition round
- Save results as JSON files in the `results/` directory
- Generate descriptive filenames like `results_Geneve_11-10-25_Juniors_Final.json`

### Bulk Competition Scraping

Use `wrrc_bulk_scraper.py` to discover and scrape multiple competitions:

```bash
python wrrc_bulk_scraper.py
```

The interactive script will prompt you for:
1. **Dance filter**: e.g., "BW" or "Boogie Woogie" (optional)
2. **Class filter**: e.g., "Main Class" or "Juniors" (optional)
3. **Round filter**: e.g., "Semi Final" or "Final" (optional)
4. **Year range**: e.g., "2022-2025" (required)
5. **Number of parallel workers**: Default is 10 (optional)

Example:
```
Dance filter: BW
Class filter: Main Class
Round filter: Semi Final
Year range: 2025
Number of parallel workers: 10
```

The bulk scraper will:
- Discover all valid competitions for the specified year(s)
- Find all rounds for each competition
- Filter rounds based on your criteria
- Scrape and save matching rounds to JSON files

### Visualization Dashboard

Launch the interactive visualization dashboard:

```bash
streamlit run Main_Dashboard.py
```

The dashboard will open in your web browser (typically at `http://localhost:8501`).

**Features:**
- **Competition Selection**: Filter by year, competition location, class, and round
- **Interactive Charts**: 
  - Click and hover for detailed information
  - Select specific couples to compare
  - Zoom and pan on charts
- **Data Export**: View detailed results in sortable tables

## Project Structure

```
WOPAV/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── wrrc_openmarkings.py        # Single competition scraper
├── wrrc_bulk_scraper.py        # Bulk competition scraper
├── Main_Dashboard.py            # Streamlit visualization dashboard
├── urls_openmarkings_noff_2025 # Example URL file (optional)
└── results/                     # Directory for scraped JSON results
    ├── results_Geneve_11-10-25_Juniors_Final.json
    ├── results_Stuttgart_22-08-25_Senior_Semi-Final.json
    └── ...
```

## Data Format

Each scraped competition is saved as a JSON file with the following structure:

```json
{
  "competition_info": {
    "location": "Geneve",
    "date": "11.10.2025",
    "round": "Final",
    "dance": "Boogie Woogie",
    "class": "Juniors",
    "judges": [
      {
        "letter": "A",
        "name": "Raynald Chanton",
        "country": "France"
      }
    ]
  },
  "couples": [
    {
      "start_number": "71",
      "position": "1",
      "teor": "65",
      "competitor_names": "Firstname Lastname & Firstname Lastname",
      "categories": {
        "BBW": {
          "name": "Boogie Woogie Basics - Woman",
          "aggregated": "3,75",
          "judge_scores": ["3,75", "5,25", "5,25", "6,75", "6", "5,25"]
        },
        ...
      },
      "sum": "65,00",
      "total": "65,00",
      "observer": ""
    }
  ]
}
```

## Dependencies

- **requests** (>=2.28.0): HTTP library for web scraping
- **beautifulsoup4** (>=4.11.0): HTML parsing
- **tqdm** (>=4.64.0): Progress bars for bulk operations
- **streamlit** (>=1.28.0): Web dashboard framework
- **plotly** (>=5.17.0): Interactive charts
- **pandas** (>=2.0.0): Data manipulation

## Notes

- The scraper handles both standard and slow/fast format result pages
- European number format (comma as decimal separator) is preserved in the data
- The bulk scraper uses parallel processing but includes delays to be respectful to the server
- Competition discovery may take time as it tests many combinations
- Results are saved with descriptive filenames for easy identification

## License

This project is provided as-is for educational and research purposes.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.