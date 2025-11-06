"""
Interactive visualization dashboard for WRRC competition results.
"""

import json
import os
import glob
import re
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def load_all_results(results_dir="results"):
    """Load all JSON result files from the results directory."""
    results = {}
    json_files = glob.glob(os.path.join(results_dir, "*.json"))
    
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                filename = os.path.basename(json_file)
                results[filename] = data
        except Exception as e:
            st.warning(f"Error loading {json_file}: {e}")
    
    return results

def parse_european_number(num_str):
    """Convert European number format (comma as decimal) to float."""
    if not num_str or num_str == "":
        return None
    try:
        # Replace comma with dot for float conversion
        return float(num_str.replace(',', '.'))
    except:
        return None

def format_name_for_category(full_name, category):
    """
    Format competitor name based on category.
    
    Args:
        full_name: Full name in format "Firstname Lastname & Firstname Lastname"
        category: Category code (BBW, BBM, LF, DF, MI)
    
    Returns:
        Formatted name string
    """
    if not full_name or full_name == "Unknown":
        return "Unknown"
    
    if "&" not in full_name:
        return full_name.strip()
    
    parts = full_name.split("&")
    if len(parts) != 2:
        return full_name.strip()
    
    first_name = parts[0].strip() # Follower
    second_name = parts[1].strip() # Leader
    
    if category == "BBW":
        # Show follower's name only
        return first_name
    elif category == "BBM":
        # Show leader's name only
        return second_name
    else:
        # For LF, DF, MI: show both lastnames
        # Extract lastnames (last word in each name)
        first_lastname = first_name.split()[-1] if first_name.split() else ""
        second_lastname = second_name.split()[-1] if second_name.split() else ""
        return f"{first_lastname} & {second_lastname}"

def prepare_couples_data(results_data):
    """Prepare couples data for visualization."""
    couples_list = []
    comp_info = results_data.get("competition_info", {})
    
    for couple in results_data.get("couples", []):
        couple_data = {
            "start_number": couple.get("start_number"),
            "position": int(couple.get("position", 0)) if couple.get("position", "").isdigit() else 0,
            "teor": parse_european_number(couple.get("teor")),
            "sum": parse_european_number(couple.get("sum")),
            "total": parse_european_number(couple.get("total")),
            "observer": couple.get("observer", ""),
            "competitor_names": couple.get("competitor_names", "Unknown"),
            "location": comp_info.get("location", "Unknown"),
            "date": comp_info.get("date", "Unknown"),
            "round": comp_info.get("round", "Unknown"),
            "dance": comp_info.get("dance", "Unknown"),
            "class": comp_info.get("class", "Unknown"),
        }
        
        # Extract category scores
        categories = couple.get("categories", {})
        for cat_code, cat_data in categories.items():
            couple_data[f"{cat_code}_aggregated"] = parse_european_number(cat_data.get("aggregated"))
            # Store judge scores as list
            judge_scores = [parse_european_number(s) for s in cat_data.get("judge_scores", [])]
            couple_data[f"{cat_code}_judge_scores"] = judge_scores
        
        couples_list.append(couple_data)
    
    return pd.DataFrame(couples_list)

def create_leaderboard_chart(df):
    """Create an interactive leaderboard bar chart."""
    df_sorted = df.sort_values("position")
    
    fig = go.Figure()
    
    # Format names to show both names
    display_names = df_sorted["competitor_names"].apply(
        lambda name: name if name != "Unknown" else "Unknown"
    )
    
    # Add bars for total score
    fig.add_trace(go.Bar(
        x=df_sorted["position"],
        y=df_sorted["total"],
        text=[f"#{pos}<br>{name}" 
              for pos, name in zip(df_sorted["position"], display_names)],
        textposition="outside",
        marker=dict(
            color=df_sorted["total"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="Total Score")
        ),
        hovertemplate="<b>Position: %{x}</b><br>" +
                      "Couple: %{text}<br>" +
                      "Total: %{y:.2f}<br>" +
                      "Sum: %{customdata:.2f}<extra></extra>",
        customdata=df_sorted["sum"],
        name="Total Score"
    ))
    
    fig.update_layout(
        title="Leaderboard - Final Rankings",
        xaxis_title="Position",
        yaxis_title="Total Score",
        hovermode="closest",
        height=600
    )
    
    return fig

