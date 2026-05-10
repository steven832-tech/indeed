import asyncio
import os
import datetime
import urllib.parse
import pandas as pd
from playwright.async_api import async_playwright

async def scrape_indeed():
    # CONFIG
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
            # Target URL: Remote Software Dev, US, Last 24h
            base_url = f"https://www.indeed.com/jobs?q=software+developer&l=United+States&sc=0kf%3Aattr%28DSQF7%29%3B&fromage=1&sort=date&start={start_val}"
            
            if API_KEY:
                encoded_url = urllib.parse.quote(base_url)
                # ZenRows bypass flags
                final_url = f"https://api.zenrows.com/v1/?api_key={API_KEY}&url={encoded_url}&js_render=true&premium_proxy=true"
            else:
                final_url = base_url

            print(f"Scraping Page {current_page + 1} via ZenRows...")
            
            try:
                await page.goto(final_url, timeout=90000)
                await page.wait_for_selector('.job_seen_beacon', timeout=30000)
                
                cards = await page.query_selector_all('.job_seen_beacon')
                for card in cards:
                    title_el = await card.query_selector('h2.jobTitle span[title]')
                    company_el = await card.query_selector('[data-testid="company-name"]')
                    link_el = await card.query_selector('h2.jobTitle a')
                    
                    href = await link_el.get_attribute('href') if link_el else ""
                    full_link = f"https://www.indeed.com{href}" if href.startswith('/') else href

                    all_jobs.append({
                        "Date": datetime.date.today().strftime("%Y-%m-%d"),
                        "Title": await title_el.inner_text() if title_el else "N/A",
                        "Company": await company_el.inner_text() if company_el else "N/A",
                        "Link": f'<a href="{full_link}" target="_blank">Apply Now</a>'
                    })
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error on page {current_page + 1}: {e}")
                break

        if all_jobs:
            new_df = pd.DataFrame(all_jobs)
            file_path = 'indeed_jobs.csv'
            if os.path.exists(file_path):
                old_df = pd.read_csv(file_path)
                final_df = pd.concat([old_df, new_df]).drop_duplicates(subset=['Title', 'Company'], keep='last')
            else:
                final_df = new_df
            
            final_df.to_csv(file_path, index=False)
            generate_html(final_df)
            print("Job data saved and HTML generated.")
        
        await browser.close()

def generate_html(df):
    df_display = df.tail(200).iloc[::-1]
    html_table = df_display.to_html(classes='display', id='jobsTable', index=False, escape=False)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Indeed Remote Jobs</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
        <style>
            body {{ font-family: sans-serif; margin: 40px; background: #f8f9fa; }}
            .container {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #2557a7; text-align: center; }}
        </style>
    </head>
    <body>
        <h1>Indeed Remote Software Jobs</h1>
        <div class="container">{html_table}</div>
        <script src="https://code.jquery.com/jquery-3.7.0.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <script>$(document).ready(function() {{ $('#jobsTable').DataTable({{ pageLength: 50 }}); }});</script>
    </body>
    </html>
    """
    with open("index.html", "w") as f:
        f.write(html_content)

if __name__ == "__main__":
    asyncio.run(scrape_indeed())
