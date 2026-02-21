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
    ip = pewe.CharField(max_length=45, unique=True, primary_key=True)
    mac = pewe.CharField(max_length=17, unique=True)
    user = pewe.CharField(max_length=50)
    path = pewe.CharField(max_length=255)

    def __str__(self):
        return self.ip.__str__()



class Container(BaseModel):
    subdomain = pewe.CharField(max_length=4, unique=True, primary_key=True)
    port = pewe.IntegerField(unique=True)
    host = pewe.ForeignKeyField(Host, backref="containers", field='ip')

    def __str__(self):
        return f"{self.subdomain}:{self.port}"



class Whitelist(BaseModel):
    username = pewe.CharField(max_length=50)
    container = pewe.ForeignKeyField(Container, backref="whitelist", field='subdomain')

    class Meta:
        indexes = (
            (('username', 'container'), True),
        )