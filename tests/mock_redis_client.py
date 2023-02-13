import fakeredis

def get_redis_instance():
    return fakeredis.FakeStrictRedis(version=7)
