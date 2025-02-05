import os

class ServiceConfig:
    ## Service Ports

    CORE_APP_PORT = os.getenv('CORE_APP_PORT', '8089')
    CLASSIFICATION_SERVICE_PORT = os.getenv('CLASSIFICATION_SERVICE_PORT', '5688')
    EMBEDDING_SERVICE_PORT = os.getenv('EMBEDDING_SERVICE_PORT', '0420')
    ENTITY_SERVICE_PORT = os.getenv('ENTITY_SERVICE_PORT', '1290')
    GEO_SERVICE_PORT = os.getenv('GEO_SERVICE_PORT', '3690')
    OLLAMA_PORT = os.getenv('OLLAMA_PORT', '11434')
    PELIAS_PLACEHOLDER_PORT = os.getenv('PELIAS_PLACEHOLDER_PORT', '3999')
    POSTGRES_SERVICE_PORT = os.getenv('POSTGRES_SERVICE_PORT', '5434')
    PREFECT_SERVER_PORT = os.getenv('PREFECT_SERVER_PORT', '4200')
    REDIS_PORT = os.getenv('REDIS_PORT', '6379')
    SCRAPER_SERVICE_PORT = os.getenv('SCRAPER_SERVICE_PORT', '8081')
    SEARXNG_PORT = os.getenv('SEARXNG_PORT', '8021')

    # Database configurations
    ARTICLES_DB_USER = os.getenv('ARTICLES_DB_USER', 'articles_user')
    ARTICLES_DB_PASSWORD = os.getenv('ARTICLES_DB_PASSWORD', 'articles_password')
    ARTICLES_DB_NAME = os.getenv('ARTICLES_DB_NAME', 'articles_db')
    ARTICLES_DB_PORT = os.getenv('ARTICLES_DB_PORT', '5473') ## THIS IS THE MAIN DATABASE
    DB_MODE = os.getenv('DB_MODE', 'managed')
    MANAGED_ARTICLES_DB_HOST = os.getenv('MANAGED_ARTICLES_DB_HOST', 'x')
    MANAGED_ARTICLES_DB_PORT = os.getenv('MANAGED_ARTICLES_DB_PORT', '5473')
    MANAGED_ARTICLES_DB_USER = os.getenv('MANAGED_ARTICLES_DB_USER', 'x')
    MANAGED_ARTICLES_DB_PASSWORD = os.getenv('MANAGED_ARTICLES_DB_PASSWORD', 'x')
    PREFECT_DB_USER = os.getenv('PREFECT_DB_USER', 'prefect_user')
    PREFECT_DB_PASSWORD = os.getenv('PREFECT_DB_PASSWORD', 'prefect_password')
    PREFECT_DB_NAME = os.getenv('PREFECT_DB_NAME', 'prefect_db')
    PREFECT_DB_PORT = os.getenv('PREFECT_DB_PORT', '5433')

    # Redis Mode
    REDIS_MODE = os.getenv('REDIS_MODE', 'managed')

    # Managed Redis Configuration
    MANAGED_REDIS_HOST = os.getenv('MANAGED_REDIS_HOST', 'x')
    MANAGED_REDIS_PORT = os.getenv('MANAGED_REDIS_PORT', '6379')

    # Determine if running in Kubernetes or Docker Compose
    RUNNING_ENV = os.getenv('RUNNING_ENV', 'compose')

    # Service URLs
    if RUNNING_ENV == 'kubernetes':
        service_urls = {
            "core-app": "http://app-opol-core",
            "service-postgres": "http://service-postgres",
            "service-embeddings": "http://service-embeddings",
            "service-scraper": "http://service-scraper",
            "service-entities": "http://service-entities",
            "service-geo": "http://service-geo",
            "redis": "redis://engine-redis",
            "prefect-server": "http://engine-prefect-server",
            "pelias-placeholder": "http://engine-pelias-placeholder",
            "ollama": "http://engine-ollama",
            "searxng": f"http://engine-searxng",
        }
    elif RUNNING_ENV == 'compose':
        service_urls = {
            "core-app": f"http://app-opol-core:{CORE_APP_PORT}",
            "service-postgres": f"http://service-postgres:{POSTGRES_SERVICE_PORT}",
            "service-embeddings": f"http://service-embeddings:{EMBEDDING_SERVICE_PORT}",
            "service-scraper": f"http://service-scraper:{SCRAPER_SERVICE_PORT}",
            "service-entities": f"http://service-entities:{ENTITY_SERVICE_PORT}",
            "service-geo": f"http://service-geo:{GEO_SERVICE_PORT}",
            "redis": f"redis://engine-redis:{REDIS_PORT}",
            "prefect-server": f"http://engine-prefect-server:{PREFECT_SERVER_PORT}",
            "pelias-placeholder": f"http://engine-pelias-placeholder:{PELIAS_PLACEHOLDER_PORT}",
            "ollama": f"http://engine-ollama:{OLLAMA_PORT}",
            "searxng": f"http://engine-searxng:{SEARXNG_PORT}",
        }
    elif RUNNING_ENV == 'local':
        service_urls = {
            "core-app": f"http://localhost:{CORE_APP_PORT}",
            "service-postgres": f"http://localhost:{POSTGRES_SERVICE_PORT}",
            "service-embeddings": f"http://localhost:{EMBEDDING_SERVICE_PORT}",
            "service-scraper": f"http://localhost:{SCRAPER_SERVICE_PORT}",
            "service-entities": f"http://localhost:{ENTITY_SERVICE_PORT}",
            "service-geo": f"http://localhost:{GEO_SERVICE_PORT}",
            "pelias-placeholder": f"http://localhost:{PELIAS_PLACEHOLDER_PORT}",
            "redis": f"redis://localhost:{REDIS_PORT}",
            "searxng": f"http://localhost:{SEARXNG_PORT}",
        }

    # Redis channel mappings with explicit types
    redis_queues = {
        "contents_without_embedding_queue": {"db": 5, "key": "contents_without_embedding_queue", "type": "list"},
        "contents_with_entities_queue": {"db": 2, "key": "contents_with_entities_queue", "type": "list"},
        "scrape_sources": {"db": 0, "key": "scrape_sources", "type": "list"},
        "raw_contents_queue": {"db": 1, "key": "raw_contents_queue", "type": "list"},
        "contents_with_embeddings": {"db": 6, "key": "contents_with_embeddings", "type": "list"},
        "contents_without_entities_queue": {"db": 2, "key": "contents_without_entities_queue", "type": "list"},
        "contents_without_geocoding_queue": {"db": 3, "key": "locations_without_geocoding_queue", "type": "list"},
        "contents_with_geocoding_queue": {"db": 4, "key": "contents_with_geocoding_queue", "type": "list"},
        "contents_without_classification_queue": {"db": 4, "key": "contents_without_classification_queue", "type": "list"},
        "contents_with_classification_queue": {"db": 4, "key": "contents_with_classification_queue", "type": "list"},
        "Orchestration_in_progress": {"db": 1, "key": "Orchestration_in_progress", "type": "string"},
        "scrapers_running": {"db": 1, "key": "scrapers_running", "type": "string"},
        "outward_irrelevant_queue": {"db": 7, "key": "outward_irrelevant_queue", "type": "list"},
        "failed_geocodes_queue": {"db": 6, "key": "failed_geocodes_queue", "type": "list"},
    }

