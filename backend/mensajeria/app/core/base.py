from pydantic import BaseModel, Field, ConfigDict

class DBModel(BaseModel):
    """
    Modelo base:
    - __schema__: esquema en Postgres
    - __tablename__: nombre de tabla (opcional).  
      Si no se define, se usa el nombre de la clase en snake_case.
    """
    model_config = ConfigDict(extra='ignore')      # tolera attrs extra
    __schema__: str = ''
    __tablename__: str | None = None

    # ----- utilidades internas -----
    @classmethod
    def _to_snake(cls, name: str) -> str:
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    @classmethod
    def table_fullname(cls) -> str:
        name = cls.__tablename__ or cls._to_snake(cls.__name__)
        return f'{cls.__schema__}.{name}' if cls.__schema__ else name