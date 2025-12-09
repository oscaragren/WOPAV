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

def load_corresponding_round_file(filename, results):
    """Load the corresponding Slow or Fast round file."""
    # If current file is Slow, load Fast; if Fast, load Slow
    if filename.endswith("_Slow.json"):
        corresponding_filename = filename.replace("_Slow.json", "_Fast.json")
    elif filename.endswith("_Fast.json"):
        corresponding_filename = filename.replace("_Fast.json", "_Slow.json")
    else:
        return None
    
    # Check if the corresponding file exists in results
    if corresponding_filename in results:
        return results[corresponding_filename]
    return None

def create_combined_slow_fast_judge_chart(data_current, data_other, judges_list=None, selected_couples_df=None):
    """Create a chart showing total scores from each judge combining both slow and fast rounds."""
    # Prepare dataframes from the data dictionaries
    df_current = prepare_couples_data(data_current)
    df_other = prepare_couples_data(data_other)
    
    if df_current.empty or df_other.empty:
        return None
    
    # Use selected couples if provided, otherwise use all couples
    if selected_couples_df is not None and not selected_couples_df.empty:
        df_display = selected_couples_df.sort_values("position")
    else:
        df_display = df_current.sort_values("position")
    
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
        # Find corresponding couple in other round by start_number
        start_number = row.get("start_number")
        if not start_number:
            continue
        
        # Find matching couple in other round
        other_couple = df_other[df_other["start_number"] == start_number]
        if other_couple.empty:
            continue
        
        other_row = other_couple.iloc[0]
        
        # Calculate total score from each judge (sum across all categories for both rounds)
        judge_totals = []
        
        # Get the number of judges from the first category
        first_category_scores = row.get(f"{categories[0]}_judge_scores", [])
        if not first_category_scores:
            continue
        
        num_judges = len([s for s in first_category_scores if s is not None])
        
        # For each judge, sum scores across all categories for both rounds
        for judge_idx in range(num_judges):
            total_score = 0.0
            
            # Sum scores from current round
            for cat in categories:
                cat_scores = row.get(f"{cat}_judge_scores", [])
                if cat_scores and judge_idx < len(cat_scores):
                    score = cat_scores[judge_idx]
                    if score is not None:
                        total_score += score
            
            # Sum scores from other round
            for cat in categories:
                cat_scores = other_row.get(f"{cat}_judge_scores", [])
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
        title="Total Scores by Judge (Combined Slow + Fast Rounds)",
        xaxis_title="Judge",
        yaxis_title="Total Score (Slow + Fast)",
        barmode='group',  # Group bars side by side
        height=500,
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

def combine_rounds_for_majority(data_current, data_other):
    """Combine slow and fast round data into one dataframe for majority calculations."""
    df_current = prepare_couples_data(data_current)
    df_other = prepare_couples_data(data_other)

    if df_current.empty:
        return df_other
    if df_other.empty:
        return df_current

    categories = ["BBW", "BBM", "LF", "DF", "MI"]

    current_map = {str(row["start_number"]): row for _, row in df_current.iterrows()}
    other_map = {str(row["start_number"]): row for _, row in df_other.iterrows()}

    combined_rows = []

    all_start_numbers = sorted(set(current_map.keys()) | set(other_map.keys()), key=lambda x: (x is None, x))

    for start_number in all_start_numbers:
        base_row = current_map.get(start_number)
        other_row = other_map.get(start_number)

        if base_row is None and other_row is not None:
            combined_rows.append(other_row.copy())
            continue
        if base_row is not None and other_row is None:
            combined_rows.append(base_row.copy())
            continue

        combined = base_row.copy()

        for cat in categories:
            col_scores = f"{cat}_judge_scores"

            scores_a = list(base_row.get(col_scores, [])) if isinstance(base_row.get(col_scores, []), list) else []
            scores_b = list(other_row.get(col_scores, [])) if isinstance(other_row.get(col_scores, []), list) else []

            max_len = max(len(scores_a), len(scores_b))
            if max_len == 0:
                combined[col_scores] = []
                continue

            combined_scores = []
            for idx in range(max_len):
                val_a = scores_a[idx] if idx < len(scores_a) else None
                val_b = scores_b[idx] if idx < len(scores_b) else None

                if val_a is None and val_b is None:
                    combined_scores.append(None)
                else:
                    total = 0.0
                    if val_a is not None:
                        total += float(val_a)
                    if val_b is not None:
                        total += float(val_b)
                    combined_scores.append(total)

            combined[col_scores] = combined_scores

        combined_rows.append(combined)

    if not combined_rows:
        return pd.DataFrame()

    return pd.DataFrame(combined_rows)

