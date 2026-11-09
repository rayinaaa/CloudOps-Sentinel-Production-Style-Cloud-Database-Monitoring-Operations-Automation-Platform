"""Base entity mixins for SQLAlchemy models supporting Oracle and PostgreSQL."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Text, TypeDecorator, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class JSONType(TypeDecorator[Any]):
    """Platform-independent JSON type compatible with Oracle CLOB and PostgreSQL JSONB."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is not None:
            if dialect.name == "postgresql":
                return value
            if isinstance(value, (dict, list)):
                return json.dumps(value)
            return str(value)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is not None:
            if dialect.name == "postgresql":
                return value
            if isinstance(value, (dict, list)):
                return value
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return value
        return value


class TimestampedBase(Base):
    """Abstract model providing UUID primary keys and standard cloud audit timestamps."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Universally Unique Identifier primary key",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        doc="Record creation UTC timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        doc="Record last updated UTC timestamp",
    )
