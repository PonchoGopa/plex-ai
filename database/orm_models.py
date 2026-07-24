from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database.db import Base


class TemplateORM(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(String(500), nullable=True, default="")
    file_type = Column(String(20), nullable=False, default="XML")
    plex_module = Column(String(100), nullable=True, default="")

    fields = relationship(
        "TemplateFieldORM",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateFieldORM.order",
    )


class TemplateFieldORM(Base):
    __tablename__ = "template_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False)
    order = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    data_type = Column(String(50), nullable=False, default="String")
    required = Column(Boolean, nullable=False, default=False)

    template = relationship("TemplateORM", back_populates="fields")

    __table_args__ = (
        UniqueConstraint("template_id", "order", name="uq_template_field_order"),
    )