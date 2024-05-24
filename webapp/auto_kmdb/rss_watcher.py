import time
import feedparser
from auto_kmdb.options import skip_url_patterns
from auto_kmdb.db import check_url_exists, init_news, connection_pool, get_rss_urls
from auto_kmdb.preprocess import clear_url
import logging


def rss_watcher(app_context):
    logging.info('Started RSS watcher')
    app_context.push()
    with connection_pool.get_connection() as connection:
        newspapers = get_rss_urls(connection)
    while True:
        logging.info('checking feeds')
        for newspaper in newspapers:
            if newspaper['rss_url']:
                get_new_from_rss(newspaper)
        time.sleep(5*60)


def skip_url(url):
    return any(url.startswith(url_pattern) for url_pattern in skip_url_patterns)


def get_new_from_rss(newspaper):
    articles_found = 0
    feed = feedparser.parse(newspaper['rss_url'])
    for entry in feed.entries:
        clean_url = clear_url(entry.link)
        with connection_pool.get_connection() as connection:
            if not check_url_exists(connection, clean_url) and not skip_url(entry.link):
                init_news(connection, 'rss', entry.link, clean_url, newspaper['name'], newspaper['id'])
                articles_found += 1
    if articles_found > 0:
        print(newspaper['name'], 'found', articles_found, 'articles')