def build_judge_rankings_for_subset(df_subset, judges_list=None):
    """Build per-judge rankings (lower is better) for the provided couples subset."""
    categories = ["BBW", "BBM", "LF", "DF", "MI"]
    if df_subset is None or df_subset.empty:
        return [], []

    num_judges = 0
    for cat in categories:
        col = f"{cat}_judge_scores"
        if col in df_subset.columns:
            for scores in df_subset[col]:
                if isinstance(scores, list):
                    count = len([s for s in scores if s is not None])
                    if count > num_judges:
                        num_judges = count
            if num_judges:
                break

    if num_judges == 0:
        return [], []

    judge_names = []
    if judges_list:
        sorted_judges = sorted(judges_list, key=lambda j: j.get("letter", ""))
        for idx in range(num_judges):
            if idx < len(sorted_judges):
                judge = sorted_judges[idx]
                full_name = judge.get("name") or ""
                letter = judge.get("letter")
                if full_name:
                    first_name = full_name.strip().split()[0]
                elif letter:
                    first_name = letter
                else:
                    first_name = f"Judge {idx + 1}"
            else:
                first_name = f"Judge {idx + 1}"
            judge_names.append(first_name)
    else:
        judge_names = [f"Judge {i+1}" for i in range(num_judges)]

    judge_rankings = []
    for judge_idx in range(num_judges):
        totals = []
        for _, row in df_subset.iterrows():
            start_number = str(row.get("start_number"))
            total_score = 0.0
            for cat in categories:
                scores = row.get(f"{cat}_judge_scores", [])
                if isinstance(scores, list) and judge_idx < len(scores):
                    score = scores[judge_idx]
                    if score is not None:
                        total_score += score
            totals.append((start_number, total_score))

        # Highest total should receive rank 1
        totals.sort(key=lambda x: (-x[1], x[0]))
        ranking = {}
        prev_score = None
        prev_rank = None
        for position, (start_number, score) in enumerate(totals, start=1):
            if prev_score is not None and score == prev_score:
                rank = prev_rank
            else:
                rank = position
                prev_score = score
                prev_rank = rank
            ranking[start_number] = rank

        judge_rankings.append(ranking)

    return judge_rankings, judge_names

def resolve_ties(candidates, judge_rankings, judge_names):
    """Resolve ties using head-to-head comparisons between couples."""
    num_judges = len(judge_names)
    tie_info = {}
    if len(candidates) <= 1:
        return [candidates], tie_info

    # Helper to count head-to-head wins
    def head_to_head(a, b):
        wins_a = 0
        wins_b = 0
        for ranking in judge_rankings:
            rank_a = ranking.get(a, float('inf'))
            rank_b = ranking.get(b, float('inf'))
            if rank_a < rank_b:
                wins_a += 1
            elif rank_b < rank_a:
                wins_b += 1
        return wins_a, wins_b

    if len(candidates) == 2:
        a, b = candidates
        wins_a, wins_b = head_to_head(a, b)
        if wins_a > wins_b:
            tie_info[a] = f"Head-to-head {wins_a}-{wins_b}"
            tie_info[b] = f"Head-to-head {wins_b}-{wins_a}"
            return [[a], [b]], tie_info
        if wins_b > wins_a:
            tie_info[a] = f"Head-to-head {wins_a}-{wins_b}"
            tie_info[b] = f"Head-to-head {wins_b}-{wins_a}"
            return [[b], [a]], tie_info
        # Exact tie
        tie_info[a] = tie_info[b] = f"Head-to-head tie ({wins_a}-{wins_b})"
        return [candidates], tie_info

    # More than two couples tied: use pairwise wins as scorecard
    pairwise_scores = {c: 0 for c in candidates}
    pairwise_notes = {c: [] for c in candidates}

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a = candidates[i]
            b = candidates[j]
            wins_a, wins_b = head_to_head(a, b)
            if wins_a > wins_b:
                pairwise_scores[a] += 1
            elif wins_b > wins_a:
                pairwise_scores[b] += 1
            pairwise_notes[a].append(f"vs {b}: {wins_a}-{wins_b}")
            pairwise_notes[b].append(f"vs {a}: {wins_b}-{wins_a}")

    max_score = max(pairwise_scores.values())
    top_candidates = [c for c, score in pairwise_scores.items() if score == max_score]

    if len(top_candidates) == len(candidates):
        # Unable to separate – treat as full tie
        for c in candidates:
            tie_info[c] = "; ".join(pairwise_notes[c])
        return [candidates], tie_info

    result_groups = []
    remaining = candidates[:]
    while remaining:
        current_scores = {c: pairwise_scores[c] for c in remaining}
        max_score = max(current_scores.values())
        current_top = [c for c in remaining if current_scores[c] == max_score]

        if len(current_top) == len(remaining):
            for c in remaining:
                tie_info[c] = "; ".join(pairwise_notes[c])
            result_groups.append(remaining[:])
            break

        if len(current_top) == 1:
            winner = current_top[0]
            tie_info[winner] = "; ".join(pairwise_notes[winner])
            result_groups.append([winner])
            remaining.remove(winner)
            continue

        # Recursively resolve among the current top candidates
        sub_groups, sub_info = resolve_ties(current_top, judge_rankings, judge_names)
        result_groups.extend(sub_groups)
        tie_info.update(sub_info)
        for group in sub_groups:
            for candidate in group:
                if candidate in remaining:
                    remaining.remove(candidate)

    # Ensure all candidates have tie info recorded
    for c in candidates:
        tie_info.setdefault(c, "; ".join(pairwise_notes[c]))

    return result_groups, tie_info

