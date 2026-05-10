import asyncio
from playwright.async_api import async_playwright
import pandas as pd

async def run():
    async with async_playwright() as p:
        # Launch browser (headless for Github Actions)
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Go to Indeed (change the URL for your region)
        url = "https://www.indeed.com/jobs?q=software+engineer&l=New+York"
        await page.goto(url)
        
        # Wait for job cards to load
        await page.wait_for_selector('.job_seen_beacon')
        
        jobs = []
        job_cards = await page.query_selector_all('.job_seen_beacon')
        
        for card in job_cards:
            title = await card.query_selector('h2.jobTitle')
            company = await card.query_selector('[data-testid="company-name"]')
            
            jobs.append({
                'title': await title.inner_text() if title else 'N/A',
                'company': await company.inner_text() if company else 'N/A'
            })
            
        # Save to CSV
        df = pd.DataFrame(jobs)
        df.to_csv('jobs.csv', index=False)
        print(f"Found {len(jobs)} jobs. Saved to jobs.csv")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
