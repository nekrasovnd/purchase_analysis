import argparse
import time
from pathlib import Path

from purchase_analysis.clients.browser_session import BrowserSession
from purchase_analysis.clients.b2b_center import MARKET_URL

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap a persistent Playwright session for B2B-Center."
    )
    parser.add_argument("--browser-profile", default=".local/b2b_profile", help="Path to persistent browser profile")
    args = parser.parse_args()

    print(f"Initializing browser session at {args.browser_profile}...")
    
    with BrowserSession(user_data_dir=args.browser_profile, headless=False) as session:
        print(f"Navigating to {MARKET_URL}...")
        resp = session.get(MARKET_URL)
        
        print("\n>>> Please switch to the opened browser window.")
        print(">>> Ensure you can access the page.")
        print(">>> If there is a CAPTCHA or Cloudflare challenge, solve it manually.")
        print(">>> Once you see the actual market search page, come back here.")
        input(">>> Press Enter in this terminal to save the session and exit...")
        
        print("\nSession saved. You can now run the sprint with --browser-profile and --resume.")

if __name__ == "__main__":
    main()
