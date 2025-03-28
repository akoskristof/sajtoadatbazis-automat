from typing import Optional
from auto_kmdb.newspapers.Newspaper import Newspaper
from bs4 import BeautifulSoup
from urllib.parse import urlparse


class Mediaworks(Newspaper):
    def is_url_this(self, url: str, html: str) -> bool:
        return urlparse(url).netloc in [
            "www.baon.hu",
            "www.bama.hu",
            "www.beol.hu",
            "www.boon.hu",
            "www.delmagyar.hu",
            "www.duol.hu",
            "www.feol.hu",
            "www.haon.hu",
            "www.heol.hu",
            "www.szoljon.hu",
            "www.kemma.hu",
            "www.nool.hu",
            "www.sonline.hu",
            "www.szon.hu",
            "www.teol.hu",
            "www.vaol.hu",
            "www.veol.hu",
            "www.zaol.hu",
            "mandiner.hu",
            "magyarnemzet.hu",
            "szabadfold.hu",
            "www.origo.hu",
            "www.vg.hu",
            "www.borsonline.hu",
            "ripost.hu",
            "metropol.hu",
        ]

    def get_description(self, url: str, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, "html.parser")
        lead_p = soup.select_one("p.lead")
        if lead_p:
            return lead_p.text
        return None

    def get_text(self, url: str, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        paragraphs = soup.select(
            ".block-content p, .block-content li, .article-text-formatter p, .article-text-formatter li"
        )

        parsed_text: list[str] = []
        for p in paragraphs:
            text_parts = []
            for element in p.contents:
                if element.name == "a":
                    link_text = element.get_text(strip=True)
                    if link_text:
                        text_parts.append(link_text)
                elif element.string is not None:
                    clean_text = element.string.strip()
                    if clean_text:
                        text_parts.append(clean_text)

            combined_text = " ".join(text_parts)
            if combined_text:
                parsed_text.append(combined_text)

        return "\n".join(parsed_text)
