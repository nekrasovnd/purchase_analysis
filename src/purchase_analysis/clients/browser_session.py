from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright, BrowserContext, Page, Playwright
from playwright_stealth import stealth

logger = logging.getLogger(__name__)

class BrowserResponse:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url

    def json(self) -> Any:
        import json
        from bs4 import BeautifulSoup
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            soup = BeautifulSoup(self.text, "lxml")
            return json.loads(soup.get_text())

    def raise_for_status(self) -> None:
        pass


class BrowserSession:
    def __init__(self, user_data_dir: str | Path, headless: bool = False, timeout: int = 30):
        self.user_data_dir = Path(user_data_dir).resolve()
        self.headless = headless
        self.timeout = timeout * 1000  # Playwright timeouts are in milliseconds
        
        self._playwright_context = sync_playwright()
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> BrowserSession:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    def start(self) -> None:
        self._playwright = self._playwright_context.__enter__()
        
        self.user_data_dir.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Launching persistent browser context at {self.user_data_dir}")
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        self._context.set_default_timeout(self.timeout)
        self._page = self._context.new_page()
        from playwright_stealth import Stealth
        Stealth().apply_stealth_sync(self._page)

    def stop(self) -> None:
        if self._context:
            self._context.close()
        if self._playwright_context:
            self._playwright_context.__exit__(None, None, None)

    def get(self, url: str, params: dict[str, str] | None = None, timeout: int | None = None) -> BrowserResponse:
        """
        Emulate requests.Session.get interface.
        """
        if not self._page:
            self.start()
        
        if params:
            from urllib.parse import urlencode
            query = urlencode(params)
            url = f"{url}?{query}"
            
        logger.info(f"Browser fetching: {url}")
        
        pw_timeout = (timeout * 1000) if timeout else self.timeout
        
        response = self._page.goto(url, timeout=pw_timeout, wait_until="domcontentloaded")
        if response is None:
            raise RuntimeError(f"Playwright got no response for {url}")
            
        # Give JS a moment if needed
        self._page.wait_for_timeout(2000)
        
        content = self._page.content()
        final_url = self._page.url
        
        return BrowserResponse(text=content, url=final_url)

    def _human_click(self, locator: Any) -> bool:
        """
        Attempts to click a locator like a human using raw mouse movements.
        """
        try:
            box = locator.bounding_box()
            if box:
                # Click in the center of the bounding box with slight random offset
                import random
                x = box["x"] + box["width"] / 2 + random.uniform(-2, 2)
                y = box["y"] + box["height"] / 2 + random.uniform(-2, 2)
                self._page.mouse.move(x, y, steps=10)
                self._page.wait_for_timeout(random.randint(100, 300))
                self._page.mouse.down()
                self._page.wait_for_timeout(random.randint(50, 150))
                self._page.mouse.up()
                return True
        except Exception as e:
            logger.debug(f"Human click failed: {e}")
        
        # Fallback to normal Playwright force click
        try:
            locator.click(force=True)
            return True
        except Exception:
            return False

    def _attempt_auto_resolve_challenge(self) -> bool:
        """
        Attempts to automatically click known captcha checkboxes (e.g. Yandex SmartCaptcha).
        Returns True if it made an attempt, False otherwise.
        """
        if not self._page:
            return False
            
        print(">>> Attempting to auto-resolve challenge (Yandex SmartCaptcha)...")
        try:
            clicked = False
            # Look for Yandex SmartCaptcha or Cloudflare iframe elements
            iframe_locators = self._page.locator("iframe[src*='captcha'], iframe[src*='smartcaptcha'], iframe[src*='cloudflare']")
            
            iframe_count = iframe_locators.count()
            if iframe_count > 0:
                print(f">>> Found {iframe_count} potential captcha iframes. Checking them...")
                
                for i in range(iframe_count):
                    if clicked: break
                    
                    frame_element = iframe_locators.nth(i)
                    frame = frame_element.content_frame
                    
                    print(f">>> Checking iframe {i+1}/{iframe_count}...")
                    
                    # Wait for the iframe to load its content
                    try:
                        frame.locator(".CheckboxCaptcha-Button, .CheckboxCaptcha-Checkbox, .SmartCaptcha-Checkbox, .recaptcha-checkbox, input[type='checkbox']").first.wait_for(state="visible", timeout=2000)
                    except Exception:
                        pass

                    # Try specific SmartCaptcha and reCAPTCHA classes
                    captcha_locators = [
                        ".CheckboxCaptcha-Button", 
                        ".CheckboxCaptcha-Checkbox", 
                        ".SmartCaptcha-Checkbox", 
                        ".recaptcha-checkbox",
                        "input[type='checkbox']"
                    ]
                    
                    for loc in captcha_locators:
                        if frame.locator(loc).count() > 0:
                            print(f">>> Found {loc} in iframe {i+1}. Attempting human click...")
                            target = frame.locator(loc).first
                            clicked = self._human_click(target)
                            break
                    
                    if not clicked:
                        print(f">>> No checkbox found in iframe {i+1}. Dumping HTML for debug...")
                        try:
                            html = frame.locator("body").inner_html()
                            with open(f"iframe_debug_{i+1}.html", "w", encoding="utf-8") as f:
                                f.write(html)
                            print(f">>> Dumped HTML to iframe_debug_{i+1}.html")
                        except Exception as html_err:
                            print(f">>> Failed to dump HTML: {html_err}")
                        
            if not clicked:
                # Try main page checkboxes if no frame found
                checkboxes = self._page.locator("input[type='checkbox']")
                if checkboxes.count() >= 1:
                    print(">>> Found checkbox(es) on main page. Attempting human click...")
                    target = checkboxes.first
                    clicked = self._human_click(target)

            if clicked:
                print(">>> Clicked captcha checkbox. Waiting for success...")
                self._page.wait_for_timeout(3000)
                
                # Click "Подтвердить" if present
                confirm_btn = self._page.locator("button:has-text('Подтвердить'), input[type='submit'][value='Подтвердить'], a:has-text('Подтвердить')").first
                if confirm_btn.count() > 0 and confirm_btn.is_visible():
                    print(">>> Found 'Подтвердить' button. Clicking...")
                    self._human_click(confirm_btn)
                    self._page.wait_for_timeout(3000)
                    
                return True
            else:
                print(">>> Could not find any clickable elements for auto-resolve.")
                
        except Exception as e:
            print(f">>> Auto-resolve error: {e}")
            
        return False

    def pause_for_challenge(self, reason: str = "Challenge detected") -> None:
        """
        Pauses the execution and asks the user to manually solve the CAPTCHA in the browser.
        First attempts to auto-solve if possible.
        """
        print(f"\n[!!!] {reason}")
        
        # 1. Try to auto-resolve
        if self._attempt_auto_resolve_challenge():
            print(">>> Auto-resolve attempted. Checking if challenge is cleared...")
            # We don't check for success here, the caller checks is_rate_limited_page again.
            # We return briefly. If caller sees it's still blocked, it will call pause_for_challenge again!
            # Wait, the caller loop has:
            # if hasattr(session, "pause_for_challenge"):
            #     session.pause_for_challenge(...)
            #     resp = session.current_page_content()
            #     if not blocked: break
            # To avoid an infinite loop if auto-solve fails, we should ONLY auto-solve once, or just pause manually right after.
            # Actually, to prevent infinite loops, we can ask for manual input if the page still has the challenge AFTER auto-solve.
            
            # Let's check page content right now
            self._page.wait_for_timeout(2000)
            text = self._page.content().lower()
            if not any(m in text for m in ("превышен максимальный лимит", "регламент площадки не допускает", "forbidden")):
                print(">>> Auto-resolve SUCCESS! Resuming automatically.")
                return

            print(">>> Auto-resolve failed or incomplete. Falling back to manual.")

        print(">>> Please switch to the opened browser window.")
        print(">>> Solve the CAPTCHA or pass the Cloudflare check.")
        print(">>> Make sure the page is fully loaded with actual data.")
        input(">>> Press Enter here in the terminal ONLY AFTER you have solved it...")
        print("Resuming...")
        
    def current_page_content(self) -> BrowserResponse:
        """
        Returns the current content of the page, useful after a manual challenge pause.
        Waits for the page to finish navigating before reading content.
        """
        if not self._page:
            raise RuntimeError("Browser not started")
        try:
            self._page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass  # timeout is fine — page may already be loaded
        try:
            self._page.wait_for_timeout(1500)  # extra buffer for JS redirects
            content = self._page.content()
            url = self._page.url
        except Exception:
            # If still navigating, wait a bit more and retry once
            self._page.wait_for_timeout(3000)
            content = self._page.content()
            url = self._page.url
        return BrowserResponse(text=content, url=url)
