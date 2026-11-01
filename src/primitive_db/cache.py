from copy import deepcopy


def create_cacher():
    """Create a bounded cache stored in a closure."""
    cache = {}

    def cache_result(key, value_func):
        """Return a cached result or calculate it once."""
        if key not in cache:
            if len(cache) >= 128:
                cache.clear()

            cache[key] = deepcopy(value_func())

        return deepcopy(cache[key])

    return cache_result
