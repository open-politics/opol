from bs4 import BeautifulSoup
import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from prefect import task, flow
from pydantic import BaseModel
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse
from io import BytesIO
import regex as r

from fastapi import APIRouter

router = APIRouter()



@task
def fetch_german_polls(plot: bool = False):
    # Define a dictionary of polling institutes and their respective URLs
    ingestion_date = datetime.now().strftime('%Y-%m-%d')

    institutes = {
        'Allensbach': 'https://www.wahlrecht.de/umfragen/allensbach.htm',
        'Forsa': 'https://www.wahlrecht.de/umfragen/forsa.htm',
        'Politbarometer': 'https://www.wahlrecht.de/umfragen/politbarometer.htm'
    }

    all_data = []


    # Iterate over each institute and its URL
    for institute, url in institutes.items():
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Locate the main results table
        table = soup.find('table', class_='wilko')
        headers = [th.get_text(strip=True) for th in table.find('thead').find('tr').find_all('th')]
        
        # Determine the range of party columns
        end_index = headers.index('Sonstige') if 'Sonstige' in headers else len(headers) - 3
        date_col_index = 0
        party_columns = headers[2:end_index]
        
        # Extract rows from the table body
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')[1:]
        
        # Process each row to extract data
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            
            date_str = cells[date_col_index].get_text(strip=True)
            
            try:
                date = datetime.strptime(date_str, '%d.%m.%Y')
            except ValueError:
                continue
            
            data_cells = cells[2:end_index]
            if len(data_cells) != len(party_columns):
                continue
            
            for party, cell in zip(party_columns, data_cells):
                val = cell.get_text(strip=True)
                val = None if val == '–' else float(val.replace('%', '').replace(',', '.')) if val else None
                
                all_data.append({
                    'date': date,
                    'institute': institute,
                    'party': party,
                    'percentage': val
                })

    # Create a DataFrame from the collected data
    df = pd.DataFrame(all_data)

    if plot:
        # Pivot the DataFrame to prepare for plotting
        pivot_df = df.groupby(['date', 'party'])['percentage'].mean().unstack('party').sort_index()
        smoothed_df = pivot_df.rolling(window=7, min_periods=1).mean()

        # Plot the smoothed data
        plt.figure(figsize=(12, 6))
        for party in smoothed_df.columns:
            plt.plot(smoothed_df.index, smoothed_df[party], label=party)
        plt.legend()
        plt.title("German Polls Over Time")
        plt.xlabel("Date")
        plt.ylabel("Percentage")
        plt.grid(True)

        # Save plot to a BytesIO object
        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        return buf

    df = df.replace([float('inf'), float('-inf')], None).fillna(0)
    
    # Convert datetime objects to strings
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')

    return df

@task
def fetch_last_election_results():
    search_url = "https://en.wikipedia.org/w/api.php"
    search_params = {
        "action": "opensearch",
        "search": "2021 German federal election",
        "limit": 1,
        "namespace": 0,
        "format": "json"
    }

    response = requests.get(search_url, params=search_params)
    search_results = response.json()

    page_url = search_results[3][0] if search_results and len(search_results) > 3 and search_results[3] else None
    if not page_url:
        raise Exception("Wikipedia page not found.")

    page_response = requests.get(page_url)
    soup = BeautifulSoup(page_response.content, 'html.parser')

    table = soup.find('table', {'class': 'infobox'})
    if not table:
        raise Exception("Election results table not found.")

    data = {'Party': [], 'Percentage': []}

    for row in table.find_all('tr'):
        header = row.find('th')
        data_cells = row.find_all('td')
        if header and data_cells:
            key = header.get_text(strip=True)
            if key in data:
                for cell in data_cells:
                    text = cell.get_text(strip=True)
                    if key == 'Percentage':
                        match = r.search(r'\d{1,2}\.\d{1,2}', text)
                        percentage = match.group(0) if match else None
                        data[key].append(percentage)
                    else:
                        data[key].append(text)

    election_results = {}
    for party, percentage in zip(data['Party'], data['Percentage']):
        if party and percentage:
            election_results[party] = float(percentage.replace(',', '.'))

    return election_results

@router.get("/germany")
async def get_germany_polls(
        latest: bool = Query(False, description="Return only the latest poll block for each institute"),
        summarised: bool = Query(False, description="Collapsed polls and ordered by percentage")
    ):
    df = fetch_german_polls()
    
    # Ensure 'date' column is of datetime type
    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
    
    if latest:
        # Get the latest date for each institute
        latest_dates = df.groupby('institute')['date'].max().reset_index()
        # Merge to filter the DataFrame to only include the latest block for each institute
        df = df.merge(latest_dates, on=['institute', 'date'])
    
    if summarised:
        # Fetch last election results
        last_election = fetch_last_election_results()

        # Filter data for the last two weeks
        two_weeks_ago = datetime.now() - timedelta(weeks=2)
        df = df[df['date'] >= two_weeks_ago]

        # Group by party and calculate the mean percentage
        current_results = df.groupby('party')['percentage'].mean().reset_index()

        # Calculate change since last election
        current_results['change_since_election'] = current_results.apply(
            lambda row: round(row['percentage'] - last_election.get(row['party'], 0), 2),
            axis=1
        )

        # Sort by percentage in descending order
        current_results = current_results.sort_values(by='percentage', ascending=False)

        # Rename columns for clarity
        current_results.rename(columns={
            'percentage': 'percentage',
            'change_since_election': 'change_since_election'
        }, inplace=True)

        # Convert to dictionary
        result = current_results.to_dict(orient='records')
    else:
        # Convert 'date' column to string format
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')

        # Replace inf values with None and NaN values with a specific value (e.g., 0)
        df = df.replace([float('inf'), float('-inf')], None).fillna(0)

        result = df.to_dict(orient='records')

    return JSONResponse(content=result)