#!/usr/bin/env python
"""Utilidad de línea de comandos de Django para JKVAL."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jkval.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django no está disponible. Activa el entorno: .venv/bin/python"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
