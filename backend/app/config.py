from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = ""
    sql_server: str = r"localhost\SQLEXPRESS"
    sql_database: str = "InvoiceAP"
    sql_driver: str = "ODBC Driver 18 for SQL Server"
    sql_trusted_connection: bool = True
    sql_user: str = ""
    sql_password: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""
    tesseract_path: str = ""
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 20
    max_pdf_pages: int = 30
    frontend_url: str = "http://localhost:5173"

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        # TrustServerCertificate=yes is needed for local Express with Driver 18 (self-signed cert).
        parts = [f"DRIVER={{{self.sql_driver}}}", f"SERVER={self.sql_server}", f"DATABASE={self.sql_database}",
                 "TrustServerCertificate=yes", "Encrypt=yes"]
        parts += ["Trusted_Connection=yes"] if self.sql_trusted_connection else \
                 [f"UID={self.sql_user}", f"PWD={self.sql_password}"]
        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(";".join(parts))

settings = Settings()
