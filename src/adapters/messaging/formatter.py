from datetime import datetime
from typing import List, Dict, Any

class MessageFormatter:
    """
    Utility to format messages with a premium, aesthetic look for the WhatsApp Business environment.
    Uses emojis, dividers, and structured layouts.
    """
    
    @staticmethod
    def header(title: str) -> str:
        return f"✨ *{title.upper()}* ✨\n{'-'*20}\n"

    @staticmethod
    def footer() -> str:
        return f"\n{'-'*20}\n🚀 *FinBot* - Seu assistente inteligente"

    @staticmethod
    def format_spending_summary(summary: List[Dict[str, Any]]) -> str:
        msg = MessageFormatter.header("Resumo de Gastos")
        
        for item in summary:
            # item: {category, limit_amount, total_spent, available, percentage_used}
            emoji = "✅" if item['percentage_used'] < 80 else "⚠️" if item['percentage_used'] < 100 else "🚨"
            msg += f"{emoji} *{item['category']}*\n"
            msg += f"   💰 Gasto: R$ {item['total_spent']:.2f}\n"
            msg += f"   🎯 Meta: R$ {item['limit_amount']:.2f}\n"
            msg += f"   📉 Disp: R$ {item['available']:.2f} ({item['percentage_used']:.1f}%)\n\n"
            
        msg += MessageFormatter.footer()
        return msg

    @staticmethod
    def format_transaction_success(category: str, amount: float, description: str = None) -> str:
        msg = MessageFormatter.header("Gasto Registrado")
        msg += f"✅ Categoria: *{category}*\n"
        msg += f"💵 Valor: *R$ {amount:.2f}*\n"
        if description:
            msg += f"📝 Descrição: _{description}_\n"
        msg += MessageFormatter.footer()
        return msg

    @staticmethod
    def format_goal_list(goals: List[Dict[str, Any]]) -> str:
        msg = MessageFormatter.header("Objetivos Financeiros")
        if not goals:
            msg += "Você não possui objetivos ativos no momento. Que tal criar um? 😊"
        else:
            for g in goals:
                # g: {title, target_amount, current_amount, status, deadline}
                progress = (g['current_amount'] / g['target_amount']) * 100 if g['target_amount'] > 0 else 0
                msg += f"🎯 *{g['title']}*\n"
                msg += f"   💰 Progresso: R$ {g['current_amount']:.2f} / R$ {g['target_amount']:.2f}\n"
                msg += f"   📊 {MessageFormatter._progress_bar(progress)}\n"
                if g['deadline']:
                    msg += f"   📅 Prazo: {g['deadline']}\n"
                msg += "\n"
        msg += MessageFormatter.footer()
        return msg

    @staticmethod
    def _progress_bar(percentage: float, length: int = 10) -> str:
        filled = int(length * percentage / 100)
        filled = min(filled, length)
        bar = "▓" * filled + "░" * (length - filled)
        return f"{bar} {percentage:.1f}%"

    @staticmethod
    def error(message: str) -> str:
        return f"❌ *OPS! ALGO DEU ERRADO*\n\n{message}\n\nSe o problema persistir, tente novamente em instantes."
