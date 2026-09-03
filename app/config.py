from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URI: str
    MONGODB_DB_NAME: str = "dpdp_guard"
    CRAWLER_COLLECTION: str = "crawler_results"
    REPORTS_COLLECTION: str = "compliance_reports"
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3.6-flash"

    class Config:
        env_file = ".env"


settings = Settings()
