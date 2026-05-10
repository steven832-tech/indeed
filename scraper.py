import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import datetime

async def scrape_indeed():
    async with async_playwright() as p:
        # Standard user-agent to avoid immediate "Bot" detection
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=user_agent)
        page = await context.new_page()

        # Your specific URL
        url = "https://www.indeed.com/jobs?q=software+developer&l=United+States&sc=0kf%3Aattr%28DSQF7%29%3B&fromage=1&sort=date"
        
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded")

        # Wait for the job cards to appear
        try:
            await page.wait_for_selector('.job_seen_beacon', timeout=10000)
        except:
            print("Timeout: Job cards not found. Indeed might be blocking the GitHub IP.")
            await browser.close()
            return

        jobs = []
        cards = await page.query_selector_all('.job_seen_beacon')

        for card in cards:
            # Indeed uses data-testid for more stable selectors
            title_el = await card.query_selector('h2.jobTitle span[title]')
            company_el = await card.query_selector('[data-testid="company-name"]')
            location_el = await card.query_selector('[data-testid="text-location"]')
            link_el = await card.query_selector('h2.jobTitle a')

            title = await title_el.inner_text() if title_el else "N/A"
            company = await company_el.inner_text() if company_el else "N/A"
            location = await location_el.inner_text() if location_el else "N/A"
            
            # Get the job link
            href = await link_el.get_attribute('href') if link_el else ""
            full_link = f"https://www.indeed.com{href}" if href.startswith('/') else href

            jobs.append({
                "date_scraped": datetime.date.today(),
                "title": title,
                "company": company,
                "location": location,
                "link": full_link
            })

        # Save to CSV (appends if it exists)
        df = pd.DataFrame(jobs)
        df.to_csv('indeed_jobs.csv', mode='a', header=not pd.io.common.file_exists('indeed_jobs.csv'), index=False)
        
        print(f"Success! Extracted {len(jobs)} jobs.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_indeed())