def determine_majority_placements(df_subset, judge_rankings, judge_names):
    """Apply the majority placement system to determine the ordering."""
    unplaced = [str(start) for start in df_subset["start_number"].tolist()]
    placement_records = []
    next_place = 1
    total_couples = len(unplaced)
    num_judges = len(judge_names)

    while unplaced:
        majority_found = False
        for threshold in range(1, total_couples + 1):
            candidate_counts = {}
            for start_number in unplaced:
                count = sum(1 for ranking in judge_rankings if ranking.get(start_number, float('inf')) <= threshold)
                if count > num_judges / 2:
                    candidate_counts[start_number] = count

            if candidate_counts:
                summary_map = {
                    start_number: f"Majority ≤ {threshold} ({candidate_counts[start_number]}/{num_judges} judges)"
                    for start_number in candidate_counts
                }

                # Sort by number of favourable placements (descending)
                sorted_candidates = sorted(candidate_counts.items(), key=lambda x: (-x[1], x[0]))
                idx = 0
                while idx < len(sorted_candidates):
                    count_value = sorted_candidates[idx][1]
                    same_count_candidates = [sorted_candidates[idx][0]]
                    idx += 1
                    while idx < len(sorted_candidates) and sorted_candidates[idx][1] == count_value:
                        same_count_candidates.append(sorted_candidates[idx][0])
                        idx += 1

                    resolved_groups, tie_info = resolve_ties(same_count_candidates, judge_rankings, judge_names)
                    for group in resolved_groups:
                        record = {
                            "place": next_place,
                            "couples": group,
                            "summary": summary_map.get(group[0]),
                            "tie_info": {c: tie_info.get(c) for c in group} if tie_info else {}
                        }
                        placement_records.append(record)
                        for candidate in group:
                            if candidate in unplaced:
                                unplaced.remove(candidate)
                        next_place += len(group)

                majority_found = True
                break

        if not majority_found:
            # Fallback: order remaining couples by average ranking across judges
            avg_ranks = []
            for start_number in unplaced:
                total_rank = sum(ranking.get(start_number, len(df_subset) + 1) for ranking in judge_rankings)
                avg_ranks.append((start_number, total_rank / num_judges))

            avg_ranks.sort(key=lambda x: (x[1], x[0]))
            for start_number, avg in avg_ranks:
                record = {
                    "place": next_place,
                    "couples": [start_number],
                    "summary": f"Fallback by average rank ({avg:.2f})",
                    "tie_info": {start_number: f"Fallback by average rank ({avg:.2f})"}
                }
                placement_records.append(record)
                unplaced.remove(start_number)
                next_place += 1

    return placement_records

