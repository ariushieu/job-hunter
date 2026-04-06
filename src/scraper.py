"""
Scraper module - Crawl job listings from Vietnamese job sites using Playwright + stealth.

Supported sites:
  - ITviec.com (Cloudflare protected - stealth + scroll bypass)
  - TopCV.vn (Vue.js SPA - direct URL search)
  - VietnamWorks.com (fallback)
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import httpx
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
    source: str  # "itviec" | "topcv" | "vietnamworks"
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
        """Scrape ITviec.com with Cloudflare bypass strategy.

        Strategy: search broad keywords ("java spring boot", "java spring")
        to get all Java jobs, then filter with _is_relevant_job() for
        intern/fresher positions. Narrow queries like "intern spring boot"
        return only senior results on ITviec.
        """
        jobs: list[Job] = []
        page: Optional[Page] = None

        # Broad search — ITviec returns 0 interns for "intern spring boot"
        # but 20+ results for "java spring boot" (includes interns)
        search_keywords = ["java spring boot", "java spring", "java intern"]

        try:
            page = await self._new_stealth_page()

            for kw_idx, keyword in enumerate(search_keywords):
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
                        "title_el": "h3[data-url]",
                        "link_attr": "data-url",
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

                # If got jobs from this keyword, skip remaining keywords
                if jobs:
                    logger.info("[ITviec] Got %d jobs from '%s', skipping remaining keywords", len(jobs), keyword)
                    break

                # Delay between keywords
                if kw_idx < len(search_keywords) - 1:
                    await self._random_delay(5, 10)

            logger.info("[ITviec] Scraped %d jobs", len(jobs))

        except Exception as e:
            logger.error("[ITviec] Scraping failed: %s", e, exc_info=True)
        finally:
            if page:
                await page.close()

        return jobs

    # ── TopCV ──────────────────────────────────

    async def scrape_topcv(self) -> list[Job]:
        """Scrape TopCV.vn using direct HTTP request + HTML parsing.

        TopCV's Vue.js SPA blocks headless browsers on VPS (returns ~6KB blank page).
        Instead, we fetch the search page via httpx with browser-like headers —
        TopCV server-renders enough HTML for job links even without JS execution.
        Fallback: try Playwright if httpx fails.
        """
        jobs: list[Job] = []

        search_keywords = ["java", "java-spring", "java-spring-boot"]

        try:
            ua = random.choice(config.USER_AGENTS)
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.topcv.vn/",
                "Connection": "keep-alive",
            }

            for kw_idx, keyword in enumerate(search_keywords):
                url = f"https://www.topcv.vn/tim-viec-lam-{keyword}?type_keyword=0&sba=1"
                logger.info("[TopCV] Fetching %s via httpx", url)

                async with httpx.AsyncClient(
                    timeout=30,
                    follow_redirects=True,
                    headers=headers,
                ) as client:
                    resp = await client.get(url)

                logger.info("[TopCV] Response: %d, %d chars", resp.status_code, len(resp.text))

                if resp.status_code != 200:
                    logger.warning("[TopCV] HTTP %d for keyword '%s'", resp.status_code, keyword)
                    continue

                html = resp.text

                # Parse job links from server-rendered HTML
                # TopCV SSR includes <a href="/viec-lam/{slug}/{id}.html"> with <h3> title
                import re

                # Find all job card blocks: <a href="/viec-lam/...html"...>...<h3...>TITLE</h3>...</a>
                # or standalone links with titles nearby
                seen: set[str] = set()

                # Pattern 1: extract href + title from links containing /viec-lam/*.html
                link_pattern = re.compile(
                    r'<a[^>]*href="([^"]*?/viec-lam/[^"]*?\.html)[^"]*"[^>]*>',
                    re.IGNORECASE,
                )
                title_pattern = re.compile(r'<h3[^>]*>(.*?)</h3>', re.IGNORECASE | re.DOTALL)

                # Find all job links and try to get titles
                for link_match in link_pattern.finditer(html):
                    href = link_match.group(1)

                    # Skip search/category links
                    if "/tim-viec-lam" in href:
                        continue

                    full_link = urljoin("https://www.topcv.vn", href)
                    full_link = full_link.split("?")[0]

                    if full_link in seen:
                        continue
                    seen.add(full_link)

                    # Look for <h3> title nearby (within next 500 chars)
                    search_start = link_match.start()
                    nearby_html = html[search_start:search_start + 500]
                    title_match = title_pattern.search(nearby_html)

                    if title_match:
                        # Strip HTML tags from title
                        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                    else:
                        # Fallback: extract from URL slug
                        slug = href.split("/viec-lam/")[-1].split("/")[0]
                        slug = re.sub(r'-\d+\.html$', '', slug)
                        title = slug.replace("-", " ").title()

                    if not title or len(title) < 5:
                        continue

                    if not _is_relevant_job(title):
                        logger.debug("[TopCV] Skipping irrelevant: %s", title[:60])
                        continue

                    jobs.append(Job(
                        title=title,
                        link=full_link,
                        source="topcv",
                    ))

                logger.info("[TopCV] Keyword '%s': found %d relevant jobs", keyword, len(jobs))

                # If first keyword got results, skip narrow ones
                if jobs and kw_idx == 0:
                    logger.info("[TopCV] Got %d jobs from broad search, skipping narrow keywords", len(jobs))
                    break

                # Delay between keywords
                if kw_idx < len(search_keywords) - 1:
                    await self._random_delay(2, 4)

            logger.info("[TopCV] Scraped %d jobs total", len(jobs))

        except Exception as e:
            logger.error("[TopCV] Scraping failed: %s", e, exc_info=True)

        return jobs

    # ── VietnamWorks (fallback) ────────────────

    async def scrape_vietnamworks(self) -> list[Job]:
        """Scrape VietnamWorks.com (React/Next.js SPA — needs networkidle).

        Strategy: search broad keyword "java" to get all Java jobs, then filter
        with _is_relevant_job() for intern/fresher positions.
        VietnamWorks renders job cards client-side via React — title text is
        NOT in the <a> inner_text (it's empty), so we use page.evaluate()
        to extract title + link from the rendered DOM via JavaScript.
        """
        jobs: list[Job] = []
        page: Optional[Page] = None

        # Broad search — "intern java" returns very few, "java" returns 50+
        search_keywords = ["java", "java spring boot"]

        try:
            page = await self._new_stealth_page()

            for kw_idx, keyword in enumerate(search_keywords):
                url = f"https://www.vietnamworks.com/viec-lam?q={keyword.replace(' ', '+')}&sort=date"
                logger.info("[VietnamWorks] Navigating to %s", url)

                # Use networkidle — React SPA needs JS execution + API calls
                await page.goto(url, wait_until="networkidle", timeout=45000)
                await self._random_delay(2, 4)
                await self._human_scroll(page, steps=3)
                await self._human_mouse_move(page, moves=2)
                await self._random_delay(1, 3)

                # Wait for React to render actual job cards (not skeleton loaders)
                try:
                    await page.wait_for_selector(
                        ".new-job-card, .block-job-list",
                        timeout=20000,
                    )
                except Exception:
                    logger.warning("[VietnamWorks] Job cards not rendered for '%s'", keyword)

                await self._human_scroll(page, steps=2)
                await self._random_delay(1, 2)

                # Use JavaScript to extract jobs — VietnamWorks React SPA
                # renders titles in elements where inner_text() from Playwright
                # returns empty. JS extraction is more reliable.
                raw_jobs = await page.evaluate("""() => {
                    const results = [];
                    // Strategy 1: .new-job-card with links
                    const cards = document.querySelectorAll('.new-job-card');
                    cards.forEach(card => {
                        // Find all <a> tags with job links (-jv suffix)
                        const links = card.querySelectorAll('a[href*="-jv"]');
                        links.forEach(a => {
                            const href = a.getAttribute('href') || '';
                            // Get title from: textContent of the <a>, or any h3/h2/span inside
                            let title = '';
                            const titleEl = a.querySelector('h3, h2, span');
                            if (titleEl) {
                                title = titleEl.textContent.trim();
                            }
                            if (!title) {
                                title = a.textContent.trim();
                            }
                            // Fallback: extract title from URL slug
                            if (!title && href) {
                                const slug = href.split('?')[0].replace(/-\\d+-jv$/, '').replace(/^\\//,'');
                                title = slug.replace(/-/g, ' ');
                            }
                            if (href && title) {
                                results.push({title, href});
                            }
                        });
                    });
                    // Strategy 2: any link with -jv pattern if strategy 1 fails
                    if (results.length === 0) {
                        const allLinks = document.querySelectorAll('a[href*="-jv"]');
                        allLinks.forEach(a => {
                            const href = a.getAttribute('href') || '';
                            let title = a.textContent.trim();
                            if (!title) {
                                const slug = href.split('?')[0].replace(/-\\d+-jv$/, '').replace(/^\\//,'');
                                title = slug.replace(/-/g, ' ');
                            }
                            if (href && title) {
                                results.push({title, href});
                            }
                        });
                    }
                    return results;
                }""")

                logger.info("[VietnamWorks] JS extracted %d raw job entries for '%s'", len(raw_jobs), keyword)

                seen: set[str] = set()
                for entry in raw_jobs:
                    title = entry.get("title", "").strip()
                    href = entry.get("href", "")

                    if not title or not href or len(title) < 5:
                        continue

                    full_link = urljoin("https://www.vietnamworks.com", href)
                    # Remove tracking params for dedup
                    full_link = full_link.split("?")[0]

                    if full_link in seen:
                        continue
                    seen.add(full_link)

                    if not _is_relevant_job(title):
                        logger.debug("[VietnamWorks] Skipping irrelevant: %s", title[:80])
                        continue

                    jobs.append(Job(
                        title=title,
                        link=full_link,
                        source="vietnamworks",
                    ))

                # If got jobs, skip remaining keywords
                if jobs:
                    logger.info("[VietnamWorks] Got %d jobs from '%s', skipping remaining keywords", len(jobs), keyword)
                    break

                # Delay between keywords
                if kw_idx < len(search_keywords) - 1:
                    await self._random_delay(5, 10)

            logger.info("[VietnamWorks] Scraped %d jobs", len(jobs))

        except Exception as e:
            logger.error("[VietnamWorks] Scraping failed: %s", e, exc_info=True)
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
