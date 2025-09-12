import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from decimal import Decimal, ROUND_DOWN
import logging

from app.core.database import AsyncSessionLocal
from app.models.order import Order, OrderType, OrderSide, OrderStatus
from app.models.position import Position, PositionSide, PositionStatus
from app.models.fill import Fill
from app.models.activity_log import ActivityLog
from app.services.gemini_client import gemini_client
from app.services.session_manager import session_manager
from app.core.config import trading_config

logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self):
        self._pending_orders: Dict[str, Order] = {}
        self._order_lock = asyncio.Lock()
        self._retry_delays = [1, 2, 5, 10, 30]  # Exponential backoff delays
        
    def _generate_client_order_id(self, symbol: str, side: str, strategy: str = None) -> str:
        """Generate deterministic client order ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        strategy_prefix = f"{strategy}_" if strategy else ""
        return f"{strategy_prefix}{symbol}_{side}_{timestamp}_{uuid.uuid4().hex[:8]}"
    
    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        strategy_name: Optional[str] = None,
        strategy_signal: Optional[Dict] = None,
        dry_run: bool = False
    ) -> Order:
        """Submit a new order to the exchange"""
        
        async with self._order_lock:
            # Get current session
            session = await session_manager.get_current_session()
            if not session or not session.is_active:
                raise ValueError("No active session for order submission")
            
            # Generate client order ID
            client_order_id = self._generate_client_order_id(
                symbol, side.value, strategy_name
            )
            
            # Create order record
            order = Order(
                session_id=session.id,
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                remaining_quantity=quantity,
                price=price,
                stop_price=stop_price,
                strategy_name=strategy_name,
                strategy_signal=str(strategy_signal) if strategy_signal else None,
                status=OrderStatus.PENDING
            )
            
            # Store in database
            async with AsyncSessionLocal() as db:
                db.add(order)
                await db.commit()
                await db.refresh(order)
                
                # Log order creation
                activity_log = ActivityLog.create_order_submitted(
                    session.id, order.id, symbol, side.value,
                    quantity, order_type.value, strategy_name
                )
                db.add(activity_log)
                await db.commit()
            
            # Submit to exchange (unless dry run)
            if not dry_run:
                await self._submit_to_exchange(order)
            else:
                logger.info(f"DRY RUN: Would submit order {order.client_order_id}")
            
            return order
    
    async def submit_bracket_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        entry_price: Optional[float] = None,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        strategy_name: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Order]:
        """Submit a bracket order (entry + stop loss + take profit)"""
        
        # Submit main order
        main_order = await self.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.LIMIT if entry_price else OrderType.MARKET,
            price=entry_price,
            strategy_name=strategy_name,
            dry_run=dry_run
        )
        
        bracket_orders = {"main": main_order}
        
        # Submit stop loss order if specified
        if stop_loss_price:
            stop_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
            stop_order = await self.submit_order(
                symbol=symbol,
                side=stop_side,
                quantity=quantity,
                order_type=OrderType.STOP_LOSS,
                stop_price=stop_loss_price,
                strategy_name=strategy_name,
                dry_run=dry_run
            )
            
            # Link orders
            async with AsyncSessionLocal() as db:
                main_order.stop_loss_order_id = stop_order.id
                stop_order.parent_order_id = main_order.id
                db.add(main_order)
                db.add(stop_order)
                await db.commit()
            
            bracket_orders["stop_loss"] = stop_order
        
        # Submit take profit order if specified
        if take_profit_price:
            tp_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
            tp_order = await self.submit_order(
                symbol=symbol,
                side=tp_side,
                quantity=quantity,
                order_type=OrderType.TAKE_PROFIT,
                price=take_profit_price,
                strategy_name=strategy_name,
                dry_run=dry_run
            )
            
            # Link orders
            async with AsyncSessionLocal() as db:
                main_order.take_profit_order_id = tp_order.id
                tp_order.parent_order_id = main_order.id
                db.add(main_order)
                db.add(tp_order)
                await db.commit()
            
            bracket_orders["take_profit"] = tp_order
        
        return bracket_orders
    
    async def _submit_to_exchange(self, order: Order):
        """Submit order to Gemini exchange with retry logic"""
        for attempt in range(order.max_retries + 1):
            try:
                # Prepare order parameters for Gemini
                gemini_order_type = self._convert_order_type_to_gemini(order.order_type)
                
                # Submit to Gemini
                response = await gemini_client.place_order(
                    symbol=order.symbol.lower(),
                    amount=str(order.quantity),
                    price=str(order.price) if order.price else "0",
                    side=order.side.value,
                    order_type=gemini_order_type,
                    client_order_id=order.client_order_id,
                    stop_price=str(order.stop_price) if order.stop_price else None
                )
                
                # Update order with exchange response
                async with AsyncSessionLocal() as db:
                    order.exchange_order_id = response.get("order_id")
                    order.status = OrderStatus.SUBMITTED
                    order.submitted_at = datetime.utcnow()
                    order.exchange_response = str(response)
                    order.retry_count = attempt
                    
                    db.add(order)
                    await db.commit()
                
                logger.info(f"Order {order.client_order_id} submitted successfully")
                return
                
            except Exception as e:
                order.retry_count = attempt
                error_msg = str(e)
                
                if attempt >= order.max_retries:
                    # Final failure
                    async with AsyncSessionLocal() as db:
                        order.status = OrderStatus.REJECTED
                        order.rejection_reason = error_msg
                        db.add(order)
                        
                        # Log the rejection
                        activity_log = ActivityLog.create_error(
                            order.session_id,
                            f"Order {order.client_order_id} rejected after {attempt + 1} attempts: {error_msg}",
                            symbol=order.symbol
                        )
                        db.add(activity_log)
                        await db.commit()
                    
                    logger.error(f"Order {order.client_order_id} rejected permanently: {error_msg}")
                    raise Exception(f"Order submission failed: {error_msg}")
                else:
                    # Retry with backoff
                    delay = self._retry_delays[min(attempt, len(self._retry_delays) - 1)]
                    logger.warning(f"Order submission attempt {attempt + 1} failed, retrying in {delay}s: {error_msg}")
                    await asyncio.sleep(delay)
    
    def _convert_order_type_to_gemini(self, order_type: OrderType) -> str:
        """Convert internal order type to Gemini order type"""
        mapping = {
            OrderType.MARKET: "exchange market",
            OrderType.LIMIT: "exchange limit",
            OrderType.STOP_LOSS: "exchange stop limit",
            OrderType.TAKE_PROFIT: "exchange limit"
        }
        return mapping.get(order_type, "exchange limit")
    
    async def cancel_order(self, order_id: int, reason: str = "Manual cancellation") -> Order:
        """Cancel an existing order"""
        async with AsyncSessionLocal() as db:
            # Get order
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            if not order.is_active:
                raise ValueError(f"Order {order_id} is not active (status: {order.status.value})")
            
            try:
                # Cancel on exchange
                if order.exchange_order_id:
                    await gemini_client.cancel_order(order.exchange_order_id)
                
                # Update order status
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.utcnow()
                db.add(order)
                
                # Log cancellation
                activity_log = ActivityLog(
                    session_id=order.session_id,
                    order_id=order.id,
                    symbol=order.symbol,
                    activity_type=ActivityLog.ActivityType.ORDER_CANCELLED,
                    level=ActivityLog.ActivityLevel.MEDIUM,
                    message=f"Cancelled {order.side.value} order for {order.quantity} {order.symbol}: {reason}"
                )
                db.add(activity_log)
                
                await db.commit()
                await db.refresh(order)
                
                logger.info(f"Order {order.client_order_id} cancelled")
                return order
                
            except Exception as e:
                logger.error(f"Error cancelling order {order.client_order_id}: {e}")
                raise
    
    async def get_active_orders(self, session_id: Optional[int] = None) -> List[Order]:
        """Get all active orders for a session"""
        async with AsyncSessionLocal() as db:
            query = select(Order).where(
                Order.status.in_([
                    OrderStatus.PENDING,
                    OrderStatus.SUBMITTED,
                    OrderStatus.PARTIALLY_FILLED
                ])
            )
            
            if session_id:
                query = query.where(Order.session_id == session_id)
            
            result = await db.execute(query.order_by(Order.created_at.desc()))
            return result.scalars().all()
    
    async def update_order_status(self, order_id: int, status_data: Dict[str, Any]):
        """Update order status from exchange data"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            
            if not order:
                return
            
            # Update order fields based on exchange data
            old_status = order.status
            order.status = self._parse_gemini_status(status_data.get("state"))
            
            if "executed_amount" in status_data:
                order.filled_quantity = float(status_data["executed_amount"])
                order.calculate_remaining_quantity()
            
            if "avg_execution_price" in status_data:
                order.average_fill_price = float(status_data["avg_execution_price"])
            
            if order.status == OrderStatus.FILLED:
                order.filled_at = datetime.utcnow()
                order.total_value = order.filled_quantity * (order.average_fill_price or order.price or 0)
                
                # Log order fill
                activity_log = ActivityLog.create_order_filled(
                    order.session_id, order.id, order.symbol, order.side.value,
                    order.filled_quantity, order.average_fill_price, order.strategy_name
                )
                db.add(activity_log)
            
            db.add(order)
            await db.commit()
            
            # Handle position updates if order is filled
            if old_status != OrderStatus.FILLED and order.status == OrderStatus.FILLED:
                await self._handle_order_fill(order)
    
    def _parse_gemini_status(self, gemini_state: str) -> OrderStatus:
        """Convert Gemini order state to internal status"""
        mapping = {
            "live": OrderStatus.SUBMITTED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED
        }
        return mapping.get(gemini_state, OrderStatus.PENDING)
    
    async def _handle_order_fill(self, order: Order):
        """Handle position creation/update when order is filled"""
        try:
            async with AsyncSessionLocal() as db:
                # Check if this is opening or closing a position
                existing_position = await self._find_existing_position(order.symbol, order.session_id)
                
                if existing_position and existing_position.is_open:
                    # This might be closing an existing position
                    await self._update_existing_position(existing_position, order)
                else:
                    # This is opening a new position
                    await self._create_new_position(order)
                    
        except Exception as e:
            logger.error(f"Error handling order fill for {order.client_order_id}: {e}")
    
    async def _find_existing_position(self, symbol: str, session_id: int) -> Optional[Position]:
        """Find existing open position for symbol"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Position).where(
                    and_(
                        Position.symbol == symbol,
                        Position.session_id == session_id,
                        Position.status.in_([PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED])
                    )
                )
            )
            return result.scalar_one_or_none()
    
    async def _create_new_position(self, order: Order):
        """Create new position from filled order"""
        async with AsyncSessionLocal() as db:
            position_side = PositionSide.LONG if order.side == OrderSide.BUY else PositionSide.SHORT
            
            position = Position(
                session_id=order.session_id,
                symbol=order.symbol,
                side=position_side,
                quantity=order.filled_quantity,
                remaining_quantity=order.filled_quantity,
                entry_price=order.average_fill_price or order.price,
                entry_value=order.total_value,
                entry_fees=0.0,  # TODO: Calculate fees from fills
                strategy_name=order.strategy_name,
                entry_signal=order.strategy_signal
            )
            
            db.add(position)
            await db.commit()
            await db.refresh(position)
            
            # Log position opening
            activity_log = ActivityLog.create_position_opened(
                position.session_id, position.id, position.symbol,
                position.side.value, position.quantity, position.entry_price,
                position.strategy_name
            )
            db.add(activity_log)
            await db.commit()
            
            logger.info(f"Created new position: {position}")
    
    async def _update_existing_position(self, position: Position, order: Order):
        """Update existing position with new order fill"""
        # This handles position sizing changes, partial closes, etc.
        # Implementation depends on specific trading logic
        pass

# Global order manager instance
order_manager = OrderManager()