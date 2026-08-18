"""External data providers.

Providers are intentionally not imported eagerly so lightweight validation/tests that
exercise non-network components do not require optional runtime data packages to be
imported during package discovery.
"""

__all__ = []
