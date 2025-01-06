import requests
from print import print
from datetime import datetime, timedelta
from opol import OPOL
from prefect import task, flow
from transformers import AutoModel
import numpy as np
t


API_URL = "https://search.dip.bundestag.de/api/v1/plenarprotokoll"
API_KEY = "I9FKdCn.hbfefNWCY336dL6x62vfwNKpoN2RZ1gp21" # Public Api Key for Bundestag API

# Label definitions
LABEL_KEYWORDS_EXTENDED = [
    ("Wirtschaft", 0),
    ("Gesundheit", 1),
    ("Bildung", 2),
    ("Umwelt", 3),
    ("Verteidigung", 4),
    ("Protokoll", 5),
    ("Sitzung", 6),
    ("Bundesrat", 7),
    ("Finanzen", 8),
    ("Verkehr", 9),
    ("Soziales", 10),
    ("Arbeit", 11),
    ("Energie", 12),
    ("Klima", 13),
    ("Kultur", 14),
    ("Recht", 15),
    ("Politik", 16),   ### News classifications
    ("Krieg", 17),
    ("Konfliktereignisse", 18),
    ("Aufdeckung", 21),
    ("Kriminalität", 22),
    ("Korruption", 23),
    ("Wissenschaft", 24),
    ("Technologie", 25),
    ("Bundestag Protokoll", 26),
    ("Bundestag Gesetzesentwurf", 27),
    ("Bundestag Bericht", 28),
    ("Bundestag Antrag", 29)
]

DEFAULT_LABEL = 5  # Other

# Existing tasks
@task
def get_article_for_bundestag(date: str):
    opol = OPOL(api_key="kgfWztuskTnN6b27", mode="remote")
    articles = opol.search.engine(f"Nachrichten aus dem Bundestag {date}")
    print("Fetching articles for Bundestag:")
    for article in articles[:1]:
        print(article)
    return articles

@task
def get_relevant_documents(past_days: int = 7):
    print(f"Fetching Bundestag documents from the past {past_days} days...")

    end_date = datetime.today()
    start_date = end_date - timedelta(days=past_days)
    params = {
        'f.datum.start': start_date.strftime('%Y-%m-%d'),
        'f.datum.end': end_date.strftime('%Y-%m-%d'),
        'apikey': API_KEY,
        'sort': 'datum desc'
    }

    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        documents = data.get('documents', [])
        if not documents:
            print("No documents found in the specified date range.")
            return []
        print(f"Documents from {params['f.datum.start']} to {params['f.datum.end']}:")
        for doc in documents:
            title = doc.get('titel')
            date = doc.get('datum')
            if title and date:
                print(f"- [{date}] {title}")
        return documents
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return []
    except Exception as err:
        print(f"An error occurred: {err}")
        return []


@task
def embedd_texts(texts: list[str]):
    model = AutoModel.from_pretrained("jinaai/jina-embeddings-v3", trust_remote_code=True)
    embeddings = model.encode(texts, task='classification')
    return embeddings


@flow
def bunestag_daily():
    print("Starting bunestag_daily flow...")
    date = datetime.today().strftime('%Y-%m-%d')
    articles = get_article_for_bundestag(date)
    documents = get_relevant_documents(past_days=60)

    article_embeddings = embedd_texts([article.title + " " + article.content for article in articles])
    document_embeddings = embedd_texts([doc.get('titel') for doc in documents])

    label_embeddings = embedd_texts([label for label, _ in LABEL_KEYWORDS_EXTENDED])

    article_classifications = []
    for article_embedding in article_embeddings:
        similarities = [float(article_embedding @ label_embedding.T) for label_embedding in label_embeddings]
        article_classifications.append(max(range(len(similarities)), key=lambda i: similarities[i]))

    articles_with_translated_labels = []
    for article, label in zip(articles, article_classifications):
        article_dict = article.dict()
        lean_article = {
            'title': article_dict['title'],
            'content': article_dict['content'][:40],
        }
        lean_article['label'] = LABEL_KEYWORDS_EXTENDED[label][0]
        articles_with_translated_labels.append(lean_article)

    print(articles_with_translated_labels)

    document_classifications = []
    for document_embedding in document_embeddings:
        similarities = [float(document_embedding @ label_embedding.T) for label_embedding in label_embeddings]
        document_classifications.append(max(range(len(similarities)), key=lambda i: similarities[i]))

    documents_with_translated_labels = []
    for document, label in zip(documents, document_classifications):
        document = {k: v for k, v in document.items() if k in ["titel", "inhalt"]}
        document['label'] = LABEL_KEYWORDS_EXTENDED[label][0]
        documents_with_translated_labels.append(document)

    print(documents_with_translated_labels)


if __name__ == "__main__":
    bunestag_daily()