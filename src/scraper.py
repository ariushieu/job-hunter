"""
Scraper module - Crawl job listings from Vietnamese job sites using Playwright + stealth.

Supported sites:
  - ITviec.com (Cloudflare protected - stealth + scroll bypass)
  - TopCV.vn (Vue.js SPA - human-like search interaction)
  - VietnamWorks.com (fallback)
  - CareerBuilder.vn (fallback)
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright_stealth import Stealth

from src import config

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────
@dataclass
class Job:
    title: str
    link: str
    source: str  # "itviec" | "topcv" | "vietnamworks" | "careerbuilder"
    found_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "found_at": self.found_at,
        }


# ──────────────────────────────────────────────
# Keyword relevance filter
# ──────────────────────────────────────────────
# Job MUST contain at least one tech keyword (to avoid unrelated jobs like sales)
TECH_KEYWORDS = ["java", "spring", "backend", "back-end", "developer", "engineer", "lập trình"]
# Job MUST contain at least one level keyword (to filter out senior/lead positions)
LEVEL_KEYWORDS = ["intern", "thực tập", "fresher"]
# Negative keywords — immediately disqualify
EXCLUDE_KEYWORDS = ["senior", "lead", "manager", "principal", "architect", "staff", "expert", "trưởng"]


def _is_relevant_job(title: str) -> bool:
    """Check if a job title is an intern/fresher-level Java/Spring job.

    Rules:
      1. Must contain at least one TECH keyword (java, spring, backend, etc.)
      2. Must contain at least one LEVEL keyword (intern, fresher, junior, etc.)
      3. Must NOT contain any EXCLUDE keyword (senior, lead, manager, etc.)
    """
    title_lower = title.lower()

    # Rule 3: reject senior/lead/manager immediately
    if any(kw in title_lower for kw in EXCLUDE_KEYWORDS):
        return False

    # Rule 1: must be tech-related
    has_tech = any(kw in title_lower for kw in TECH_KEYWORDS)
    if not has_tech:
        return False

    # Rule 2: must be intern/fresher/junior level
    has_level = any(kw in title_lower for kw in LEVEL_KEYWORDS)
    return has_level


# ──────────────────────────────────────────────
# Main scraper class
# ──────────────────────────────────────────────
class JobScraper:
    """Playwright-based scraper with stealth and human-like behavior."""

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    # ── lifecycle ──────────────────────────────

    async def start(self) -> None:
        """Launch the stealth browser."""
        self._playwright = await async_playwright().start()
        ua = random.choice(config.USER_AGENTS)
        viewport = random.choice(config.VIEWPORT_SIZES)

        logger.info("Launching browser | UA: %s… | Viewport: %s", ua[:60], viewport)

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=ua,
            viewport=viewport,
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            java_script_enabled=True,
            ignore_https_errors=True,  # CareerBuilder.vn has expired SSL cert
        )

    async def stop(self) -> None:
        """Gracefully close browser resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def _new_stealth_page(self) -> Page:
        """Create a new page with stealth patches applied."""
        if not self._context:
            raise RuntimeError("Browser context not initialized. Call start() first.")
        page = await self._context.new_page()
        stealth = Stealth(
            navigator_languages_override=("vi-VN", "vi", "en-US", "en"),
            navigator_webdriver=True,
            chrome_runtime=True,
        )
        await stealth.apply_stealth_async(page)
        return page

    # ── human-like helpers ─────────────────────

    @staticmethod
    async def _random_delay(
        min_s: float = config.ACTION_DELAY_MIN,
        max_s: float = config.ACTION_DELAY_MAX,
    ) -> None:
        """Sleep a random duration to mimic human pauses."""
        delay = random.uniform(min_s, max_s)
        logger.debug("Sleeping %.1fs", delay)
        await asyncio.sleep(delay)

    @staticmethod
    async def _human_scroll(page: Page, steps: int = 3) -> None:
        """Scroll down gradually to trigger lazy loading and bypass CF sensors."""
        for i in range(steps):
            distance = random.randint(config.SCROLL_STEP_MIN, config.SCROLL_STEP_MAX)
            await page.mouse.wheel(0, distance)
            delay = random.uniform(config.SCROLL_DELAY_MIN, config.SCROLL_DELAY_MAX)
            await asyncio.sleep(delay)
            logger.debug("Scroll step %d/%d: %dpx", i + 1, steps, distance)

    @staticmethod
    async def _human_mouse_move(page: Page, moves: int = 3) -> None:
        """Move mouse randomly on the page to appear human."""
        for _ in range(moves):
            x = random.randint(100, 900)
            y = random.randint(100, 600)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.4))

    @staticmethod
    async def _human_type(page: Page, selector: str, text: str) -> None:
        """Type text character by character with random delays."""
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        for char in text:
            await page.keyboard.type(char, delay=random.randint(
                config.TYPING_DELAY_MIN, config.TYPING_DELAY_MAX
            ))

    # ── ITviec ─────────────────────────────────

    async def scrape_itviec(self) -> list[Job]:
        """Scrape ITviec.com with Cloudflare bypass strategy."""
        jobs: list[Job] = []
        page: Optional[Page] = None

        try:
            page = await self._new_stealth_page()
            keyword = random.choice(config.SEARCH_KEYWORDS[:3])
            url = f"https://itviec.com/it-jobs?query={keyword.replace(' ', '+')}"
            logger.info("[ITviec] Navigating to %s", url)

            await page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT)
            await self._random_delay(2, 4)

            # Critical: scroll to bypass Cloudflare sensor
            logger.info("[ITviec] Performing human-like scroll to bypass CF")
            await self._human_scroll(page, steps=4)
            await self._human_mouse_move(page, moves=3)
            await self._random_delay(2, 4)

            # Wait for content to appear after CF challenge
            # NOTE: avoid "networkidle" — Cloudflare keeps connections alive, causing timeout
            try:
                await page.wait_for_selector(
                    "div.job-card, div.job_content, a[href*='/it-jobs/']",
                    timeout=20000,
                )
            except Exception:
                logger.warning("[ITviec] Job selectors not found, page may be blocked")

            # Check if we got blocked (CF challenge page)
            page_content = await page.content()
            if "Just a moment" in page_content or "challenge-platform" in page_content:
                logger.warning("[ITviec] Cloudflare challenge detected, waiting...")
                await asyncio.sleep(8)
                await self._human_scroll(page, steps=2)
                await asyncio.sleep(3)

            # Try multiple selector strategies (sites change HTML often)
            # ITviec uses h3 with data-url attribute (NOT <a> inside h3)
            selector_chains = [
                # Strategy 1: current ITviec layout (2025-2026)
                # h3 has text=title and data-url=link
                {
                    "container": "div.job-card",
                    "title_el": "h3",
                    "link_attr": "data-url",  # special: link is in data-url on h3
                },
                # Strategy 2: fallback with <a> tags
                {
                    "container": "div.job_content, div[data-search-result]",
                    "title_el": "h3 a, h2 a, a[href*='/it-jobs/']",
                    "link_attr": "href",
                },
            ]

            for strategy_idx, strategy in enumerate(selector_chains):
                try:
                    containers = await page.query_selector_all(strategy["container"])
                    if not containers:
                        logger.debug(
                            "[ITviec] Strategy %d: no containers found with '%s'",
                            strategy_idx, strategy["container"],
                        )
                        continue

                    logger.info(
                        "[ITviec] Strategy %d: found %d job containers",
                        strategy_idx, len(containers),
                    )

                    for container in containers:
                        try:
                            el = await container.query_selector(strategy["title_el"])
                            if not el:
                                continue

                            title = (await el.inner_text()).strip()
                            href = await el.get_attribute(strategy["link_attr"])

                            if not title or not href:
                                continue

                            full_link = urljoin("https://itviec.com", href)

                            if not _is_relevant_job(title):
                                logger.debug("[ITviec] Skipping irrelevant: %s", title[:50])
                                continue

                            jobs.append(Job(
                                title=title,
                                link=full_link,
                                source="itviec",
                            ))
                        except Exception as e:
                            logger.debug("[ITviec] Error parsing single job card: %s", e)
                            continue

                    if jobs:
                        break  # Got results, stop trying other strategies

                except Exception as e:
                    logger.debug("[ITviec] Strategy %d failed: %s", strategy_idx, e)
                    continue

            logger.info("[ITviec] Scraped %d jobs", len(jobs))

        except Exception as e:
            logger.error("[ITviec] Scraping failed: %s", e, exc_info=True)
        finally:
            if page:
                await page.close()

        return jobs

    # ── TopCV ──────────────────────────────────

    async def scrape_topcv(self) -> list[Job]:
        """Scrape TopCV.vn by interacting like a real user (search from homepage)."""
        jobs: list[Job] = []
        page: Optional[Page] = None

        try:
            page = await self._new_stealth_page()
            logger.info("[TopCV] Navigating to homepage")

            # Step 1: Go to homepage
            await page.goto(
                "https://www.topcv.vn",
                wait_until="domcontentloaded",
                timeout=config.PAGE_LOAD_TIMEOUT,
            )
            await self._random_delay(2, 4)
            await self._human_scroll(page, steps=2)
            await self._human_mouse_move(page, moves=2)

            # Step 2: Find search box and type keyword like a human
            search_selectors = [
                "#keyword",
                "input[name='keyword']",
                "input[placeholder*='Tìm']",
                "input[placeholder*='tìm']",
                "input[type='text'][class*='search']",
                "input.input-search-job",
            ]

            search_input = None
            for sel in search_selectors:
                try:
                    search_input = await page.wait_for_selector(sel, timeout=5000)
                    if search_input:
                        logger.info("[TopCV] Found search input: %s", sel)
                        break
                except Exception:
                    continue

            if not search_input:
                logger.warning("[TopCV] Could not find search input, trying direct URL")
                await page.goto(
                    "https://www.topcv.vn/tim-viec-lam-intern-java-spring-boot",
                    wait_until="domcontentloaded",
                    timeout=config.PAGE_LOAD_TIMEOUT,
                )
                await self._random_delay(2, 3)
            else:
                # Type keyword like a human
                keyword = random.choice(config.SEARCH_KEYWORDS[:3])
                logger.info("[TopCV] Typing keyword: '%s'", keyword)

                await search_input.click()
                await asyncio.sleep(random.uniform(0.3, 0.8))

                # Clear any existing text
                await page.keyboard.press("Control+a")
                await asyncio.sleep(0.2)

                # Type character by character
                for char in keyword:
                    await page.keyboard.type(char, delay=random.randint(
                        config.TYPING_DELAY_MIN, config.TYPING_DELAY_MAX
                    ))

                await self._random_delay(0.5, 1.5)

                # Press Enter to search
                logger.info("[TopCV] Pressing Enter to search")
                await page.keyboard.press("Enter")

            # Step 3: Wait for results to render (Vue.js)
            # NOTE: avoid "networkidle" — Vue.js keeps background requests alive
            await self._random_delay(3, 5)
            try:
                await page.wait_for_selector(
                    ".job-item-search-result, .job-item, div[class*='job-item']",
                    timeout=20000,
                )
            except Exception:
                logger.warning("[TopCV] Job selectors not found after search")
            await self._human_scroll(page, steps=3)

            # Step 4: Extract job listings
            # TopCV uses h3 > a for title/link inside .job-item-search-result
            selector_chains = [
                # Strategy 1: current TopCV layout (2025-2026) — h3 contains <a> with title+link
                {
                    "container": ".job-item-search-result",
                    "title": "h3 a",
                    "title_attr": None,  # use inner_text for title
                },
                # Strategy 2: aria-label approach
                {
                    "container": ".job-item-search-result",
                    "title": "a[aria-label]",
                    "title_attr": "aria-label",
                },
                # Strategy 3: broad fallback
                {
                    "container": "div[class*='job-item']",
                    "title": "a[href*='/viec-lam/'], a[href*='/brand/'], a[href*='/tuyen-dung/']",
                    "title_attr": "aria-label",
                },
            ]

            for strategy_idx, strategy in enumerate(selector_chains):
                try:
                    containers = await page.query_selector_all(strategy["container"])
                    if not containers:
                        logger.debug(
                            "[TopCV] Strategy %d: no containers with '%s'",
                            strategy_idx, strategy["container"],
                        )
                        continue

                    logger.info(
                        "[TopCV] Strategy %d: found %d job containers",
                        strategy_idx, len(containers),
                    )

                    for container in containers:
                        try:
                            link_el = await container.query_selector(strategy["title"])
                            if not link_el:
                                continue

                            # Get title from aria-label attr or inner text
                            title_attr = strategy.get("title_attr")
                            if title_attr:
                                title = (await link_el.get_attribute(title_attr) or "").strip()
                            if not title_attr or not title:
                                title = (await link_el.inner_text()).strip()

                            href = await link_el.get_attribute("href")

                            if not title or not href:
                                continue

                            full_link = urljoin("https://www.topcv.vn", href)

                            if not _is_relevant_job(title):
                                logger.debug("[TopCV] Skipping irrelevant: %s", title[:50])
                                continue

                            jobs.append(Job(
                                title=title,
                                link=full_link,
                                source="topcv",
                            ))
                        except Exception as e:
                            logger.debug("[TopCV] Error parsing job card: %s", e)
                            continue

                    if jobs:
                        break

                except Exception as e:
                    logger.debug("[TopCV] Strategy %d failed: %s", strategy_idx, e)
                    continue

            # Check for empty results
            if not jobs:
                page_text = await page.inner_text("body")
                if "0 việc làm" in page_text or "không tìm thấy" in page_text.lower():
                    logger.info("[TopCV] No jobs found for this keyword")

            logger.info("[TopCV] Scraped %d jobs", len(jobs))

        except Exception as e:
            logger.error("[TopCV] Scraping failed: %s", e, exc_info=True)
        finally:
            if page:
                await page.close()

        return jobs

    # ── VietnamWorks (fallback) ────────────────

    async def scrape_vietnamworks(self) -> list[Job]:
        """Scrape VietnamWorks.com as a fallback source."""
        jobs: list[Job] = []
        page: Optional[Page] = None

        try:
            page = await self._new_stealth_page()
            keyword = random.choice(config.SEARCH_KEYWORDS[:2])
            url = f"https://www.vietnamworks.com/viec-lam?q={keyword.replace(' ', '+')}&sort=date"
            logger.info("[VietnamWorks] Navigating to %s", url)

            await page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT)
            await self._random_delay(2, 4)
            await self._human_scroll(page, steps=3)
            await self._human_mouse_move(page, moves=2)
            await self._random_delay(1, 3)

            selector_chains = [
                {
                    "container": "div[class*='JobCard'], div[class*='job-card']",
                    "title": "a[class*='title'], h3 a, h2 a, a[class*='job']",
                },
                {
                    "container": "div[class*='job-item'], div[class*='search-result']",
                    "title": "a[href*='vietnamworks.com'], a[href*='/job/'], h3 a, h2 a, a",
                },
                {
                    "container": "div.job-item, li.job-item, div[class*='result']",
                    "title": "a[href*='-jv'], a[href*='/job/'], a[href*='/viec-lam/'], a",
                },
            ]

            for strategy_idx, strategy in enumerate(selector_chains):
                try:
                    containers = await page.query_selector_all(strategy["container"])
                    if not containers:
                        continue

                    logger.info(
                        "[VietnamWorks] Strategy %d: found %d job containers",
                        strategy_idx, len(containers),
                    )

                    for container in containers:
                        try:
                            link_el = await container.query_selector(strategy["title"])
                            if not link_el:
                                continue

                            title = (await link_el.inner_text()).strip()
                            href = await link_el.get_attribute("href")

                            if not title or not href:
                                continue

                            full_link = urljoin("https://www.vietnamworks.com", href)

                            if not _is_relevant_job(title):
                                logger.debug("[VietnamWorks] Skipping irrelevant: %s", title[:50])
                                continue

                            jobs.append(Job(
                                title=title,
                                link=full_link,
                                source="vietnamworks",
                            ))
                        except Exception as e:
                            logger.debug("[VietnamWorks] Error parsing job card: %s", e)
                            continue

                    if jobs:
                        break

                except Exception as e:
                    logger.debug("[VietnamWorks] Strategy %d failed: %s", strategy_idx, e)
                    continue

            logger.info("[VietnamWorks] Scraped %d jobs", len(jobs))

        except Exception as e:
            logger.error("[VietnamWorks] Scraping failed: %s", e, exc_info=True)
        finally:
            if page:
                await page.close()

        return jobs

    # ── CareerBuilder (fallback) ───────────────

    async def scrape_careerbuilder(self) -> list[Job]:
        """Scrape CareerBuilder.vn as a fallback source."""
        jobs: list[Job] = []
        page: Optional[Page] = None

        try:
            page = await self._new_stealth_page()
            keyword = random.choice(config.SEARCH_KEYWORDS[:2])
            url = f"https://careerbuilder.vn/viec-lam/{keyword.replace(' ', '-')}-k-vi.html"
            logger.info("[CareerBuilder] Navigating to %s", url)

            await page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT)
            await self._random_delay(2, 4)
            await self._human_scroll(page, steps=3)
            await self._human_mouse_move(page, moves=2)
            await self._random_delay(1, 3)

            selector_chains = [
                {
                    "container": "div.job-item, div.job-list-default div.list-item",
                    "title": "a.job_link, a[class*='title'], h3.title a, h3 a, a",
                },
                {
                    "container": "div[class*='job'], li[class*='job']",
                    "title": "a[href*='careerbuilder.vn/vi/'], a[href*='/viec-lam/'], h3 a, a",
                },
            ]

            for strategy_idx, strategy in enumerate(selector_chains):
                try:
                    containers = await page.query_selector_all(strategy["container"])
                    if not containers:
                        continue

                    logger.info(
                        "[CareerBuilder] Strategy %d: found %d job containers",
                        strategy_idx, len(containers),
                    )

                    for container in containers:
                        try:
                            link_el = await container.query_selector(strategy["title"])
                            if not link_el:
                                continue

                            title = (await link_el.inner_text()).strip()
                            href = await link_el.get_attribute("href")

                            if not title or not href:
                                continue

                            full_link = urljoin("https://careerbuilder.vn", href)

                            if not _is_relevant_job(title):
                                logger.debug("[CareerBuilder] Skipping irrelevant: %s", title[:50])
                                continue

                            jobs.append(Job(
                                title=title,
                                link=full_link,
                                source="careerbuilder",
                            ))
                        except Exception as e:
                            logger.debug("[CareerBuilder] Error parsing job card: %s", e)
                            continue

                    if jobs:
                        break

                except Exception as e:
                    logger.debug("[CareerBuilder] Strategy %d failed: %s", strategy_idx, e)
                    continue

            logger.info("[CareerBuilder] Scraped %d jobs", len(jobs))

        except Exception as e:
            logger.error("[CareerBuilder] Scraping failed: %s", e, exc_info=True)
        finally:
            if page:
                await page.close()

        return jobs

    # ── Orchestrator ───────────────────────────

    async def scrape_all(self) -> list[Job]:
        """Scrape all sources. Each source is independent - one failure won't affect others."""
        all_jobs: list[Job] = []

        scrapers = [
            ("ITviec", self.scrape_itviec),
            ("TopCV", self.scrape_topcv),
            ("VietnamWorks", self.scrape_vietnamworks),
            ("CareerBuilder", self.scrape_careerbuilder),
        ]

        for name, scraper_fn in scrapers:
            try:
                logger.info("─── Starting %s scraper ───", name)
                jobs = await scraper_fn()
                all_jobs.extend(jobs)

                # Random delay between sites to look natural
                if name != scrapers[-1][0]:
                    await self._random_delay(5, 10)

            except Exception as e:
                logger.error("Scraper %s crashed unexpectedly: %s", name, e, exc_info=True)
                continue  # Never let one site crash the whole pipeline

        # Deduplicate by link within this run
        seen_links: set[str] = set()
        unique_jobs: list[Job] = []
        for job in all_jobs:
            if job.link not in seen_links:
                seen_links.add(job.link)
                unique_jobs.append(job)

        logger.info(
            "Total scraped: %d jobs (%d unique) from %d sources",
            len(all_jobs), len(unique_jobs), len(scrapers),
        )
        return unique_jobs
