from sqlalchemy import (Column, Integer, String, Text, DateTime,
                        ForeignKey, Table, func)
from sqlalchemy.orm import relationship
from app.database import Base

# Table 3.4: role_permissions (mapping table)
role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.role_id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.permission_id"), primary_key=True),
)

# Table 3.2: roles
class Role(Base):
    __tablename__ = "roles"
    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), nullable=False, unique=True)
    description = Column(String(255))
    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")

# Table 3.3: permissions
class Permission(Base):
    __tablename__ = "permissions"
    permission_id = Column(Integer, primary_key=True, autoincrement=True)
    permission_name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255))
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

# Table 3.1: users
class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"))
    created_at = Column(DateTime, server_default=func.now())
    role = relationship("Role", back_populates="users")

# Table 3.5: documents
class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.user_id"))
    access_level = Column(String(100), nullable=False)
    upload_date = Column(DateTime, server_default=func.now())

# Table 3.6: query_logs
class QueryLog(Base):
    __tablename__ = "query_logs"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    query_text = Column(Text, nullable=False)
    response_text = Column(Text)
    timestamp = Column(DateTime, server_default=func.now())