config = ServiceConfig()

def get_db_url():
    """Get database URL based on mode"""
    if os.getenv('DB_MODE') == "managed":
        return (
            f"postgresql+asyncpg://{config.MANAGED_ARTICLES_DB_USER}:{config.MANAGED_ARTICLES_DB_PASSWORD}"
                f"@{config.MANAGED_ARTICLES_DB_HOST}:{config.MANAGED_ARTICLES_DB_PORT}/{config.ARTICLES_DB_NAME}"
            )
    else:
        return (
            f"postgresql+asyncpg://{config.ARTICLES_DB_USER}:{config.ARTICLES_DB_PASSWORD}"
                f"@database-articles:{config.ARTICLES_DB_PORT}/{config.ARTICLES_DB_NAME}"
            )

def get_redis_url():
    """Get Redis URL based on mode"""
    if os.getenv('REDIS_MODE') == "managed":
        return f"redis://{config.MANAGED_REDIS_HOST}:{config.MANAGED_REDIS_PORT}"
    else:
        return f"redis://engine-redis:{config.REDIS_PORT}"

def get_sync_db_url():
    """Get synchronous database URL for Alembic"""
    if os.getenv('DB_MODE') == "managed":
        return (
            f"postgresql://{config.MANAGED_ARTICLES_DB_USER}:{config.MANAGED_ARTICLES_DB_PASSWORD}"
                f"@{config.MANAGED_ARTICLES_DB_HOST}:{config.MANAGED_ARTICLES_DB_PORT}/{config.ARTICLES_DB_NAME}"
            )
    else:
            return (
                f"postgresql://{config.ARTICLES_DB_USER}:{config.ARTICLES_DB_PASSWORD}"
                f"@database-articles:{config.ARTICLES_DB_PORT}/{config.ARTICLES_DB_NAME}"
            )
