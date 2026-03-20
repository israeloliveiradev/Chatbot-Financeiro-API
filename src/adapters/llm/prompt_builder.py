from datetime import date
from typing import List, Dict, Any

class PromptBuilder:
    def build_system_prompt(
        self,
        client_name: str,
        monthly_income: float,
        goals: List[Dict[str, Any]],
        spendings_summary: List[Dict[str, Any]],
        history: List[Dict[str, str]]
    ) -> str:
        """
        Constrói o prompt do sistema para o Gemini, incluindo contexto do cliente.
        """
        goals_list = "\n".join([
            f"- {g['title']}: Alvo R$ {g['target_amount']} | Atual R$ {g['current_amount']} | Status: {g['status']} | ID: {g['id']}"
            for g in goals
        ]) if goals else "Nenhum objetivo cadastrado."

        # BUG-02 FIX: itera sobre spendings_summary corretamente (que vem do GetMonthlySpending)
        monthly_goals_list = "\n".join([
            f"- Categoria: {s['category']} | Limite: R$ {s['limit_amount']} | Gasto: R$ {s['total_spent']} | Disponível: R$ {s['available']}"
            for s in spendings_summary
        ]) if spendings_summary else "Nenhuma meta mensal definida."

        history_str = "\n".join([
            f"{'Usuário' if h['role'] == 'user' else 'Bot'}: {h['content']}"
            for h in history
        ]) if history else "Sem histórico."

        prompt = f"""
Você é um ASSISTENTE FINANCEIRO PESSOAL inteligente e amigável no WhatsApp.
Seu objetivo é ajudar o cliente {client_name} a gerir seus gastos, economizar e atingir seus objetivos financeiros.

DADOS DO CLIENTE:
- Nome: {client_name}
- Renda Mensal: R$ {monthly_income:.2f}

OBJETIVOS ATIVOS:
{goals_list}

METAS DE GASTO DO MÊS ATUAL:
{monthly_goals_list}

HISTÓRICO RECENTE:
{history_str}

REGRAS DE COMPORTAMENTO:
1. Responda de forma direta, concisa e amigável. Use emojis.
2. Seja proativo: se o cliente tiver dinheiro sobrando no orçamento, sugira aportar em um objetivo.
3. Se o cliente perguntar algo sobre seu dinheiro, use as ferramentas disponíveis para consultar os dados acima.
4. Para qualquer ação (criar objetivo, registrar gasto, simular, etc), use sempre a ferramenta correspondente.
5. Se não houver uma ferramenta específica para o que o usuário quer, responda educadamente via chat.
"""
        return prompt.strip()
