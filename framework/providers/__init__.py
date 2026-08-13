"""Stable container for explicitly documented optional-provider namespaces.

Provider implementations are never selected or imported by this package.
Consumers must import an exact reviewed provider module explicitly.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