def create_category_comparison_chart(df, selected_couples_df=None):
    """Create a radar/spider chart comparing category scores."""
    categories = ["BBW", "BBM", "LF", "DF", "MI"]
    category_names = {
        "BBW": "Basics - Woman",
        "BBM": "Basics - Man",
        "LF": "Lead & Follow",
        "DF": "Dance Figures",
        "MI": "Music Interpretation"
    }
    
    # Use selected couples if provided, otherwise use top 5
    if selected_couples_df is not None and not selected_couples_df.empty:
        display_couples = selected_couples_df
    else:
        display_couples = df.nsmallest(5, "position")
    
    fig = go.Figure()
    
    for idx, row in display_couples.iterrows():
        values = []
        for cat in categories:
            score = row.get(f"{cat}_aggregated")
            values.append(score if score is not None else 0)
        
        # Close the radar chart by adding first value at the end
        values.append(values[0])
        labels = [category_names[cat] for cat in categories] + [category_names[categories[0]]]
        
        # Show both names in legend
        couple_name = row['competitor_names'] if row['competitor_names'] != "Unknown" else "Unknown"
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=labels,
            fill='toself',
            name=f"#{row['position']} {couple_name}",
            line=dict(width=2)
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max([df[cat + "_aggregated"].max() for cat in categories if cat + "_aggregated" in df.columns])]
            )
        ),
        title="Category Scores Comparison",
        height=600,
        showlegend=True
    )
    
    return fig

def create_normalized_category_comparison_chart(df, selected_couples_df=None):
    """Create a normalized radar/spider chart comparing category scores."""
    categories = ["BBW", "BBM", "LF", "DF", "MI"]
    category_names = {
        "BBW": "Basics - Woman",
        "BBM": "Basics - Man",
        "LF": "Lead & Follow",
        "DF": "Dance Figures",
        "MI": "Music Interpretation"
    }
    
    # Maximum scores for each category
    max_scores = {
        "BBW": 7.5,
        "BBM": 7.5,
        "LF": 15.0,
        "DF": 10.0,
        "MI": 25.0
    }
    
    # Use selected couples if provided, otherwise use top 5
    if selected_couples_df is not None and not selected_couples_df.empty:
        display_couples = selected_couples_df
    else:
        display_couples = df.nsmallest(5, "position")
    
    fig = go.Figure()
    
    for idx, row in display_couples.iterrows():
        values = []
        for cat in categories:
            score = row.get(f"{cat}_aggregated")
            if score is not None and max_scores[cat] > 0:
                # Normalize: divide by max score (keep as decimal 0-1)
                normalized_score = score / max_scores[cat]
                values.append(normalized_score)
            else:
                values.append(0)
        
        # Close the radar chart by adding first value at the end
        values.append(values[0])
        labels = [category_names[cat] for cat in categories] + [category_names[categories[0]]]
        
        # Show both names in legend
        couple_name = row['competitor_names'] if row['competitor_names'] != "Unknown" else "Unknown"
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=labels,
            fill='toself',
            name=f"#{row['position']} {couple_name}",
            line=dict(width=2)
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickmode='linear',
                tick0=0,
                dtick=0.2,
                tickformat='.0%'
            )
        ),
        title="Category Scores Comparison (Normalized)",
        height=600,
        showlegend=True
    )
    
    return fig

def create_category_bar_chart(df, category):
    """Create a bar chart for a specific category."""
    df_sorted = df.sort_values("position")
    
    fig = go.Figure()
    
    cat_agg_col = f"{category}_aggregated"
    if cat_agg_col not in df.columns:
        return None
    
    # Format names based on category
    display_names = df_sorted["competitor_names"].apply(
        lambda name: format_name_for_category(name, category)
    )
    
    fig.add_trace(go.Bar(
        x=[f"#{pos}" for pos in df_sorted["position"]],
        y=df_sorted[cat_agg_col],
        text=display_names,
        marker=dict(
            color=df_sorted[cat_agg_col],
            colorscale="Blues",
            showscale=True,
            colorbar=dict(title="Score")
        ),
        hovertemplate="<b>%{text}</b><br>" +
                      "Position: %{x}<br>" +
                      "Score: %{y:.2f}<extra></extra>",
        name=category
    ))
    
    category_names = {
        "BBW": "Boogie Woogie Basics - Woman",
        "BBM": "Boogie Woogie Basics - Man",
        "LF": "Lead and follow, basic dancing, harmony, dance performance",
        "DF": "Dance Figures (how do they present)",
        "MI": "Music Interpretation (what do they present)"
    }
    
    fig.update_layout(
        title=f"{category_names.get(category, category)} - Scores by Position",
        xaxis_title="Position",
        yaxis_title="Aggregated Score",
        height=400
    )
    
    return fig

