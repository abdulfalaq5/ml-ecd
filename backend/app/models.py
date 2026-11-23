"""Skema database. Nama kolom kanal = canonical field di docs/CHANNELS.md §0.1."""
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

# kanal numerik yang disimpan untuk Rec 01 / 02 (time & depth based)
CHANNELS = [
    "bit_depth", "bit_tvd", "hole_depth", "hole_tvd", "block_pos", "rop", "hookload", "hookload_max",
    "wob", "torque", "torque_max", "rpm", "spp", "flow_in", "flow_out_pct", "active_pit", "trip_tank",
    "gain_loss", "spm_total", "ecd", "anp", "mud_dens_in", "inclination", "azimuth", "actc",
]


class ChannelMixin:
    """Kolom kanal dibuat dinamis dari CHANNELS (disalin declarative ke tiap tabel)."""


for _c in CHANNELS:
    setattr(ChannelMixin, _c, mapped_column(Float, nullable=True))


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Well(Base):
    __tablename__ = "wells"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    field: Mapped[str] = mapped_column(String(64), default="")
    uwi: Mapped[str] = mapped_column(String(64), default="")
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    section: Mapped[str] = mapped_column(String(32), default="")
    shoe_md: Mapped[float | None] = mapped_column(Float, nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="train")  # train | blind | case | shadow
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | archived
    notes: Mapped[str] = mapped_column(Text, default="")
    # zona rathole: open hole di bawah shoe yang tidak ter-cover casing (mis. casing di-set lebih awal)
    # {"top_md": 5354, "base_md": 5651, "since": ISO waktu casing selesai di-set/cement, "note": "..."}
    rathole: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # data section depth-based (core/sections.py): [{from_md, hole_size, shoe_md, casing_id, preset, pv, yp, note}]
    sections: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestFile(Base):
    __tablename__ = "ingest_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    record: Mapped[int] = mapped_column(SmallInteger)
    basis: Mapped[str] = mapped_column(String(8))  # time | depth
    fmt: Mapped[str] = mapped_column(String(32), default="")
    rows: Mapped[int] = mapped_column(Integer, default=0)
    t_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    t_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    d_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    mapped: Mapped[dict] = mapped_column(JSON, default=dict)
    unmapped: Mapped[list] = mapped_column(JSON, default=list)
    qc: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    uploaded_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("well_id", "sha256"),)


class TimeSample(ChannelMixin, Base):
    """Rec 01 (record=1) dan Rec 02 (record=2) basis waktu. Hypertable TimescaleDB."""
    __tablename__ = "ts_data"
    well_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)


class DepthSample(ChannelMixin, Base):
    """Rec 01 / 02 basis depth (0,25 ft)."""
    __tablename__ = "depth_data"
    well_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    md: Mapped[float] = mapped_column(Float, primary_key=True)


class PPFGVersion(Base):
    __tablename__ = "ppfg_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | approved | superseded
    source_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tvd_datum: Mapped[str] = mapped_column(String(16), default="RKB")
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str] = mapped_column(String(64), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PPFGRow(Base):
    __tablename__ = "ppfg_rows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("ppfg_versions.id", ondelete="CASCADE"), index=True)
    md: Mapped[float] = mapped_column(Float)
    tvd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    sfg: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    fg_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    shmax: Mapped[float | None] = mapped_column(Float, nullable=True)
    obg: Mapped[float | None] = mapped_column(Float, nullable=True)
    formation: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MudWeight(Base):
    __tablename__ = "mud_weight"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    md: Mapped[float] = mapped_column(Float)
    tvd: Mapped[float | None] = mapped_column(Float, nullable=True)
    mw: Mapped[float] = mapped_column(Float)
    remark: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Survey(Base):
    __tablename__ = "survey"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    md: Mapped[float] = mapped_column(Float)
    tvd: Mapped[float | None] = mapped_column(Float, nullable=True)
    inc: Mapped[float | None] = mapped_column(Float, nullable=True)
    azi: Mapped[float | None] = mapped_column(Float, nullable=True)
    dls: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    onset: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    md: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="ADVISORY")
    category: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[str] = mapped_column(String(16), default="Sedang")
    review_status: Mapped[str] = mapped_column(String(24), default="Draft")
    evidence: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(64), default="manual")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MLModel(Base):
    __tablename__ = "ml_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    algo: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="candidate")  # candidate|shadow|production|archived|failed
    features: Mapped[list] = mapped_column(JSON, default=list)
    train_wells: Mapped[list] = mapped_column(JSON, default=list)
    blind_wells: Mapped[list] = mapped_column(JSON, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    residual_q: Mapped[dict] = mapped_column(JSON, default=dict)
    feature_ranges: Mapped[dict] = mapped_column(JSON, default=dict)
    importance: Mapped[dict] = mapped_column(JSON, default=dict)
    gates: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_path: Mapped[str] = mapped_column(String(512), default="")
    log: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    proposed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    proposed_by: Mapped[str] = mapped_column(String(64), default="")
    approved_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    well_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    narrative: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
