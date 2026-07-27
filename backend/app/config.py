from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://cr_user:cr_pass@localhost:5432/clash_royale"
    clash_royale_api_key: str = ""
    clash_royale_api_base_url: str = "https://api.clashroyale.com/v1"
    admin_api_key: str = "change_me_admin_key"
    sync_on_startup: bool = False
    card_sync_cron_hour: int = 3
    leaderboard_top_n: int = 100
    leaderboard_page_limit: int = 100
    untrack_after_misses: int = 3
    battles_per_player: int = 25
    opponent_expansion_rounds: int = 2
    sync_ranked_battles_only: bool = True
    battlelog_batch_size: int = 10
    deck_evo_slots: str = "0,2"
    deck_hero_slot: int = 1


settings = Settings()
