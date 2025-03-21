# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module helps manage objects that need to be cached. Objects are cached both in memory
and on disk so that the cache can be leveraged by multiple processes.

Each object you want to save needs to have a string ID that identifies it. The ID is used to
locate the object in memory (a key in a dictionary), and on the disk (the filename).
"""

import contextlib
import fcntl
import os
import pickle

from time import time


@contextlib.contextmanager
def get_lock(name):
    """Create a `name.lock` file and, using fcntl, lock it (or wait for the lock to be released) before proceeding.

    Notes:
         The `name.lock` file is not removed after the lock is released; it is kept to be reused:
         we only care about the lock status.

    Args:
        name (str): The name of the file you want to lock. A lockfile `name.lock` will be created.
    """
    with open(name + ".lock", "a+") as fdesc:
        fcntl.flock(fdesc, fcntl.LOCK_EX)
        yield fdesc


class DiskCache:
    """Manages the cache. Objects expire after a `cache_duration` time (defaults to one hour).
    Objects are pickled into a file. The directory to save those files has to be specified.
    Methods to save and load an object by its ID are provided.
    """

    def __init__(self, cache_dir, cache_duration=3600):
        """Initializes the DiskCache object.

        Args:
            cache_dir (str): The location where the pickled objects are saved.
            cache_duration (int): Defaults to 3600, the number of seconds objects are kept before
                you get a miss.
        """
        self.cache_dir = cache_dir
        self.mem_cache = {}
        self.cache_duration = cache_duration

    def get_fname(self, objid):
        """Returns the cache filename given a cache object ID.

        Args:
            objid (str): The cache object ID.

        Returns:
            str: The cache filename.
        """
        return os.path.join(self.cache_dir, objid)

    def get(self, objid):
        """Returns the cached object given its object ID `objid`. Returns None if
        the object is not in the cache, or if it has expired.

        First, we check if the object is in the memory dictionary; otherwise, we look
        for its corresponding cache file, and load it from there.

        Args:
            objid (str): The string representing the object ID you want to get.

        Returns:
            object: The cached object, or None if the object does not exist or the cache has expired.
        """
        obj = None
        saved_time = 0
        fname = self.get_fname(objid)
        if objid in self.mem_cache:
            saved_time, obj = self.mem_cache[objid]
        elif os.path.isfile(fname):
            with get_lock(fname):
                with open(fname, "rb") as fdesc:
                    saved_time, obj = pickle.load(fdesc)
            self.mem_cache[objid] = (saved_time, obj)
        if time() - saved_time < self.cache_duration:
            return obj
        else:
            return None

    def save(self, objid, obj):
        """Save an object into the cache.

        Objects are saved both in memory and into the corresponding cache file (one file
        for each object ID). Objects are saved paired with the timestamp representing the time
        when they have been saved.

        Args:
            objid (str): The ID of the object you are saving.
            obj (object): The Python object that you want to save.
        """
        fname = self.get_fname(objid)
        with get_lock(fname):
            with open(fname, "wb") as fdesc:
                save_time = time()
                pickle.dump((save_time, obj), fdesc)
                self.mem_cache[objid] = (save_time, obj)