def create_judge_scores_chart(df, category, judges_list=None, selected_couples_df=None):
    """Create a chart showing judge scores for a category."""
    # Use selected couples if provided, otherwise use top 5
    if selected_couples_df is not None and not selected_couples_df.empty:
        df_display = selected_couples_df
    else:
        df_display = df.nsmallest(5, "position")
    
    fig = go.Figure()
    
    cat_judge_col = f"{category}_judge_scores"
    
    # Create judge name mapping if judges_list is provided
    judge_names = []
    if judges_list:
        # Sort judges by letter to match score order
        sorted_judges = sorted(judges_list, key=lambda x: x.get("letter", ""))
        judge_names = [judge.get("name", f"Judge {judge.get('letter', '?')}") for judge in sorted_judges]
    
    # Define different line styles to make overlapping lines distinguishable
    line_styles = [
        dict(width=2.5, dash='solid'),        # Solid line
        dict(width=2.5, dash='dash'),         # Dashed line
        dict(width=2.5, dash='dot'),          # Dotted line
        dict(width=2.5, dash='dashdot'),      # Dash-dot line
        dict(width=2.5, dash='longdash'),     # Long dash
        dict(width=2.5, dash='longdashdot'),  # Long dash-dot
        dict(width=2.5, dash='5px 2px'),      # Custom: 5px dash, 2px gap
        dict(width=2.5, dash='10px 5px 2px 5px'), # Custom: dash-dot-dot pattern
    ]
    
    for trace_idx, (idx, row) in enumerate(df_display.iterrows()):
        judge_scores = row.get(cat_judge_col, [])
        if judge_scores:
            # Filter out None values
            valid_scores = [s for s in judge_scores if s is not None]
            
            # Use judge names if available, otherwise use letters
            if judge_names and len(judge_names) >= len(valid_scores):
                x_labels = judge_names[:len(valid_scores)]
            else:
                x_labels = [chr(65 + i) for i in range(len(valid_scores))]  # A, B, C, ...
            
            # Format name based on category
            couple_name = format_name_for_category(row['competitor_names'], category)
            
            # Select line style (cycle through styles if more couples than styles)
            line_style = line_styles[trace_idx % len(line_styles)]
            
            fig.add_trace(go.Scatter(
                x=x_labels,
                y=valid_scores,
                mode='lines+markers',
                name=f"#{row['position']} {couple_name}",
                line=line_style,
                marker=dict(size=10, line=dict(width=1, color='white')),
                opacity=0.9  # Slight transparency to see overlapping lines
            ))
    
    fig.update_layout(
        title=f"{category} - Judge Scores",
        xaxis_title="Judge",
        yaxis_title="Score",
        hovermode="x unified",
        height=400
    )
    
    return fig

