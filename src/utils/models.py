import peewee
from playhouse.postgres_ext import (
    JSONField,
    

) 

from ..config.config import PostgresConfig


__db__ = peewee.PostgresqlDatabase(None)

def db_init(cfg: PostgresConfig):
    __db__.init(
        cfg.name,
        user=cfg.user,
        password=cfg.password,
        host=cfg.host,
        port=cfg.port,
    )
    __db__.connect()
    __db__.create_tables([Host, User, Session, Container, Whitelist, ApiKey])



class BaseModel(peewee.Model):
    class Meta:
        database = __db__



class User(BaseModel):
    """Peewee model representing a user."""
    email = peewee.CharField(unique=True, primary_key=True)
    passwd_salt = peewee.CharField()
    passwd_hash = peewee.CharField()
    role = peewee.CharField()



class ApiKey(BaseModel):
    key_hash = peewee.CharField()
    name = peewee.CharField()
    active = peewee.BooleanField(default=True)
    created_at = peewee.DateTimeField(formats="%Y-%m-%d %H:%M:%S")
    last_used_at = peewee.DateTimeField(formats="%Y-%m-%d %H:%M:%S")
    revoked_at = peewee.DateTimeField(formats="%Y-%m-%d %H:%M:%S", null=True, default=None)
    user = peewee.ForeignKeyField(User, field="email", on_delete="CASCADE")

    class Meta:
        indexes = (
            (('user', 'name'), True),
        )


class Session(BaseModel):
    id = peewee.UUIDField(unique=True, primary_key=True)
    created_at = peewee.DateTimeField(formats="%Y-%m-%d %H:%M:%S")
    valid_until = peewee.DateTimeField(formats="%Y-%m-%d %H:%M:%S")
    user = peewee.ForeignKeyField(User, field="email", on_delete="CASCADE")



class Host(BaseModel):
    """Peewee model representing a physical host."""
    ip = peewee.CharField(max_length=45, unique=True, primary_key=True)
    mac = peewee.CharField(max_length=17, unique=True)
    config = JSONField(default={})

    def __str__(self):
        return self.ip.__str__()



class Container(BaseModel):
    """Peewee model representing a Docker container."""
    subdomain = peewee.CharField(max_length=4, unique=True, primary_key=True)
    mc_port = peewee.IntegerField()
    rcon_port = peewee.IntegerField()
    rcon_password = peewee.TextField(null=True) # Encrypted at rest
    initialized = peewee.BooleanField(default=False)
    to_be_deleted = peewee.BooleanField(default=False)
    config = JSONField(default={})
    host = peewee.ForeignKeyField(Host, backref="containers", field='ip', null=True, on_delete='SET NULL')
    owner = peewee.ForeignKeyField(User, backref="containers", field='email', null=True, on_delete='SET NULL')

    class Meta:
        indexes = (
            (('mc_port', 'host'), True),
            (('rcon_port', 'host'), True),
        )
    def __str__(self):
        return f"{self.subdomain}:{self.mc_port}"



class Whitelist(BaseModel):
    """Peewee model representing a whitelist entry."""
    username = peewee.CharField(max_length=50)
    container = peewee.ForeignKeyField(Container, backref="whitelist", field='subdomain', on_delete='CASCADE')

    class Meta:
        indexes = (
            (('username', 'container'), True),
        )

    def __str__(self):
        return f"{self.username}:{self.container}"