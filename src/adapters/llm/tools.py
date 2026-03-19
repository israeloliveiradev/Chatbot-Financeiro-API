from typing import List, Optional

def registrar_gasto(category_name: str, amount: float, description: Optional[str] = None):
    """Registra um gasto (ex: categoria, valor, descrição opcional)."""
    pass

def criar_objetivo(title: str, target_amount: float, deadline: Optional[str] = None):
    """Cria uma meta financeira (ex: título, valor alvo, data opcional YYYY-MM-DD)."""
    pass

def listar_objetivos():
    """Lista metas ativas."""
    pass

def cancelar_objetivo(goal_id: str):
    """Cancela uma meta pelo ID."""
    pass

def simular_compra(item_name: str, price: float):
    """Simula impacto de uma compra no orçamento."""
    pass

def obter_resumo_mensal():
    """
    Retorna um resumo dos gastos totais, limites e saldo disponível no mês atual.
    """
    pass

# List of tools to be passed to Gemini
FINANCIAL_TOOLS = [
    registrar_gasto,
    criar_objetivo,
    listar_objetivos,
    cancelar_objetivo,
    simular_compra,
    obter_resumo_mensal
]
