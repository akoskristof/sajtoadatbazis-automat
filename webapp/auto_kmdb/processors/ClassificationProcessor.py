from os import environ
from typing import Any
from numpy import ndarray
from sklearn.svm import SVC
from transformers.tokenization_utils_base import BatchEncoding
from huggingface_hub import hf_hub_download
from auto_kmdb.processors import Processor
from time import sleep
from transformers import (
    BertForSequenceClassification,
    BertTokenizer,
    PreTrainedTokenizer,
    PreTrainedModel,
)
import torch.nn.functional as F
from auto_kmdb import db
from joblib import load
import torch
import logging
import gc
import traceback

CATEGORY_MAP: dict[str, int] = {"hungarian-news": 0, "eu-news": 1, "world-news": 2}


def format_article(title, description, url):
    domain = ".".join(url.split("/")[2].split(".")[-2:])
    return f"{title}\n{description}\n({domain})"


class ClassificationProcessor(Processor):
    def __init__(self) -> None:
        logging.info("Initializing classification processor")
        self.done: bool = False
        self.model: PreTrainedModel
        self.tokenizer: PreTrainedTokenizer
        self.svm_classifier: SVC

    def is_done(self) -> bool:
        return self.done

    def load_model(self) -> None:
        logging.info("Loading classification model")
        self.model = BertForSequenceClassification.from_pretrained(
            "K-Monitor/kmdb_classification_hubert_v2"
        ).to(environ.get("DEVICE", "cpu"))
        self.tokenizer = BertTokenizer.from_pretrained(
            "SZTAKI-HLT/hubert-base-cc", max_length=512
        )
        self.svm_classifier = load(
            hf_hub_download(
                repo_id="K-Monitor/kmdb_classification_category_v2",
                filename="svm_classifier_category.joblib",
            )
        )
        self.done = True
        logging.info("Classification model loaded")

    def _prepare_input(self, text) -> BatchEncoding:
        """Prepares the input for prediction."""
        return self.tokenizer(text, return_tensors="pt")

    def _extract_outputs(self, inputs) -> tuple[ndarray, ndarray]:
        """Extracts logits and CLS embedding from model outputs."""
        output = self.model(**inputs, output_hidden_states=True)
        cls_embedding: ndarray = (
            output.hidden_states[-1][:, 0, :].squeeze().cpu().numpy()
        )
        return output.logits, cls_embedding

    def predict(self, text: str) -> tuple[int, float, int]:
        logging.info("Running classification prediction")
        inputs = self._prepare_input(text).to(environ.get("DEVICE", "cpu"))

        score: float
        label: int
        category: int
        with torch.no_grad():
            logits, cls_embedding = self._extract_outputs(inputs)

            probabilities = F.softmax(logits[0], dim=-1)
            score = float(probabilities[1])
            label = 1 if score > 0.42 else 0
            category = CATEGORY_MAP.get(
                self.svm_classifier.predict([cls_embedding])[0], 0
            )

        del inputs, logits, probabilities
        return label, score, category

    def _save_classification(self, connection, next_row, label, score, category):
        """Saves the classification result to the database."""
        if next_row["source"] == 1:
            db.save_classification_step(connection, next_row["id"], 1, 1.0, category)
        else:
            db.save_classification_step(
                connection, next_row["id"], label, score, category
            )

    def process_next(self):
        with db.connection_pool.get_connection() as connection:
            next_rows = db.get_classification_queue(connection)

        for next_row in next_rows:
            if next_row is None:
                sleep(30)
                return

            logging.info("Processing next classification")
            text: str = format_article(
                next_row["title"], next_row["description"], next_row["clean_url"]
            )

            try:
                label, score, category = self.predict(text)
                with db.connection_pool.get_connection() as connection:
                    self._save_classification(
                        connection, next_row, label, score, category
                    )
            except Exception as e:
                with db.connection_pool.get_connection() as connection:
                    db.skip_processing_error(connection, next_row["id"])

                logging.warning(f"Exception during: {next_row['id']}")
                logging.error(e)
                logging.error(traceback.format_exc())

        torch.cuda.empty_cache()
        gc.collect()
