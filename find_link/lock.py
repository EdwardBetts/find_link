import time
from redis import StrictRedis

# from https://chris-lamb.co.uk/posts/distributing-locking-python-and-redis
# TODO: move redis location to config

redis = StrictRedis(host='localhost', port=6379, db=0)

class Lock(object):
    def __init__(self, key, expires=60, timeout=10):
        """
        Distributed locking using Redis SETNX and GETSET.

        Usage::

            with Lock('my_lock'):
                print "Critical section"

        :param  expires     We consider any existing lock older than
                            ``expires`` seconds to be invalid in order to
                            detect crashed clients. This value must be higher
                            than it takes the critical section to execute.
        :param  timeout     If another client has already obtained the lock,
                            sleep for a maximum of ``timeout`` seconds before
                            giving up. A value of 0 means we never wait.
        """

        self.key = key
        self.timeout = timeout
        self.expires = expires

    def __enter__(self):
        timeout = self.timeout
        while timeout >= 0:
            expires = time.time() + self.expires + 1

            if redis.setnx(self.key, expires):
                # We gained the lock; enter critical section
                return

            current_value = redis.get(self.key)

            # We found an expired lock and nobody raced us to replacing it
            if (current_value and float(current_value) < time.time() and
                    redis.getset(self.key, expires) == current_value):
                return

            timeout -= 1
            time.sleep(1)

        raise LockTimeout("Timeout whilst waiting for lock")

    def __exit__(self, exc_type, exc_value, traceback):
        redis.delete(self.key)

class LockTimeout(BaseException):
    pass
