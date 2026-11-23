from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg


@dataclass
class DatabasePools:
    admin: Any
    readonly: Any

    async def close(self) -> None:
        await self.admin.close()
        await self.readonly.close()


async def create_database_pools(admin_url: str, readonly_url: str) -> DatabasePools:
    pool_options = {"statement_cache_size": 0}
    return DatabasePools(
        admin=await asyncpg.create_pool(admin_url, **pool_options),
        readonly=await asyncpg.create_pool(readonly_url, **pool_options),
    )
