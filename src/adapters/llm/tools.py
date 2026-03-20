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

def registrar_aporte(goal_title: str, amount: float):
    """
    Registra um novo valor guardado (aporte) para um objetivo específico.
    :param goal_title: Título do objetivo (conforme a lista de objetivos ativos).
    :param amount: Valor do aporte.
    """
    pass

def simular_poupanca(target_amount: float, monthly_saving: float):
    """
    Simula em quanto tempo o cliente atingirá um valor alvo guardando uma quantia mensal.
    :param target_amount: Valor que deseja atingir.
    :param monthly_saving: Quanto o cliente consegue guardar por mês.
    """
    pass

def cancelar_objetivo(goal_title: str):
    """
    Remove/Cancela um objetivo financeiro.
    :param goal_title: Título do objetivo a ser cancelado.
    """
    pass

def responder_conversa(reply_text: str):
    """
    Responde mensagens gerais, saudações, dúvidas ou qualquer interação que não exija uma das outras ferramentas.
    :param reply_text: O texto da resposta amigável para o usuário.
    """
    pass

# List of tools to be passed to Gemini
FINANCIAL_TOOLS = [
    registrar_gasto,
    criar_objetivo,
    listar_objetivos,
    definir_meta_mensal,
    obter_resumo_mensal,
    registrar_aporte,
    simular_poupanca,
    cancelar_objetivo,
    responder_conversa
]
