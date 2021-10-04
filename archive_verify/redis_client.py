from redis import Redis


def get_redis_instance():
    return Redis()
