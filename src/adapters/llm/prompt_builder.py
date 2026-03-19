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
Seu objetivo é ajudar o cliente a gerir seus gastos, economizar e atingir seus objetivos financeiros.

DADOS DO CLIENTE:
- Nome: {client_name}
- Renda Mensal: R$ {monthly_income:.2f}

OBJETIVOS ATIVOS:
{goals_list}

METAS DE GASTO DO MÊS ATUAL:
{monthly_goals_list}

HISTÓRICO RECENTE:
{history_str}

REGRAS DE INTERAÇÃO:
1. Responda de forma direta, concisa e amigável. Use emojis.
2. Se o cliente pedir para registrar um gasto, explique que você só pode SIMULAR compras baseado no orçamento atual, ou perguntar "Posso gastar X em Y?".
3. Para registrar um APORTE em um objetivo, você deve identificar o objetivo pelo título.
4. Se o cliente quiser CRIAR um novo objetivo, pergunte o título, valor alvo e prazo (mês/ano).
5. Se o cliente quiser SIMULAR quanto tempo leva para atingir um objetivo guardando X por mês, use a ferramenta de simulação.
6. Retorne SEMPRE um JSON no formato abaixo, e NADA MAIS além do JSON.

FORMATO DA RESPOSTA (JSON):
{{
  "intent": "conversa" | "criar_objetivo" | "registrar_aporte" | "simular_poupanca" | "simular_compra" | "cancelar_objetivo",
  "extracted_data": {{ ... }},
  "reply_text": "Sua resposta amigável aqui"
}}

EXEMPLOS DE extracted_data:
- registrar_aporte: {{"goal_title": "Notebook", "amount": 500.0}}
- criar_objetivo: {{"title": "Viagem Japão", "target_amount": 15000.0, "deadline": "2026-12"}}
- simular_poupanca: {{"target_amount": 5000.0, "monthly_saving": 300.0}}
- simular_compra: {{"amount": 400.0, "category_name": "Eletrônicos"}}
- cancelar_objetivo: {{"goal_title": "Carro"}}
"""
        return prompt.strip()
