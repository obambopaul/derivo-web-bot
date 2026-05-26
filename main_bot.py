import streamlit as st
import asyncio
import collections
import pandas as pd
from deriv_api import DerivAPI

# --- UI CONFIG ---
st.set_page_config(page_title="Derivo Master Bot", layout="wide")
st.title("🚀 Derivo Ultimate Web Dashboard")

# Sidebar
st.sidebar.header("Settings")
token = st.sidebar.text_input("Deriv API Token", type="password")
stake = st.sidebar.number_input("Initial Stake ($)", value=0.35, min_value=0.35)
target = st.sidebar.number_input("Target Profit ($)", value=5.0)
stop_loss = st.sidebar.number_input("Stop Loss ($)", value=-20.0)
v_loss_req = st.sidebar.slider("Virtual Losses", 0, 5, 1)

# Main Metrics
m1, m2, m3 = st.columns(3)
pnl_metric = m1.metric("PnL", "$0.00")
streak_metric = m2.metric("Streak", "0")
status = m3.empty()

chart = st.empty()
logs = st.expander("Activity Log", expanded=True)

if 'pnl' not in st.session_state: st.session_state.pnl = 0.0
if 'log_data' not in st.session_state: st.session_state.log_data = []

async def run_bot():
    api = DerivAPI(app_id=1089)
    try:
        await api.authorize(token)
        st.toast("Connected!")
        
        history = collections.deque(maxlen=50)
        v_count = 0
        current_stake = stake
        
        sub = await api.subscribe({'ticks': 'R_100'})
        async for msg in sub:
            digit = int(str(msg['tick']['quote']).split('.')[-1][-1])
            history.append(digit)
            
            # Logic: If 3 Evens, bet Odd
            evens = [d for d in list(history)[-3:] if d % 2 == 0]
            streak = len(evens) if len(evens) == len(list(history)[-3:]) else 0
            
            # Update UI
            pnl_metric.metric("PnL", f"${st.session_state.pnl:.2f}")
            streak_metric.metric("Even Streak", str(streak))
            chart.bar_chart(pd.Series(history).value_counts())

            if streak >= 3:
                if v_count < v_loss_req:
                    v_count += 1
                    st.session_state.log_data.append("🔹 Virtual Loss Recorded")
                else:
                    status.warning("⚡ TRADING...")
                    # --- PLACE REAL TRADE ---
                    proposal = await api.proposal({"proposal": 1, "amount": current_stake, "basis": "stake", "contract_type": "DIGITODD", "currency": "USD", "duration": 1, "duration_unit": "t", "symbol": "R_100"})
                    buy = await api.buy({"buy": proposal['proposal']['id'], "price": current_stake})
                    
                    # Wait for result
                    poc = await api.subscribe({"proposal_open_contract": 1, "contract_id": buy['buy']['contract_id']})
                    async for res in poc:
                        c = res['proposal_open_contract']
                        if c['status'] in ['won', 'lost']:
                            prof = float(c['profit'])
                            st.session_state.pnl += prof
                            if prof > 0:
                                st.session_state.log_data.append(f"✅ WIN: +${prof}")
                                current_stake = stake
                                v_count = 0
                            else:
                                st.session_state.log_data.append(f"❌ LOSS: ${prof}")
                                current_stake *= 2.1
                            break
                    status.empty()
            
            # Show Logs
            with logs:
                for l in st.session_state.log_data[-5:]: st.write(l)
                
            if st.session_state.pnl >= target or st.session_state.pnl <= stop_loss:
                st.write("Target reached or Stop Loss hit.")
                break
    except Exception as e:
        st.error(f"Error: {e}")

if st.sidebar.button("START BOT"):
    if token: asyncio.run(run_bot())
    else: st.error("Enter Token!")
