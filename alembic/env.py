import os

from sqlalchemy import engine_from_config, pool

from alembic import context
from sentinel import models  # noqa: F401
from sentinel.db import Base

config = context.config
url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
if url.startswith("sqlite:///"):
    from pathlib import Path

    Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
target_metadata = Base.metadata
if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
