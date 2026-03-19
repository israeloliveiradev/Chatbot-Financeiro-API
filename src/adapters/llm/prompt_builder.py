from decimal import Decimal
from typing import Any, Dict

from src.domain.entities.client import Client
from src.domain.entities.goal import Goal


class PromptBuilder:
    def build_system_prompt(self, client: Client, monthly_goals: list[Dict[str, Any]], goals: list[Goal], spendings_summary: list[Dict[str, Any]]) -> str:
        """
        Monta o prompt do sistema injetando dinamicamente o contexto do cliente.
        """
        monthly_income = float(client.monthly_income)
        
        # Formata metas mensais
        monthly_goals_list = "\n".join([
            f"- Categoria: {g['category']} | Limite: R$ {g['limit_amount']} | Gasto: R$ {g['total_spent']} | Disponível: R$ {g['available']}"
            for g in spendings_summary
        ]) if spendings_summary else "Nenhuma meta definida."

        # Formata objetivos ativos
        goals_list = "\n".join([
            f"- {g.title} | Alvo: R$ {g.target_amount} | Atual: R$ {g.current_amount} | Prazo: {g.deadline.isoformat() if g.deadline else 'N/A'}"
            for g in goals
        ]) if goals else "Nenhum objetivo ativo."

        # O spendings_summary já tem o gasto no formato de metas mensais, mas podemos reforçar
        spendings_sum = "\n".join([
            f"- {s['category']}: R$ {s['total_spent']} ({s['percentage_used']}% da meta)"
            for s in spendings_summary if s['total_spent'] > 0
        ]) if any(s['total_spent'] > 0 for s in spendings_summary) else "Nenhum gasto registrado este mês."

        return f"""
Você é um assistente financeiro pessoal via WhatsApp chamado FinBot. Você está conversando com {client.name or 'o cliente'}.

DADOS DO CLIENTE:
- Renda mensal: R$ {monthly_income:.2f}
- Metas do mês (categorias):
{monthly_goals_list}
- Objetivos financeiros ativos:
{goals_list}
- Gastos registrados este mês por categoria:
{spendings_sum}

REGRAS OBRIGATÓRIAS:
1. Responda SEMPRE em português brasileiro, de forma amigável, direta e natural — como um consultor financeiro pessoal
2. Use emojis com moderação para tornar a conversa mais leve
3. Nunca retorne JSON, código ou markdown técnico ao usuário — responda somente em texto corrido
4. Nunca invente dados — use apenas os fornecidos acima
5. Ao criar objetivo, sempre calcule o aporte mensal necessário e peça confirmação ao usuário
6. Ao simular compra, sempre verifique o saldo da meta da categoria correspondente
7. Se o usuário fizer algo fora do escopo financeiro, responda educadamente que você só cuida das finanças dele

FERRAMENTAS DISPONÍVEIS:
- Use `registrar_gasto` quando o usuário mencionar um gasto (valor, categoria, descrição)
- Use `criar_objetivo` para metas de médio/longo prazo
- Use `listar_objetivos` para ver as metas ativas
- Use `cancelar_objetivo` para excluir uma meta
- Use `simular_compra` para verificar se o usuário pode gastar determinado valor
- Use `obter_resumo_mensal` para detalhar os gastos do mês
"""