def compute_majority_system_results(df_subset, judges_list=None):
    """Compute majority-based placements and return a dataframe summarising the scenario."""
    if df_subset is None or df_subset.empty:
        return None

    judge_rankings, judge_names = build_judge_rankings_for_subset(df_subset, judges_list)
    if not judge_rankings or not judge_names:
        return None

    placement_records = determine_majority_placements(df_subset, judge_rankings, judge_names)
    if not placement_records:
        return None

    rows = []
    for record in placement_records:
        place = record["place"]
        couples = record["couples"]
        summary = record.get("summary")
        tie_info = record.get("tie_info") or {}

        place_label = f"{place}"
        if len(couples) > 1:
            place_label = f"{place} (tie)"

        for start_number in couples:
            row = df_subset[df_subset["start_number"] == start_number].iloc[0]
            row_data = {
                "Place": place_label,
                "Start #": start_number,
                "Couple": row.get("competitor_names", "Unknown")
            }

            for idx, ranking in enumerate(judge_rankings):
                col_name = judge_names[idx]
                rank_value = ranking.get(start_number)
                row_data[col_name] = "" if rank_value is None else rank_value

            notes = []
            if summary:
                notes.append(summary)
            tie_note = tie_info.get(start_number)
            if tie_note:
                notes.append(tie_note)
            row_data["Notes"] = " | ".join(notes)

            rows.append(row_data)

    if not rows:
        return None

    df_result = pd.DataFrame(rows)
    ordered_cols = ["Place", "Start #", "Couple"] + judge_names + ["Notes"]
    df_result = df_result[ordered_cols]
    return df_result


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
        
        # Determine base round label (strip trailing " - fast/slow" if present)
        base_round_label = (round_name or "Unknown round").strip()
        if round_name:
            parts = round_name.rsplit(" - ", 1)
            if len(parts) == 2 and parts[1].lower() in ("fast", "slow"):
                base_round_label = parts[0].strip()

        # Check if this is a Slow or Fast round file and append to round name
        if filename.endswith("_Slow.json"):
            display_round_name = f"{base_round_label} (slow)"
        elif filename.endswith("_Fast.json"):
            display_round_name = f"{base_round_label} (fast)"
        else:
            display_round_name = base_round_label
        
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
        
        # Store with the display round name (which includes Slow/Fast if applicable)
        organized_results[year][location][class_name][display_round_name] = {
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
    round_display_name = selected_round  # Use the selected round name which already includes (Slow) or (Fast) if applicable
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Location", comp_info.get("location", "Unknown"))
    with col2:
        st.metric("Date", comp_info.get("date", "Unknown"))
    with col3:
        st.metric("Class", comp_info.get("class", "Unknown"))
    with col4:
        st.metric("Round", round_display_name)
    
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
    
    # For First round or Final round with Slow/Fast, show combined chart
    round_name_lower = comp_info.get("round", "").lower()
    is_first_or_final = "first round" in round_name_lower or "final" in round_name_lower
    
    if is_first_or_final and (selected_file.endswith("_Slow.json") or selected_file.endswith("_Fast.json")):
        # Load the corresponding Slow/Fast file
        other_round_data = load_corresponding_round_file(selected_file, results)
        
        if other_round_data:
            combined_fig = create_combined_slow_fast_judge_chart(
                selected_data, 
                other_round_data, 
                judges_list=judges_list, 
                selected_couples_df=judge_selected_couples_df
            )
            if combined_fig:
                st.plotly_chart(combined_fig, width="stretch")
    

    # Alternative ranking using majority placement logic
    majority_input_df = judge_selected_couples_df.sort_values("position")
    majority_df = compute_majority_system_results(majority_input_df, judges_list)
    if majority_df is not None and not majority_df.empty:
        st.subheader("Majority Placement Scenario (Current Round)")
        st.dataframe(majority_df, width="stretch", hide_index=True)
        st.caption(
            "Placements computed by awarding each judge's favourite couple rank 1, "
            "then checking for majorities across 1st, 1st-2nd, etc. Ties are resolved "
            "using head-to-head judge comparisons; if still tied with an even number "
            "of judges the couples share the place."
        )

        # If we have both slow and fast data for this round, compute combined majority scenario
        if is_first_or_final and (selected_file.endswith("_Slow.json") or selected_file.endswith("_Fast.json")):
            other_round_data = load_corresponding_round_file(selected_file, results)
            if other_round_data:
                combined_df = combine_rounds_for_majority(selected_data, other_round_data)
                if combined_df is not None and not combined_df.empty:
                    selected_starts = set(majority_input_df["start_number"].astype(str).tolist())
                    combined_df = combined_df[combined_df["start_number"].astype(str).isin(selected_starts)].copy()
                    if "position" in combined_df.columns:
                        combined_df = combined_df.sort_values("position")
                combined_majority_df = compute_majority_system_results(combined_df, judges_list)
                if combined_majority_df is not None and not combined_majority_df.empty:
                    st.subheader("Majority Placement Scenario (Combined Slow + Fast)")
                    st.dataframe(combined_majority_df, width="stretch", hide_index=True)
 
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
    
    st.dataframe(display_df, width="stretch", height=400, hide_index=True)
    
    # Judges information
    if comp_info.get("judges"):
        st.header("Judges")
        judges_df = pd.DataFrame(comp_info["judges"])
        st.dataframe(judges_df[["letter", "name", "country"]], width="stretch", hide_index=True)

if __name__ == "__main__":
    main()

