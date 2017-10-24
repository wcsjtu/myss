# -*- coding: utf-8 -*-

"""
a lru_cache container/decorator derivatived from django
"""

from functools import wraps, update_wrapper
from collections import namedtuple
_CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


HITS, MISSES = 0, 1
PREV, NEXT, KEY, RESULT = 0, 1, 2, 3    # names for the link fields

__all__ = ["LRUCache", "lru_cache"]

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


def lru_cache(maxsize=100, ismethod=True):

    def _lru_cache(func):
        lruc = LRUCache(maxsize)
        @wraps(func)
        def wrapper(*args, **kwargs):
            index = 1 if ismethod else 0
            key = args[index]
            if key in lruc:
                return lruc[key]
            else:
                val = func(*args, **kwargs)
                lruc[key] = val
                return val
        wrapper.__wrapped__ = func
        wrapper.cache_info = lruc.__repr__
        wrapper.cache_clear = lruc.__del__
        return update_wrapper(wrapper, func)
    return _lru_cache

if __name__ == "__main__":
    import sys
    @lru_cache(ismethod=False)
    def f(key):
        print("execute f with key = %s" % key)
        return key.upper()
    @lru_cache(ismethod=False)
    def g(key):
        print("execute g with key = %s" % key)
        return key.upper()
    
    class A(object):
        @lru_cache()
        def h(self, x):
            print("execute h with key = %s" % x)
            return x.upper()


    f("aaa")
    f("ddd")
    f("aaa")

    g("aaa")
    g("ppp")
    g("aaa")
    g("qqq")

    a = A()
    a.h("hhhh")
    a.h("gggg")
    a.h("hhhh")