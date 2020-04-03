"""This module helps managing objects that needs to be cached. Objects are cached both in memory
and on disk so that the cache can be leveraged by multiple processes.

Each object you want to save needs to have a string id that identifies it. The id is used to
locate the object in the memory (a key in a dictionary), and on the disk (the filename).
"""

import os
import fcntl
import pickle
import contextlib
from time import time


@contextlib.contextmanager
def get_lock(name):
    """Create a "name".lock file and, using fcnt,
    lock it (or wait for the lock to be released) before proceeding

    N.B. The "name".lock file is not removed after the lock is released, it is kept to be reused:
    we only care about the lock status.

    Params:
        name (str): the name of the file you want to lock. A lockfile name.lock will be created
    """
    with open(name + '.lock', 'a+') as fdesc:
        fcntl.flock(fdesc, fcntl.LOCK_EX)
        yield fdesc


class DiskCache(object):
    """The class that manages the cache. Objects expires after a cache_duration time (defaults
    to one hour). Objects are pickled into a file. The directory to save those files has to
    be specified. Methods to save and load an object by its id are provided.
    """
    def __init__(self, cache_dir, cache_duration=3600):
        """Build the DiskCache object

        Args:
            cache_dir (str): the location where the pickled objects are saved
            cache_duration (int): defaults 3600, the number of seconds objects are kept before
                you get a miss
        """
        self.cache_dir = cache_dir
        self.mem_cache = {}
        self.cache_duration = cache_duration

    def get_fname(self, objid):
        """Simple auxiliary function that returns the cache filename given a cache object id
        """
        return os.path.join(self.cache_dir, objid)

    def get(self, objid):
        """Returns the cached object given its object id ``objid``. Returns None if
        the object is not in the cache, or if it has expired.

        First we check if the object is in the memory dictionary, otherwise we look
        for its corresponding cache file, and we loads it from there.

        Args:
            objid (str): the string representing the object id you want to get

        Returns:
            The cached object, or None if the object does not exist or the cache is expired
        """
        obj = None
        saved_time = 0
        fname = self.get_fname(objid)
        if objid in self.mem_cache:
            saved_time, obj = self.mem_cache[objid]
        elif os.path.isfile(fname):
            with get_lock(fname):
                with open(fname) as fdesc:
                    saved_time, obj = pickle.load(fdesc)
            self.mem_cache[objid] = (saved_time, obj)
        if time() - saved_time < self.cache_duration:
            return obj
        else:
            return None

    def save(self, objid, obj):
        """Save an object into the cache.

        Objects are saved both in memory and into the corresponding cache file (one file
        for each object id).
        Objects are saved paired with the timestamp representing the time when it
        has been saved.

        Args:
            objid (str): The id of the object you are saving
            obj: the python object that you want to save
        """
        fname = self.get_fname(objid)
        with get_lock(fname):
            with open(fname, 'w') as fdesc:
                save_time = time()
                pickle.dump((save_time, obj), fdesc)
                self.mem_cache[objid] = (save_time, obj)
