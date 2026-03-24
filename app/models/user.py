from datetime import datetime, timezone
from enum import Enum
from app.extensions import db


class UserRole(Enum):
    """
    Enumera los roles posibles de usuario en el sistema.

    Valores:
        - ADMIN: Usuario con privilegios administrativos.
        - USER: Usuario estándar.
    """

    ADMIN = "admin"
    USER = "user"


class User(db.Model):
    """
    Modelo que representa un usuario del sistema.

    Atributos:
        - id: Identificador único.
        - username: Nombre de usuario (único).
        - email: Correo electrónico (único).
        - password_hash: Hash de la contraseña.
        - role: Rol del usuario (admin o user).
        - is_active: Indica si la cuenta está activa.
        - last_login_at: Fecha y hora del último acceso.
        - created_at: Fecha de creación del usuario.
        - updated_at: Fecha de última actualización.

    Relaciones:
        - clients_created: Clientes creados por este usuario (relación con Client).
        - clients_updated: Clientes actualizados por este usuario (relación con Client).
        - businesses_created: Negocios creados por este usuario (relación con Business).
        - businesses_updated: Negocios actualizados por este usuario (relación con Business).
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(
        db.Enum(UserRole, name="user_role_enum"), default=UserRole.USER, nullable=False
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(
        db.DateTime, default=datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"
