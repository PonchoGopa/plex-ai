from typing import Optional

from sqlalchemy.orm import joinedload

from database.db import get_session
from database.orm_models import TemplateFieldORM, TemplateORM
from models.template import Template, TemplateField


class TemplateRepository:
    """
    Repository para persistir y recuperar plantillas Plex.

    Traduce entre el modelo de dominio (Template / TemplateField,
    definido en models/template.py y usado por el parser) y el
    modelo ORM (TemplateORM / TemplateFieldORM). El resto del
    sistema (parser, motor de validaciones, generadores) nunca
    debería importar SQLAlchemy directamente: solo conoce Template.
    """

    def save(self, template: Template) -> int:
        """
        Guarda una plantilla y sus campos.

        Si ya existe una plantilla con el mismo nombre, se reemplaza
        por completo (borra la anterior y crea la nueva). Es un
        upsert simple; no versiona cambios de estructura todavía.

        Retorna el id de la plantilla persistida.
        """
        with get_session() as session:
            existing = (
                session.query(TemplateORM)
                .filter(TemplateORM.name == template.name)
                .one_or_none()
            )

            if existing is not None:
                session.delete(existing)
                session.flush()

            template_orm = TemplateORM(
                name=template.name,
                description=template.description,
                file_type=template.file_type,
                plex_module=template.plex_module,
                fields=[
                    TemplateFieldORM(
                        order=f.order,
                        name=f.name,
                        data_type=f.data_type,
                        required=f.required,
                    )
                    for f in template.fields
                ],
            )

            session.add(template_orm)
            session.flush()
            return template_orm.id

    def find_by_name(self, name: str) -> Optional[Template]:
        with get_session() as session:
            template_orm = (
                session.query(TemplateORM)
                .options(joinedload(TemplateORM.fields))
                .filter(TemplateORM.name == name)
                .one_or_none()
            )

            if template_orm is None:
                return None

            return self._to_domain(template_orm)

    def exists(self, name: str) -> bool:
        with get_session() as session:
            return (
                session.query(TemplateORM.id)
                .filter(TemplateORM.name == name)
                .first()
                is not None
            )

    @staticmethod
    def _to_domain(template_orm: TemplateORM) -> Template:
        return Template(
            name=template_orm.name,
            description=template_orm.description or "",
            file_type=template_orm.file_type,
            plex_module=template_orm.plex_module or "",
            fields=[
                TemplateField(
                    order=f.order,
                    name=f.name,
                    data_type=f.data_type,
                    required=f.required,
                )
                for f in sorted(template_orm.fields, key=lambda x: x.order)
            ],
        )