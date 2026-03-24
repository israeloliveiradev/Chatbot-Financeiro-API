from abc import ABC, abstractmethod
from typing import Any

class BaseUseCase(ABC):
    """
    Interface base para todos os Casos de Uso.
    Garante que todos implementem o método 'execute'.
    """
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        pass
