"""Runtime configuration. Every value can be overridden by an env var of the same name."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # --- database (PostgreSQL 16) ---
    DB_NAME: str = "partfit_db"
    DB_USER: str = "partfit_user"
    DB_PASSWORD: str = "partfit_pwd"
    DB_HOST: str = "db"
    DB_PORT: int = 5432

    # --- auth ---
    JWT_SECRET: str = "partfit_dev_jwt_secret_change_me_in_prod_1112"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8

    # --- infra ---
    REDIS_URL: str = "redis://redis:6379/0"
    WAREHOUSE_ARTIFACT_DIR: str = "/data/warehouse"
    WAREHOUSE_CATALOG: str = "lantu_ads"

    # --- scan cost model (documented in README §成本口径) ---
    COST_PER_GIB_CNY: float = 0.30       # 每次查询扫描 1 GiB 的分摊单价（元）
    QUERY_VOLUME_SCALE: float = 5.0      # seed 的 60 条日志代表日均 300 条，月折算放样 5 倍
    MONTHLY_QUERY_DAYS: int = 30         # 日查询量折算月账单的天数
    COST_CURRENCY: str = "CNY"
    DEFAULT_MONTHLY_BUDGET_CNY: float = 1800.0
    DEFAULT_WARN_RATIO: float = 0.75
    DEFAULT_CRITICAL_RATIO: float = 0.92

    # --- rewrite scoring weights (algorithm 2) ---
    RISK_WEIGHT_LOW: float = 1.0
    RISK_WEIGHT_MEDIUM: float = 1.6
    RISK_WEIGHT_HIGH: float = 2.4
    CONFIDENCE_WRAP_FIX: float = 0.95
    CONFIDENCE_PROJECTION: float = 0.90
    CONFIDENCE_PREDICATE_ADDED: float = 0.62
    REWRITE_WINDOW_DAYS: int = 7

    # --- limits ---
    RATE_WINDOW_SECONDS: int = 60
    RATE_WINDOW_MAX: int = 240
    ESTIMATE_INLINE: bool = False
    ESTIMATE_MAX_QUERIES: int = 200
    QUERY_PAGE_MAX: int = 200

    # --- demo seed ---
    SEED_DEMO: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
