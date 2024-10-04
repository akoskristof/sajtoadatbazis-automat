from dotenv import load_dotenv

from webapp.auto_kmdb.Processor import Processor

load_dotenv("data/.env")

from flask import Flask
from threading import Thread
from time import sleep

sleep(10)  # TODO better wait handling
from auto_kmdb.DownloadProcessor import (
    DownloadProcessor,
    do_retries,
)
from auto_kmdb.ClassificationProcessor import ClassificationProcessor
from auto_kmdb.NERProcessor import NERProcessor
from auto_kmdb.KeywordProcessor import KeywordProcessor
from auto_kmdb.rss_watcher import rss_watcher
import logging


logger: logging.Logger = logging.getLogger(__name__)


def create_app() -> Flask:
    logfile = "data/log.txt"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filename=logfile,
    )

    for _ in range(10):
        logger.info("")
    logger.info("Started")

    app = Flask(
        __name__,
        instance_relative_config=True,
    )

    with app.app_context():
        from auto_kmdb.routes import api

        app.register_blueprint(api)
        logger.info("registered api")

    Thread(target=rss_watcher, args=(app.app_context(),), daemon=True).start()
    Thread(target=do_retries, args=(app.app_context(),), daemon=True).start()

    processors: list[Processor] = [
        DownloadProcessor(),
        ClassificationProcessor(),
        NERProcessor(),
        KeywordProcessor(),
    ]
    for processor in processors:
        processor.load_model()
        Thread(target=processor.process_loop, args=(), daemon=True).start()

    @app.route("/hello")
    def hello():
        return "Hello, World!"

    return app


app = create_app()
