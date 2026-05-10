import asyncio
import os
import datetime
import urllib.parse
import random
import pandas as pd
from playwright.async_api import async_playwright

MAX_PAGES = 3


async def safe_goto(page, url, retries=3):

    for attempt in range(retries):

        try:

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=120000
            )

            return True

        except Exception as e:

            print(f"[{datetime.datetime.now()}] Retry {attempt + 1} failed:", e)

            await asyncio.sleep(5)

    return False


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

        # Hide automation detection
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

            # Use ZenRows proxy if API key exists
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

            print(f"\n[{datetime.datetime.now()}] Scraping Page {current_page + 1}")

            try:

                success = await safe_goto(page, final_url)

                if not success:

                    print("Skipping page after retries")
                    continue

                await page.wait_for_timeout(random.randint(4000, 7000))

                # Safe screenshot
                try:

                    await page.screenshot(
                        path=f"debug_page_{current_page + 1}.png",
                        full_page=False,
                        timeout=15000
                    )

                except Exception as e:

                    print("Screenshot failed:", e)

                # Detect blocks/captcha
                content = await page.content()

                blocked_keywords = [
                    "captcha",
                    "verify you are human",
                    "access denied",
                    "blocked"
                ]

                if any(word in content.lower() for word in blocked_keywords):

                    print("Blocked by Indeed")

                    with open(
                        f"blocked_page_{current_page + 1}.html",
                        "w",
                        encoding="utf-8"
                    ) as f:
                        f.write(content)

                    continue

                # Wait for job cards
                try:

                    await page.wait_for_selector(
                        ".job_seen_beacon, [data-testid='slider_item']",
                        timeout=30000
                    )

                except:

                    print("No jobs found on page")
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

                        print("Card parse failed:", e)

                await asyncio.sleep(random.randint(3, 8))

            except Exception as e:

                print("Page failed:", e)

        await browser.close()

    # ALWAYS CREATE FILES

    if all_jobs:

        new_df = pd.DataFrame(all_jobs)

        if os.path.exists("indeed_jobs.csv"):

            old_df = pd.read_csv("indeed_jobs.csv")

            df = pd.concat([old_df, new_df]).drop_duplicates(
                subset=["Job Title", "Company", "Link"],
                keep="last"
            )

        else:

            df = new_df

        # Keep latest 3000 jobs
        df = df.tail(3000)

        print(f"\nSUCCESS: {len(all_jobs)} jobs saved")

    else:

        print("\nNo jobs found")

        # Keep existing data alive
        if os.path.exists("indeed_jobs.csv"):

            print("Loading old CSV")

            df = pd.read_csv("indeed_jobs.csv")

        else:

            print("Creating empty CSV")

            df = pd.DataFrame(columns=[
                "Date Found",
                "Job Title",
                "Company",
                "Link"
            ])

    # ALWAYS SAVE FILES

    df.to_csv("indeed_jobs.csv", index=False)

    df.to_json(
        "jobs.json",
        orient="records",
        indent=2
    )

    generate_html(df)


def generate_html(df):

    df_display = df.tail(200).iloc[::-1]

    if len(df_display) == 0:

        html_table = "<h2>No jobs found yet</h2>"

    else:

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

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Indeed Jobs Tracker</title>

    <link rel="stylesheet"
          href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">

    <style>

        body {{
            font-family: Arial, sans-serif;
            background: #f4f7f6;
            margin: 20px;
        }}

        .container {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            overflow-x: auto;
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

            if ($('#jobsTable').length) {{

                $('#jobsTable').DataTable({{
                    pageLength: 50,
                    order: [[0, "desc"]]
                }});

            }}

        }});

    </script>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:

        f.write(html_content)


if __name__ == "__main__":

    asyncio.run(scrape_indeed())
