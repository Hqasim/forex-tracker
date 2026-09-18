"""Scrapy settings for the forex_tracker project.

See https://docs.scrapy.org/en/latest/topics/settings.html for the full
reference.
"""

import os

BOT_NAME = "forex_tracker"

SPIDER_MODULES = ["forex_tracker.scraper.spiders"]
NEWSPIDER_MODULE = "forex_tracker.scraper.spiders"

# Identify the bot and where it can be reported, per Scrapy's crawling
# etiquette guidance.
USER_AGENT = "forex-tracker (+https://github.com/Hqasim/forex-tracker)"

# Compliance: this project only ever reads publicly published rate tables
# and honours robots.txt.
ROBOTSTXT_OBEY = True

# Be polite: throttle to the site's pace rather than hammering it, and back
# off automatically if it starts responding slowly.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1

RETRY_ENABLED = True
RETRY_TIMES = 3

ITEM_PIPELINES = {
    "forex_tracker.scraper.pipelines.ValidationPipeline": 100,
    "forex_tracker.scraper.pipelines.SQLModelPipeline": 300,
    "forex_tracker.scraper.pipelines.RetentionPipeline": 400,
}

LOG_LEVEL = "INFO"
FEED_EXPORT_ENCODING = "utf-8"

# Cache responses locally during development so iterating on selectors
# doesn't require re-hitting the live site. Off by default; opt in with
# `SCRAPY_HTTPCACHE_ENABLED=1 scrapy crawl rates`.
HTTPCACHE_ENABLED = os.environ.get("SCRAPY_HTTPCACHE_ENABLED") == "1"
HTTPCACHE_EXPIRATION_SECS = 3600
