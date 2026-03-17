from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Dict, Any

class SimulateSavings:
    async def execute(self, target_amount: Decimal, monthly_saving: Decimal, start_date: date) -> Dict[str, Any]:
        """
        Simula em quanto tempo um objetivo será atingido dado um aporte mensal.
        Retorna a quantidade de meses e a data estimada.
        Não consome repositórios, é puro cálculo.
        """
        if monthly_saving <= 0:
            return {"possible": False, "reason": "Aporte mensal deve ser maior que zero."}
        if target_amount <= 0:
            return {"possible": False, "reason": "Objetivo deve ser maior que zero."}

        months_needed = int(-(-target_amount // monthly_saving))  # Ceil division
        estimated_date = start_date + relativedelta(months=months_needed)
        
        return {
            "possible": True,
            "months_needed": months_needed,
            "estimated_date": estimated_date.isoformat(),
            "target_amount": float(target_amount),
            "monthly_saving": float(monthly_saving),
            "total_saved": float(months_needed * monthly_saving)
        }
