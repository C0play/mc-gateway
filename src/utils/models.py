import peewee as pewe
from ..config.config import PostgresConfig


__db__ = pewe.PostgresqlDatabase(None)

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



class BaseModel(pewe.Model):
    class Meta:
        database = __db__



class Host(BaseModel):
    """Peewee model representing a physical host."""
    ip = pewe.CharField(max_length=45, unique=True, primary_key=True)
    mac = pewe.CharField(max_length=17, unique=True)
    user = pewe.CharField(max_length=50)
    path = pewe.CharField(max_length=255)

    def __str__(self):
        return self.ip.__str__()



class Container(BaseModel):
    """Peewee model representing a Docker container."""
    subdomain = pewe.CharField(max_length=4, unique=True, primary_key=True)
    port = pewe.IntegerField()
    host = pewe.ForeignKeyField(Host, backref="containers", field='ip', null=True, on_delete='SET NULL')
    initialized = pewe.BooleanField(default=False)
    to_be_deleted = pewe.BooleanField(default=False)
    config = pewe.TextField(default="{}")

    class Meta:
        indexes = (
            (('port', 'host'), True),
        )

    def __str__(self):
        return f"{self.subdomain}:{self.port}"



class Whitelist(BaseModel):
    """Peewee model representing a whitelist entry."""
    username = pewe.CharField(max_length=50)
    container = pewe.ForeignKeyField(Container, backref="whitelist", field='subdomain', on_delete='CASCADE')

    class Meta:
        indexes = (
            (('username', 'container'), True),
        )

    def __str__(self):
        return f"{self.username}:{self.container}"