from typing import override

from PySide6.QtCore import QObject


class SingletonMeta(type):
    """Metaclass that enforces a single instance per class.

    Classes using this metaclass will return the same instance on every instantiation call. The
    first call creates and stores the instance; subsequent calls return the cached one.

    Usage::

        class MyClass(metaclass=SingletonMeta):
            def __init__(self):
                self.value = 42

        a = MyClass()
        b = MyClass()
        assert a is b  # True

    Note:
        ``*args`` and ``**kwargs`` are only applied during the first instantiation. Later calls
        silently ignore any new arguments.
    """

    _instances: dict["SingletonMeta", object] = {}

    @override
    def __call__(cls, *args: object, **kwargs: object):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class SingletonQObjectMeta(SingletonMeta, type(QObject)):
    """Combined metaclass for Qt singletons.

    Resolves the MRO conflict between :class:`SingletonMeta` and ``type(QObject)`` so that a
    ``QObject`` subclass can use singleton semantics without hitting Qt's internal metaclass
    restrictions.
    """

    pass
