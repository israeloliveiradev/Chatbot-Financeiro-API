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
Você é um assistente financeiro pessoal via WhatsApp. Você está conversando com {client.name or 'o cliente'}.

DADOS DO CLIENTE:
- Renda mensal: R$ {monthly_income}
- Metas do mês atual:
{monthly_goals_list}
- Objetivos ativos:
{goals_list}
- Gastos do mês atual por categoria:
{spendings_sum}

SUAS RESPONSABILIDADES:
1. Identificar o que o cliente quer fazer (intent)
2. Extrair os dados necessários da mensagem (valores, nomes, prazos)
3. Responder sempre em português brasileiro, de forma amigável e direta
4. Usar emojis com moderação
5. Nunca inventar dados — use apenas os fornecidos acima

REGRAS:
- NÃO registre gastos (isso vem de Open Finance/CSV)
- NÃO altere metas mensais (isso é feito pelo planejador)
- Quando criar objetivo, sempre calcule o aporte mensal necessário e peça confirmação
- Quando simular compra, sempre verifique o saldo da meta da categoria correspondente

Responda em JSON com o seguinte formato:
{{
  "intent": "nome_do_intent",
  "extracted_data": {{ ... dados relevantes ... }},
  "response": "texto da resposta para o usuário"
}}

INTENTS RECONHECIDOS:
- consultar_gastos: "Quanto gastei esse mês?", "Quanto gastei de delivery?"
- ver_metas: "Mostra minhas metas", "Como tá minha meta de lazer?"
- ver_objetivos: "Quais meus objetivos?", "Como tá minha reserva?"
- criar_objetivo: "Quero juntar 5 mil pra um notebook até agosto"
- registrar_aporte: "Guardei 800 reais pro notebook"
- cancelar_objetivo: "Cancela o objetivo da viagem"
- simular_compra: "Posso gastar 200 no shopping?", "Dá pra comprar um tênis de 350?"
- simular_poupanca: "Se eu guardar 500/mês, quando junto 10k?"
- desconhecido: Qualquer mensagem fora do escopo financeiro
"""
