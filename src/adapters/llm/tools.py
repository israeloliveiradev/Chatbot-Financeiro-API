from typing import List, Optional

def registrar_gasto(category_name: str, amount: float, description: Optional[str] = None):
    """
    Registra um novo gasto/despesa.
    :param category_name: Nome da categoria (ex: Alimentação, Transporte, Lazer).
    :param amount: Valor do gasto.
    :param description: Descrição opcional do que foi comprado.
    """
    pass

def criar_objetivo(title: str, target_amount: float, deadline: Optional[str] = None):
    """
    Cria uma nova meta/objetivo financeiro (ex: Viagem, Carro Novo).
    :param title: Título do objetivo.
    :param target_amount: Valor total que deseja juntar.
    :param deadline: Data limite opcional no formato YYYY-MM-DD.
    """
    pass

def listar_objetivos():
    """Retorna a lista de todos os seus objetivos financeiros ativos e o progresso de cada um."""
    pass

def definir_meta_mensal(category_name: str, limit_amount: float):
    """
    Define um limite de gastos (orçamento) para uma categoria específica no mês atual.
    :param category_name: Nome da categoria.
    :param limit_amount: Valor máximo que deseja gastar no mês.
    """
    pass

def obter_resumo_mensal():
    """
    Retorna um relatório detalhado de quanto você já gastou por categoria, 
    quais metas mensais foram atingidas e quanto ainda tem disponível.
    """
    pass

# List of tools to be passed to Gemini
FINANCIAL_TOOLS = [
    registrar_gasto,
    criar_objetivo,
    listar_objetivos,
    definir_meta_mensal,
    obter_resumo_mensal
]
