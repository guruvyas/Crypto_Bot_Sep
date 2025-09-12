Backend Requirement for Crypto Trading Bot (Gemini Sandbox)

Tech stack: Python (FastAPI), SQLite, Gemini Sandbox (REST + WebSocket). 
Single process only, lock guard. Config in YAML. Secrets in env.

Session lifecycle: Only one session active at a time. On app start create session with unique name + date, starting balance, allocation, mode (full or session amount). End on request or timeout. Persist session summary JSON/CSV.

Entities: Session, Order, Position, Fill, ActivityLog, PriceBar, ConfigSnapshot. ActivityLog must log every action in plain English.

UI contract: Provide one dashboard endpoint returning portfolio total, session allocation, session P&L, cumulative P&L, open positions, open orders, recent fills, activity feed. Endpoints: start, pause, end session.

Trading logic (V1): Trend, Mean Reversion, Breakout. Each with stop/target rules as defined.

Risk mgmt: One position per symbol. Position sizing = session allocation (fixed $ risk or fractional). Hard stops. Guardrails: max positions, max loss, max order size, cooldown, whitelist.

Order handling: Deterministic client_order_id, bracket orders with stop/target, retries with backoff, dry-run toggle.

Persistence: Store all session data in DB + write JSON/CSV summaries. Cache P&L and balances for fast reads.
