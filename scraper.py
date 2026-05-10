import asyncio
import os
import datetime
import urllib.parse
import pandas as pd
from playwright.async_api import async_playwright

async def scrape_indeed():
    API_KEY = os.getenv('PROXY_API_KEY')
    MAX_PAGES = 3 
    all_jobs = []
    
    async with async_playwright() as p:
        is_github = os.getenv('GITHUB_ACTIONS') == 'true'
        browser = await p.chromium.launch(headless=is_github)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for current_page in range(MAX_PAGES):
            start_val = current_page * 10
            base_url = f"https://www.indeed.com/jobs?q=software+developer&l=United+States&sc=0kf%3Aattr%28DSQF7%29%3B&fromage=1&sort=date&start={start_val}"
            
            if API_KEY:
                encoded_url = urllib.parse.quote(base_url)
                final_url = f"https://api.zenrows.com/v1/?api_key={API_KEY}&url={encoded_url}&js_render=true&premium_proxy=true"
            else:
                final_url = base_url

            print(f"Scraping Page {current_page + 1}...")
            
            try:
                await page.goto(final_url, timeout=90000)
                await page.wait_for_selector('.job_seen_beacon', timeout=30000)
                
                cards = await page.query_selector_all('.job_seen_beacon')
                for card in cards:
                    title_el = await card.query_selector('h2.jobTitle span[title]')
                    company_el = await card.query_selector('[data-testid="company-name"]')
                    link_el = await card.query_selector('h2.jobTitle a')
                    
                    if link_el:
                        href = await link_el.get_attribute('href')
                        full_link = f"https://www.indeed.com{href}" if href.startswith('/') else href
                    else:
                        full_link = "#"

                    all_jobs.append({
                        "Date Found": datetime.date.today().strftime("%Y-%m-%d"),
                        "Job Title": await title_el.inner_text() if title_el else "N/A",
                        "Company": await company_el.inner_text() if company_el else "N/A",
                        "Link": f'<a href="{full_link}" target="_blank" class="apply-btn">Apply Now</a>'
                    })
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error: {e}")
                break

        if all_jobs:
            new_df = pd.DataFrame(all_jobs)
            # Purana data load karein agar exist karta hai
            if os.path.exists('indeed_jobs.csv'):
                old_df = pd.read_csv('indeed_jobs.csv')
                df = pd.concat([old_df, new_df]).drop_duplicates(subset=['Job Title', 'Company'], keep='last')
            else:
                df = new_df
            
            df.to_csv('indeed_jobs.csv', index=False)
            generate_html(df)
        
        await browser.close()

def generate_html(df):
    df_display = df.tail(200).iloc[::-1]
    # 'escape=False' zaroori hai taake HTML links (<a> tags) kaam karein
    html_table = df_display.to_html(classes='display nowrap', id='jobsTable', index=False, escape=False)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Indeed Tracker</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
        <style>
            body {{ font-family: sans-serif; margin: 40px; background: #f4f7f6; }}
            .container {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h1 {{ text-align: center; color: #2557a7; }}
            .apply-btn {{ background: #2557a7; color: white !important; padding: 5px 15px; border-radius: 4px; text-decoration: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Indeed Remote Software Jobs Tracker</h1>
        <div class="container">{html_table}</div>
        <script src="https://code.jquery.com/jquery-3.7.0.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <script>$(document).ready(function() {{ $('#jobsTable').DataTable({{ order: [[0, 'desc']] }}); }});</script>
    </body>
    </html>
    """
    with open("index.html", "w") as f:
        f.write(html_content)

if __name__ == "__main__":
    asyncio.run(scrape_indeed())
