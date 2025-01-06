import os
from datetime import datetime, timedelta
import time
import logging
import subprocess
from prefect import task, flow

@task
def download_recent_pressekonferenz_videos():
    channel_url = 'https://www.youtube.com/@tilojung/videos'
    search_keywords = ['Bundespressekonferenz', "Regierungspressekonferenz", "BPK"]
    date_filter = 'today-1weeks'  # Using the recommended date format
    output_directory = '/app/results/%(title)s.%(ext)s'
    
    if not os.path.exists('/app/results'):
        os.makedirs('/app/results')
    
    # Create a case-insensitive regex pattern from the search keywords
    match_title_regex = '(?i)' + '|'.join(search_keywords)
    
    # Set up logging
    logging.basicConfig(filename='/app/results/download.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    
    command = (
        f'yt-dlp '
        f'--verbose '
        f'--match-title "{match_title_regex}" '
        f'--date {date_filter} '
        f'-o "{output_directory}" '
        f'-f bestaudio '
        f'"{channel_url}"'
    )
    
    logging.info(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    logging.info(f"stdout: {result.stdout}")
    if result.stderr:
        logging.error(f"stderr: {result.stderr}")

@flow
def main():
    download_recent_pressekonferenz_videos()

if __name__ == "__main__":
    main()