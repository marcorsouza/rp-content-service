"""SQLAlchemy models matching the Prisma schema tables for content radar."""
import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Double, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class ContentSourceType(str, enum.Enum):
    RACE = "RACE"
    NEWS = "NEWS"


class DiscoveryRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class DiscoveredContentStatus(str, enum.Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"


class DiscoveredNewsCategory(str, enum.Enum):
    RACE = "RACE"
    HEALTH = "HEALTH"
    PERFORMANCE = "PERFORMANCE"
    MARKET = "MARKET"
    GENERAL = "GENERAL"


class ContentSource(Base):
    __tablename__ = "ContentSource"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[ContentSourceType] = mapped_column(Enum(ContentSourceType, name="ContentSourceType"), nullable=False)
    baseUrl: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    isActive: Mapped[bool] = mapped_column(Boolean, default=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    discovery_runs: Mapped[list["ContentDiscoveryRun"]] = relationship(back_populates="source")


class ContentDiscoveryRun(Base):
    __tablename__ = "ContentDiscoveryRun"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[ContentSourceType] = mapped_column(Enum(ContentSourceType, name="ContentSourceType"), nullable=False)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[DiscoveryRunStatus] = mapped_column(
        Enum(DiscoveryRunStatus, name="DiscoveryRunStatus"), default=DiscoveryRunStatus.RUNNING
    )
    startedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finishedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    itemsFound: Mapped[int] = mapped_column(Integer, default=0)
    itemsNew: Mapped[int] = mapped_column(Integer, default=0)
    itemsDuplicate: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sourceId: Mapped[str | None] = mapped_column(String, ForeignKey("ContentSource.id", ondelete="SET NULL"), nullable=True)

    source: Mapped["ContentSource | None"] = relationship(back_populates="discovery_runs")
    discovered_races: Mapped[list["DiscoveredRace"]] = relationship(back_populates="discovery_run")
    discovered_news: Mapped[list["DiscoveredNews"]] = relationship(back_populates="discovery_run")


class DiscoveredRace(Base):
    __tablename__ = "DiscoveredRace"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    eventDate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    sourceUrl: Mapped[str] = mapped_column(String, nullable=False)
    sourceName: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    status: Mapped[DiscoveredContentStatus] = mapped_column(
        Enum(DiscoveredContentStatus, name="DiscoveredContentStatus"), default=DiscoveredContentStatus.NEW
    )
    aiSummary: Mapped[str | None] = mapped_column(Text, nullable=True)
    rawPayload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discoveryRunId: Mapped[str | None] = mapped_column(
        String, ForeignKey("ContentDiscoveryRun.id", ondelete="SET NULL"), nullable=True
    )
    publishedRaceId: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    discovery_run: Mapped["ContentDiscoveryRun | None"] = relationship(back_populates="discovered_races")


class DiscoveredNews(Base):
    __tablename__ = "DiscoveredNews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    originalTitle: Mapped[str] = mapped_column(String, nullable=False)
    suggestedTitle: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sourceUrl: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sourceName: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[DiscoveredNewsCategory] = mapped_column(
        Enum(DiscoveredNewsCategory, name="DiscoveredNewsCategory"), default=DiscoveredNewsCategory.GENERAL
    )
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    status: Mapped[DiscoveredContentStatus] = mapped_column(
        Enum(DiscoveredContentStatus, name="DiscoveredContentStatus"), default=DiscoveredContentStatus.NEW
    )
    rawPayload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discoveryRunId: Mapped[str | None] = mapped_column(
        String, ForeignKey("ContentDiscoveryRun.id", ondelete="SET NULL"), nullable=True
    )
    publishedPostId: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    discovery_run: Mapped["ContentDiscoveryRun | None"] = relationship(back_populates="discovered_news")
