from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, func
from database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(10), nullable=False)
    buy_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    buy_date = Column(Date, nullable=False)
    current_price = Column(Float, default=0.0)
    highest_price = Column(Float, default=0.0)
    stop_loss_method = Column(String(20), nullable=False)
    stop_loss_value = Column(Float, nullable=False)
    stop_loss_price = Column(Float, default=0.0)
    status = Column(String(20), default="holding")
    close_price = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    holding_id = Column(Integer, nullable=False)
    trigger_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(200), nullable=False)
