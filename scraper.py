import asyncio
import os
import datetime
import urllib.parse
import pandas as pd
from playwright.async_api import async_playwright

async def scrape_indeed():
    # SETUP
    API_KEY = os.getenv('PROXY_API_KEY') # Get from GitHub Secrets
    MAX_PAGES = 3 
    all_jobs = []
    
    async with async_playwright() as p:
        is_github = os.getenv('GITHUB_ACTIONS') == 'true'
        browser = await p.chromium.launch(headless=is_github)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for current_page in range(MAX_PAGES):
            start_val = current_page * 10
            # Your specific URL for Remote Software Devs in the US
            base_url = f"https://www.indeed.com/jobs?q=software+developer&l=United+States&sc=0kf%3Aattr%28DSQF7%29%3B&fromage=1&sort=date&start={start_val}"
            
            # Proxy bypass logic
            if API_KEY:
                encoded_url = urllib.parse.quote(base_url)
                final_url = f"https://proxy.scrapeops.io/v1/?api_key={API_KEY}&url={encoded_url}"
            else:
                final_url = base_url

            print(f"Scraping Page {current_page + 1}...")
            
            try:
                await page.goto(final_url, timeout=60000)
                await page.wait_for_selector('.job_seen_beacon', timeout=15000)
                
                cards = await page.query_selector_all('.job_seen_beacon')
                for card in cards:
                    title_el = await card.query_selector('h2.jobTitle span[title]')
                    company_el = await card.query_selector('[data-testid="company-name"]')
                    link_el = await card.query_selector('h2.jobTitle a')
                    
                    href = await link_el.get_attribute('href') if link_el else ""
                    full_link = f"https://www.indeed.com{href}" if href.startswith('/') else href

                    all_jobs.append({
                        "Date Found": datetime.date.today().strftime("%Y-%m-%d"),
                        "Title": await title_el.inner_text() if title_el else "N/A",
                        "Company": await company_el.inner_text() if company_el else "N/A",
                        "Link": f'<a href="{full_link}" target="_blank">Apply</a>'
                    })
                await asyncio.sleep(2) 
            except Exception as e:
                print(f"Stopped at page {current_page + 1}: {e}")
                break

        # SAVE DATA
        if all_jobs:
            df = pd.DataFrame(all_jobs)
            # CSV Storage
            file_path = 'indeed_jobs.csv'
            df.to_csv(file_path, mode='a', index=False, header=not os.path.exists(file_path))
            
            # HTML for GitHub Pages
            generate_html()
            
        await browser.close()

def generate_html():
    if not os.path.exists('indeed_jobs.csv'):
        return
    
    df = pd.read_csv('indeed_jobs.csv').drop_duplicates(subset=['Title', 'Company'], keep='last')
    # Show last 200 jobs, newest first
    df = df.tail(200).iloc[::-1]
    
    html_table = df.to_html(classes='display nowrap', id='jobsTable', index=False, escape=False)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Job Tracker</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
        <style>
            body {{ font-family: -apple-system, sans-serif; margin: 40px; background: #f9f9f9; }}
            .container {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h1 {{ color: #161c2d; }}
        </style>
    </head>
    <body>
        <h1>Indeed Remote Software Jobs (Last 24h)</h1>
        <div class="container">{html_table}</div>
        <script src="https://code.jquery.com/jquery-3.7.0.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <script>$(document).ready(function() {{ $('#jobsTable').DataTable({{ pageLength: 50, responsive: true }}); }});</script>
    </body>
    </html>
    """
    with open("index.html", "w") as f:
        f.write(html_content)

if __name__ == "__main__":
    asyncio.run(scrape_indeed())
