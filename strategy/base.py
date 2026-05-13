from abc import ABC, abstractmethod
from typing import Optional, Tuple
from sodex import OrderSide

class BaseStrategy(ABC):
    """
    Interface base para todas as estratégias de trading.
    Define o contrato que o TraderEngine espera.
    """

    @abstractmethod
    def analyze(self, market_data: dict) -> Tuple[Optional[OrderSide], float]:
        """
        Analisa os dados de mercado e retorna uma sugestão de entrada.
        
        Args:
            market_data: Dicionário contendo preços, indicadores e sinais externos.
            
        Returns:
            Tuple[Optional[OrderSide], float]: (Lado da ordem, Preço sugerido)
        """
        pass

    @abstractmethod
    def get_tp_sl(self, fill_price: float, qty: float, notional: float) -> Tuple[float, float]:
        """
        Calcula os níveis de Take Profit e Stop Loss.
        
        Args:
            fill_price: Preço de execução da entrada.
            qty: Quantidade executada.
            notional: Valor nominal do trade.
            
        Returns:
            Tuple[float, float]: (Preço TP, Preço SL)
        """
        pass

    @abstractmethod
    def check_exit(self, side: OrderSide, current_data: dict) -> bool:
        """
        Verifica se há um sinal de saída antecipada (ex: cruzamento inverso).
        """
        pass
