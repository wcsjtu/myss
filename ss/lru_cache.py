# -*- coding: utf-8 -*-

from collections import namedtuple
_CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


HITS, MISSES = 0, 1
PREV, NEXT, KEY, RESULT = 0, 1, 2, 3    # names for the link fields

__all__ = ["LRUCache"]

class LRUCache(object):
    
    def __init__(self, maxsize=100):
        self._cache = {}
        self._maxsize = maxsize
        self._stats = [0, 0]
        self._root = []
        self._root[:] = [self._root, self._root, None, None]
        self._nonlocal_root = [self._root]

    def __getitem__(self, key):
        link = self._cache.get(key)
        if link is not None:
            self._root, = self._nonlocal_root
            link_prev, link_next, key, result = link
            link_prev[NEXT] = link_next
            link_next[PREV] = link_prev
            last = self._root[PREV]
            last[NEXT] = self._root[PREV] = link
            link[PREV] = last
            link[NEXT] = self._root
            self._stats[HITS] += 1
            return result
        else:
            self._stats[MISSES] += 1
            return None

    def __contains__(self, key):
        return key in self._cache

    def __setitem__(self, key, val):
        self._root, = self._nonlocal_root
        if key in self._cache:
            return
        elif len(self._cache) >= self._maxsize:
            oldroot = self._root
            oldroot[KEY] = key
            oldroot[RESULT] = val
            self._root = self._nonlocal_root[0] = oldroot[NEXT]
            oldkey = self._root[KEY]
            oldvalue = self._root[RESULT]
            self._root[KEY] = self._root[RESULT] = None
            del self._cache[oldkey]
            self._cache[key] = oldroot
        else:
            last = self._root[PREV]
            link = [last, self._root, key, val]
            last[NEXT] = self._root[PREV] = self._cache[key] = link

    def __del__(self):
        self._cache.clear()
        self._root = self._nonlocal_root[0]
        self._root[:] = [self._root, self._root, None, None]
        self._stats[:] = [0, 0]

    def __repr__(self):
        return _CacheInfo(self._stats[HITS], self._stats[MISSES], 
                self._maxsize, len(self._cache)).__repr__()

