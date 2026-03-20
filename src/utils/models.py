import peewee
from playhouse.postgres_ext import JSONField

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
    __db__.create_tables([Host, Container, Whitelist])



class BaseModel(peewee.Model):
    class Meta:
        database = __db__



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
    host = peewee.ForeignKeyField(Host, backref="containers", field='ip', null=True, on_delete='SET NULL')
    initialized = peewee.BooleanField(default=False)
    to_be_deleted = peewee.BooleanField(default=False)
    config = JSONField(default={})

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