def create_judge_scores_by_judge_chart(df, category, judges_list=None, selected_couples_df=None):
    """Create a chart showing total scores (sum of all categories) from each judge to all couples."""
    # Use selected couples if provided, otherwise use all couples
    if selected_couples_df is not None and not selected_couples_df.empty:
        df_display = selected_couples_df.sort_values("position")
    else:
        df_display = df.sort_values("position")
    
    fig = go.Figure()
    
    # All categories to sum
    categories = ["BBW", "BBM", "LF", "DF", "MI"]
    
    # Create judge name mapping if judges_list is provided
    judge_names = []
    if judges_list:
        # Sort judges by letter to match score order
        sorted_judges = sorted(judges_list, key=lambda x: x.get("letter", ""))
        judge_names = [judge.get("name", f"Judge {judge.get('letter', '?')}") for judge in sorted_judges]
    else:
        # If no judges list, try to determine from first couple's scores
        first_couple_scores = df_display.iloc[0].get(f"{categories[0]}_judge_scores", [])
        if first_couple_scores:
            num_judges = len([s for s in first_couple_scores if s is not None])
            judge_names = [chr(65 + i) for i in range(num_judges)]  # A, B, C, ...
    
    if not judge_names:
        return None
    
    # Get colors for each couple
    colors = px.colors.qualitative.Set3
    
    for idx, (row_idx, row) in enumerate(df_display.iterrows()):
        # Calculate total score from each judge (sum across all categories)
        judge_totals = []
        
        # Get the number of judges from the first category
        first_category_scores = row.get(f"{categories[0]}_judge_scores", [])
        if not first_category_scores:
            continue
        
        num_judges = len([s for s in first_category_scores if s is not None])
        
        # For each judge, sum scores across all categories
        for judge_idx in range(num_judges):
            total_score = 0.0
            for cat in categories:
                cat_scores = row.get(f"{cat}_judge_scores", [])
                if cat_scores and judge_idx < len(cat_scores):
                    score = cat_scores[judge_idx]
                    if score is not None:
                        total_score += score
            judge_totals.append(total_score)
        
        # Use judge names if available
        if len(judge_names) >= len(judge_totals):
            x_labels = judge_names[:len(judge_totals)]
        else:
            x_labels = [chr(65 + i) for i in range(len(judge_totals))]  # A, B, C, ...
        
        # Use full couple name (not category-specific)
        couple_name = row['competitor_names'] if row['competitor_names'] != "Unknown" else "Unknown"
        
        # Get color for this couple
        color = colors[idx % len(colors)]
        
        fig.add_trace(go.Bar(
            x=x_labels,
            y=judge_totals,
            name=f"#{row['position']} {couple_name}",
            marker=dict(color=color, line=dict(width=1, color='white')),
            opacity=0.8
        ))
    
    fig.update_layout(
        title="Total Scores by Judge (Sum of All Categories)",
        xaxis_title="Judge",
        yaxis_title="Total Score",
        barmode='group',  # Group bars side by side
        height=500,
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

def main():
    st.set_page_config(
        page_title="WRRC Competition Results Visualizer",
        page_icon="🏆",
        layout="wide"
    )
    
    st.title("🏆 WRRC Competition Results Visualizer")
    st.markdown("Explore and analyze competition results with interactive visualizations")
    
    # Load all results
    results = load_all_results()
    
    if not results:
        st.error("No result files found in the 'results' directory.")
        return
    
    # Sidebar for file selection
    st.sidebar.header("Competition Selection")
    
    # Organize results by year, competition, class, and round
    organized_results = {}
    for filename, data in results.items():
        comp_info = data.get("competition_info", {})
        date_str = comp_info.get("date", "Unknown")
        location = comp_info.get("location", "Unknown")
        class_name = comp_info.get("class", "Unknown")
        round_name = comp_info.get("round", "Unknown")
        
        # Extract year from date (format: "DD.MM.YYYY" or similar)
        year = "Unknown"
        if date_str and date_str != "Unknown":
            # Try to extract year from date string
            year_match = re.search(r'(\d{4})', date_str)
            if year_match:
                year = year_match.group(1)
        
        if year not in organized_results:
            organized_results[year] = {}
        
        # Use location as competition identifier
        if location not in organized_results[year]:
            organized_results[year][location] = {}
        
        if class_name not in organized_results[year][location]:
            organized_results[year][location][class_name] = {}
        
        organized_results[year][location][class_name][round_name] = {
            "filename": filename,
            "data": data
        }
    
    # Year filter
    available_years = sorted([y for y in organized_results.keys() if y != "Unknown"], reverse=True)
    if "Unknown" in organized_results:
        available_years.append("Unknown")
    
    if not available_years:
        st.error("No valid years found in the results.")
        return
    
    selected_year = st.sidebar.selectbox(
        "Select Year:",
        options=available_years,
        index=0
    )
    
    # Competition filter (based on selected year)
    if selected_year not in organized_results:
        st.error(f"No competitions found for year {selected_year}.")
        return
    
    available_competitions = sorted(organized_results[selected_year].keys())
    if not available_competitions:
        st.error(f"No competitions found for year {selected_year}.")
        return
    
    selected_competition = st.sidebar.selectbox(
        "Select Competition:",
        options=available_competitions,
        index=0
    )
    
    # Class filter
    if selected_competition not in organized_results[selected_year]:
        st.error(f"No classes found for competition {selected_competition}.")
        return
    
    available_classes = sorted(organized_results[selected_year][selected_competition].keys())
    if not available_classes:
        st.error(f"No classes found for competition {selected_competition}.")
        return
    
    selected_class = st.sidebar.selectbox(
        "Select Class:",
        options=available_classes,
        index=0
    )
    
    # Round filter
    if selected_class not in organized_results[selected_year][selected_competition]:
        st.error(f"No rounds found for class {selected_class}.")
        return
    
    available_rounds = sorted(organized_results[selected_year][selected_competition][selected_class].keys())
    if not available_rounds:
        st.error(f"No rounds found for class {selected_class}.")
        return
    
    selected_round = st.sidebar.selectbox(
        "Select Round:",
        options=available_rounds,
        index=0
    )
    
    # Get the selected data
    selected_entry = organized_results[selected_year][selected_competition][selected_class][selected_round]
    selected_file = selected_entry["filename"]
    selected_data = selected_entry["data"]
    
    # Display competition info
    comp_info = selected_data.get("competition_info", {})
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Location", comp_info.get("location", "Unknown"))
    with col2:
        st.metric("Date", comp_info.get("date", "Unknown"))
    with col3:
        st.metric("Class", comp_info.get("class", "Unknown"))
    with col4:
        st.metric("Round", comp_info.get("round", "Unknown"))
    
    # Prepare data
    df = prepare_couples_data(selected_data)
    
    if df.empty:
        st.warning("No couple data found in this file.")
        return
    
    st.metric("Total Couples", len(df))
    
    # Main visualizations
    st.header("Leaderboard")
    leaderboard_fig = create_leaderboard_chart(df)
    st.plotly_chart(leaderboard_fig, width="stretch")
    
    # Category comparison
    st.header("Category Scores Comparison")
    
    # Create checkboxes for couple selection
    df_sorted = df.sort_values("position")
    couple_options = {}
    for idx, row in df_sorted.iterrows():
        label = f"#{row['position']} - {row['competitor_names']}"
        couple_options[label] = idx
    
    # Default to top 5 couples selected
    default_selected = list(df_sorted.nsmallest(5, "position").index)
    
    selected_indices = st.multiselect(
        "Select couples to compare:",
        options=list(couple_options.values()),
        format_func=lambda x: f"#{df_sorted.loc[x, 'position']} - {df_sorted.loc[x, 'competitor_names']}",
        default=default_selected
    )
    
    # Create filtered dataframe with selected couples
    if selected_indices:
        selected_couples_df = df_sorted.loc[selected_indices]
    else:
        selected_couples_df = df_sorted.nsmallest(5, "position")
    
    col1, col2 = st.columns(2)
    
    with col1:
        comparison_fig = create_category_comparison_chart(df, selected_couples_df)
        st.plotly_chart(comparison_fig, width="stretch")
    
    with col2:
        normalized_fig = create_normalized_category_comparison_chart(df, selected_couples_df)
        st.plotly_chart(normalized_fig, width="stretch")
    
    # Category-specific charts
    st.header("Category Breakdown")
    categories = ["BBW", "BBM", "LF", "DF", "MI"]
    
    selected_category = st.selectbox("Select Category:", categories)
    
    category_fig = create_category_bar_chart(df, selected_category)
    if category_fig:
        st.plotly_chart(category_fig, width="stretch")
    
    # Judge scores
    st.header("Judge Scores Analysis")
    judge_category = st.selectbox("Select Category for Judge Scores:", categories, key="judge_category")
    
    # Create checkboxes for couple selection for judge scores
    judge_couple_options = {}
    for idx, row in df_sorted.iterrows():
        judge_couple_options[idx] = idx
    
    # Default to top 5 couples selected
    judge_default_selected = list(df_sorted.nsmallest(5, "position").index)
    
    judge_selected_indices = st.multiselect(
        "Select couples to compare:",
        options=list(judge_couple_options.values()),
        format_func=lambda x: f"#{df_sorted.loc[x, 'position']} - {df_sorted.loc[x, 'competitor_names']}",
        default=judge_default_selected,
        key="judge_couples"
    )
    
    # Create filtered dataframe with selected couples for judge scores
    if judge_selected_indices:
        judge_selected_couples_df = df_sorted.loc[judge_selected_indices]
    else:
        judge_selected_couples_df = df_sorted.nsmallest(5, "position")
    
    judges_list = comp_info.get("judges", [])
    judge_fig = create_judge_scores_chart(df, judge_category, judges_list=judges_list, selected_couples_df=judge_selected_couples_df)
    if judge_fig:
        st.plotly_chart(judge_fig, width="stretch")
    
    # Chart showing total scores (sum of all categories) from each judge to all couples
    judge_by_judge_fig = create_judge_scores_by_judge_chart(df, judge_category, judges_list=judges_list, selected_couples_df=judge_selected_couples_df)
    if judge_by_judge_fig:
        st.plotly_chart(judge_by_judge_fig, width="stretch")
    
    # Detailed data table
    st.header("Detailed Results Table")
    
    # Prepare table data
    display_df = df[[
        "position", "start_number", "competitor_names", "total", "sum",
        "BBW_aggregated", "BBM_aggregated", "LF_aggregated", 
        "DF_aggregated", "MI_aggregated", "observer"
    ]].copy()
    
    display_df.columns = [
        "Position", "Start #", "Competitors", "Total", "Sum",
        "BBW", "BBM", "LF", "DF", "MI", "Observer"
    ]
    
    st.dataframe(display_df, width="stretch", height=400)
    
    # Judges information
    if comp_info.get("judges"):
        st.header("Judges")
        judges_df = pd.DataFrame(comp_info["judges"])
        st.dataframe(judges_df[["letter", "name", "country"]], width="stretch")

if __name__ == "__main__":
    main()

