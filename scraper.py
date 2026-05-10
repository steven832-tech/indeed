# scraper.py

import asyncio
import os
import datetime
import urllib.parse
import pandas as pd
from playwright.async_api import async_playwright


MAX_PAGES = 3


async def scrape_indeed():
    API_KEY = os.getenv("PROXY_API_KEY")
    all_jobs = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox"
            ]
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768}
        )

        page = await context.new_page()

        # Hide Playwright detection
        await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
        """)

        for current_page in range(MAX_PAGES):

            start_val = current_page * 10

            base_url = (
                "https://www.indeed.com/jobs?"
                "q=software+developer"
                "&l=United+States"
                "&fromage=1"
                "&sort=date"
                f"&start={start_val}"
            )

            # Use ZenRows if API key exists
            if API_KEY:
                encoded_url = urllib.parse.quote(base_url)

                final_url = (
                    "https://api.zenrows.com/v1/"
                    f"?apikey={API_KEY}"
                    f"&url={encoded_url}"
                    "&js_render=true"
                    "&premium_proxy=true"
                )
            else:
                final_url = base_url

            print(f"\nScraping page {current_page + 1}")
            print(final_url)

            try:
                await page.goto(
                    final_url,
                    wait_until="domcontentloaded",
                    timeout=120000
                )

                await page.wait_for_timeout(5000)

                # Debug screenshot
                await page.screenshot(
                    path=f"debug_page_{current_page + 1}.png",
                    full_page=True
                )

                # Try multiple selectors
                try:
                    await page.wait_for_selector(
                        ".job_seen_beacon, [data-testid='slider_item']",
                        timeout=30000
                    )
                except:
                    print("No jobs selector found")
                    continue

                cards = await page.query_selector_all(
                    ".job_seen_beacon, [data-testid='slider_item']"
                )

                print(f"Found {len(cards)} cards")

                for card in cards:

                    try:
                        title_el = await card.query_selector("h2 a span")
                        company_el = await card.query_selector(
                            "[data-testid='company-name']"
                        )
                        link_el = await card.query_selector("h2 a")

                        title = (
                            await title_el.inner_text()
                            if title_el else "N/A"
                        )

                        company = (
                            await company_el.inner_text()
                            if company_el else "N/A"
                        )

                        href = (
                            await link_el.get_attribute("href")
                            if link_el else None
                        )

                        if href:
                            full_link = (
                                f"https://www.indeed.com{href}"
                                if href.startswith("/")
                                else href
                            )
                        else:
                            full_link = "#"

                        print(title, "-", company)

                        all_jobs.append({
                            "Date Found": datetime.date.today().strftime("%Y-%m-%d"),
                            "Job Title": title,
                            "Company": company,
                            "Link": (
                                f'<a href="{full_link}" '
                                f'target="_blank" '
                                f'class="apply-link">Apply Now</a>'
                            )
                        })

                    except Exception as e:
                        print("Card parsing failed:", e)

                await asyncio.sleep(3)

            except Exception as e:
                print("Page failed:", e)

        await browser.close()

    if all_jobs:

        df = pd.DataFrame(all_jobs)

        if os.path.exists("indeed_jobs.csv"):

            old_df = pd.read_csv("indeed_jobs.csv")

            df = pd.concat([old_df, df]).drop_duplicates(
                subset=["Job Title", "Company"],
                keep="last"
            )

        df.to_csv("indeed_jobs.csv", index=False)

        generate_html(df)

        print(f"\nSUCCESS: {len(all_jobs)} jobs saved")

    else:
        print("\nNo jobs found")


def generate_html(df):

    df_display = df.tail(200).iloc[::-1]

    html_table = df_display.to_html(
        classes="display nowrap",
        id="jobsTable",
        index=False,
        escape=False
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <title>Indeed Jobs Tracker</title>

    <link rel="stylesheet"
          href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">

    <style>

        body {{
            font-family: Arial, sans-serif;
            background: #f4f7f6;
            margin: 40px;
        }}

        .container {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        }}

        h1 {{
            text-align: center;
            color: #2557a7;
            margin-bottom: 25px;
        }}

        table {{
            width: 100%;
        }}

        .apply-link {{
            background: #2557a7;
            color: white !important;
            padding: 6px 15px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 13px;
            font-weight: bold;
        }}

        .apply-link:hover {{
            background: #1c3d7a;
        }}

    </style>
</head>

<body>

    <h1>Indeed Remote Software Jobs Tracker</h1>

    <div class="container">
        {html_table}
    </div>

    <script src="https://code.jquery.com/jquery-3.7.0.js"></script>

    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>

    <script>

        $(document).ready(function() {{

            $('#jobsTable').DataTable({{
                pageLength: 50,
                order: [[0, "desc"]]
            }});

        }});

    </script>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == "__main__":
    asyncio.run(scrape_indeed())
