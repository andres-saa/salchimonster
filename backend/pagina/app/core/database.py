# db.py
import os
import inspect
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor, Json
from pydantic import BaseModel

# ------------------------------------------------------------------
# 1)  Mixin para los modelos  --------------------------------------
# ------------------------------------------------------------------
class DBModel(BaseModel):
    """
    Modelo base para tus entidades Pydantic.

    Atributos de clase (NO son columnas):
    -------------------------------------
    - __schema__: esquema en PostgreSQL ('' = esquema público)
    - __tablename__: nombre de tabla. Si no se define, se deriva
      automáticamente del nombre de la clase en snake_case.
    """
    model_config = {"extra": "ignore"}       # ignora attrs externos
    __schema__: str = ''
    __tablename__: str | None = None

    # Utilidades internas  -----------------
    @classmethod
    def _to_snake(cls, name: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    @classmethod
    def table_fullname(cls) -> str:
        name = cls.__tablename__ or cls._to_snake(cls.__name__)
        return f'{cls.__schema__}.{name}' if cls.__schema__ else name


# ------------------------------------------------------------------
# 2)  Clase Db (helper psycopg2)  ----------------------------------
# ------------------------------------------------------------------
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")


class Db:
    # ---------- init / context manager ---------------------------
    def __init__(self) -> None:
        self.conn_str = (
            f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} "
            f"host={DB_HOST} port={DB_PORT}"
        )
        self.conn = psycopg2.connect(self.conn_str)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()

    def close_connection(self):
        self.conn.close()

    # ---------- helpers internos ---------------------------------
    @staticmethod
    def _get_table(model_or_cls: Union[DBModel, type[DBModel]]) -> str:
        """
        Devuelve '<schema>.<tabla>' usando el mixin DBModel.
        Acepta instancia o clase del modelo.
        """
        cls = model_or_cls if isinstance(model_or_cls, type) else model_or_cls.__class__
        if hasattr(cls, "table_fullname"):
            return cls.table_fullname()
        # Fallback: snake_case del nombre de la clase
        return re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()

    @staticmethod
    def _to_payload(data: BaseModel) -> Dict[str, Any]:
        # excluye None y atributos de clase (estos últimos no aparecen)
        return data.model_dump(exclude_none=True)

    # ---------- ejecución genérica -------------------------------
    def execute_query(
        self,
        query: str,
        params: Optional[Union[Dict[str, Any], Tuple, List]] = None,
        fetch: bool = False,
    ):
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                result = None
                if fetch:
                    rows = cursor.fetchall()
                    if not rows:
                        result = None
                    elif len(rows) == 1:
                        result = rows[0]          # dict
                    else:
                        result = rows             # list[dict]
                self.conn.commit()
                return result
        except Exception as e:
            self.conn.rollback()
            print(f"An error occurred: {e}")

    # --------- consultas con JSON automático ---------------------
    def _process_json_params(self, params):
        if params is None:
            return None
        if isinstance(params, (list, tuple)):
            return type(params)(
                Json(p) if isinstance(p, (dict, list)) else p for p in params
            )
        if isinstance(params, dict):
            return {k: Json(v) if isinstance(v, (dict, list)) else v for k, v in params.items()}
        return params

    def execute_query_json(
        self,
        query: str,
        params: Optional[Union[Dict, Tuple, List]] = None,
        fetch: bool = False,
    ):
        processed = self._process_json_params(params)
        return self.execute_query(query, processed, fetch)

    # ---------- SELECT helpers -----------------------------------
    def build_select_query(
        self,
        target: Union[type[DBModel], DBModel, str],  # modelo o nombre de tabla
        fields: Optional[List[str]] = None,
        condition: str = '',
        order_by: str = '',
        limit: int = 0,
        offset: int = 0,
        *,
        schema: str = ''        # ←  schema separado y opcional
    ) -> str:
        """
        Si `target` es str, construye la tabla como  <schema>.<tabla>
        Si `target` es modelo, usa su propio schema / tablename.
        """
        # 1.  Resolver el nombre completo de tabla
        if isinstance(target, str):
            # target = 'customer', schema = 'users'  →  'users.customer'
            table = f'{schema}.{target}' if schema else target
        else:
            table = self._get_table(target)   # usa mixin DBModel

        # 2.  Columnas
        cols = ', '.join(fields) if fields else '*'

        # 3.  Construir la consulta
        query = f'SELECT {cols} FROM {table}'
        if condition:
            query += f' WHERE {condition}'
        if order_by:
            query += f' ORDER BY {order_by}'
        if limit:
            query += f' LIMIT {limit}'
        if offset:
            query += f' OFFSET {offset}'
        return query

    # ---------- INSERT (una fila) --------------------------------
    def build_insert_query(
        self,
        data: DBModel,
        returning: str = ''
    ) -> Tuple[str, Dict[str, Any]]:
        table = self._get_table(data)
        payload = self._to_payload(data)
        cols = ', '.join(payload.keys())
        vals = ', '.join(f'%({k})s' for k in payload)
        query = f'INSERT INTO {table} ({cols}) VALUES ({vals})'
        if returning:
            query += f' RETURNING {returning}'
        return query, payload

    # ---------- INSERT masivo ------------------------------------
    def build_bulk_insert_query(
        self,
        data_list: List[DBModel],
        returning: str = ''
    ) -> Tuple[str, List[Dict[str, Any]]]:
        if not data_list:
            raise ValueError("data_list no puede estar vacío")

        table = self._get_table(data_list[0])
        first_payload = self._to_payload(data_list[0])
        cols = ', '.join(first_payload.keys())
        placeholders = ', '.join(f'%({k})s' for k in first_payload)
        values_block = ', '.join(f'({placeholders})' for _ in data_list)

        query = f'INSERT INTO {table} ({cols}) VALUES {values_block}'
        if returning:
            query += f' RETURNING {returning}'

        params = [self._to_payload(m) for m in data_list]
        return query, params

    def execute_bulk_insert(
        self,
        query: str,
        params: List[Dict[str, Any]],
        fetch: bool = False,
    ):
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.executemany(query, params)
                self.conn.commit()
                if fetch:
                    return cursor.fetchall()
        except Exception as e:
            self.conn.rollback()
            print(f"An error occurred: {e}")

    # ---------- UPDATE -------------------------------------------
    def build_update_query(
        self,
        data: DBModel,
        condition: str,
        returning: str = ''
    ) -> Tuple[str, Dict[str, Any]]:
        table = self._get_table(data)
        payload = self._to_payload(data)
        set_clause = ', '.join(f'{k} = %({k})s' for k in payload)
        query = f'UPDATE {table} SET {set_clause} WHERE {condition}'
        if returning:
            query += f' RETURNING {returning}'
        return query, payload

    # ---------- BULK UPDATE --------------------------------------
    def execute_bulk_update(
        self,
        query: str,
        params: List[Dict[str, Any]],
        fetch: bool = False,
    ):
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.executemany(query, params)
                self.conn.commit()
                if fetch:
                    return cursor.fetchall()
        except Exception as e:
            self.conn.rollback()
            print(f"An error occurred: {e}")

    # ---------- DELETE -------------------------------------------
    def build_soft_delete_query(
        self,
        model_cls: type[DBModel],
        condition: str,
        returning: str = ''
    ) -> str:
        table = self._get_table(model_cls)
        query = f'UPDATE {table} SET exist = FALSE WHERE {condition}'
        if returning:
            query += f' RETURNING {returning}'
        return query

    def build_delete_query(
        self,
        model_cls: type[DBModel],
        condition: str,
        returning: str = ''
    ) -> str:
        table = self._get_table(model_cls)
        query = f'DELETE FROM {table} WHERE {condition}'
        if returning:
            query += f' RETURNING {returning}'
        return query

    # ---------- fetch helpers ------------------------------------
    def fetch_one(self, query: str, params=None):
        return self.execute_query(query, params, fetch=True)

    def fetch_all(self, query: str, params=None):
        result = self.execute_query(query, params, fetch=True)
        # Cuando usamos fetch=True en execute_query ya puede devolver list/dict/None
        return result

    # ---------- archivo .sql loader ------------------------------
    def cargar_archivo_sql(self, nombre_archivo: str) -> Optional[str]:
        try:
            ruta_llamador = os.path.dirname(
                os.path.abspath(inspect.stack()[1].filename)
            )
            ruta_archivo = os.path.join(ruta_llamador, nombre_archivo)
            with open(ruta_archivo, "r", encoding="utf-8") as archivo:
                return archivo.read()
        except FileNotFoundError:
            print(f"El archivo '{nombre_archivo}' no fue encontrado en '{ruta_llamador}'.")
        except Exception as e:
            print(f"Ocurrió un error al leer el archivo: {e}")
        return None
