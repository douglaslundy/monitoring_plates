"""Métricas de recursos do host (CPU, RAM, disco) via psutil.

Leitura barata (microssegundos) para o painel "Recursos do servidor". CPU/RAM
refletem o HOST (o container compartilha /proc do host para esses valores);
disco usa o filesystem do volume de storage (= disco do host). Degrada
graciosamente (available=False) se o psutil não estiver instalado.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class SystemMetrics:
    available: bool
    cpu_percent: float
    cpu_count: int
    load_avg_1m: float
    mem_total_mb: int
    mem_used_mb: int
    mem_available_mb: int
    mem_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_percent: float

    def as_dict(self) -> dict:
        return asdict(self)


_EMPTY = SystemMetrics(False, 0.0, 0, 0.0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)

_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024


def _disk_path() -> str:
    for path in ("/app/storage", "/"):
        if os.path.isdir(path):
            return path
    return "/"


def get_system_metrics() -> SystemMetrics:
    try:
        import psutil
    except Exception:
        return _EMPTY

    try:
        vm = psutil.virtual_memory()
        du = psutil.disk_usage(_disk_path())
        try:
            load1 = os.getloadavg()[0]
        except (OSError, AttributeError):
            load1 = 0.0

        return SystemMetrics(
            available=True,
            cpu_percent=round(psutil.cpu_percent(interval=0.2), 1),
            cpu_count=psutil.cpu_count() or 0,
            load_avg_1m=round(load1, 2),
            mem_total_mb=int(vm.total // _MB),
            mem_used_mb=int(vm.used // _MB),
            mem_available_mb=int(vm.available // _MB),
            mem_percent=round(vm.percent, 1),
            disk_total_gb=round(du.total / _GB, 1),
            disk_used_gb=round(du.used / _GB, 1),
            disk_free_gb=round(du.free / _GB, 1),
            disk_percent=round(du.percent, 1),
        )
    except Exception:
        return _EMPTY
