"""
core/terms.py
Legal text for CascadeTrade Terminal.
Terms of Service, Privacy Policy, Risk Disclaimer, Cookie Notice.
All text stored here so it can be updated in one place.
"""

TERMS_OF_SERVICE = """
Roleigh QuanTrader — Terms of Service

Last updated: June 2026

By creating an account and using Roleigh QuanTrader ("the Service"), you agree to the following terms.

1. DESCRIPTION OF SERVICE

Roleigh QuanTrader is automated trading software that connects to your Alpaca brokerage account via API keys. The Service analyses market data and generates trading signals which can be executed automatically or manually.

Roleigh QuanTrader is SOFTWARE. It is NOT a financial advisor, investment advisor, broker-dealer, or any form of regulated financial service.

2. YOUR ACCOUNTS

2.1 Alpaca Account
You are responsible for creating and maintaining your own Alpaca brokerage account. Roleigh QuanTrader does not open, manage, or hold your Alpaca account. All trading funds are held by Alpaca Securities LLC, a FINRA-registered broker-dealer and SIPC member.

2.2 API Keys
You provide your Alpaca API keys to Roleigh QuanTrader so the software can execute trades on your behalf. Your API keys are encrypted at rest in our database. You may revoke your API keys at any time through your Alpaca dashboard, which immediately disconnects Roleigh QuanTrader from your account.

2.3 OpenAI Account (Optional)
If you choose to use AI sentiment analysis, you must create your own OpenAI account and provide your own API key. Roleigh QuanTrader does not access, store, or manage your OpenAI billing.

2.4 Discord (Optional)
If you choose to receive trade alerts via Discord, you must create your own Discord server and webhook. Roleigh QuanTrader sends messages to your webhook URL only.

2.5 Finnhub Account (Optional)
If you choose to use the IPO & New Listings scanner, you may provide your own Finnhub API key. Roleigh QuanTrader uses it to fetch upcoming IPO data. Roleigh QuanTrader does not access, store, or manage your Finnhub billing.

3. TRADING RISKS

3.1 Paper Trading
Paper trading uses simulated money with real market data. Paper trading results do NOT guarantee similar results with real money. Slippage, liquidity, and execution differences exist between paper and live trading.

3.2 Real Money Trading
Trading stocks involves SIGNIFICANT RISK OF LOSS. You could lose some or all of your invested capital. Past performance does not guarantee future results. The value of your investments can go down as well as up.

3.3 No Guarantee of Profits
Roleigh QuanTrader makes NO guarantee of profits, returns, or positive performance. The Service may produce losses. You trade entirely at your own risk.

3.4 Automated Trading
When the bot is running, it will execute trades automatically based on your configured settings. This includes buying and selling stocks without manual confirmation. You are responsible for monitoring the bot and stopping it if undesired trades occur.

3.5 Stop Losses and Risk Management
While Roleigh QuanTrader includes stop-loss and risk management features, these are not foolproof. Market gaps, low liquidity, and system outages can cause stop losses to execute at prices worse than configured. Roleigh QuanTrader is not liable for any losses resulting from failed or delayed stop-loss executions.

4. FEES AND PAYMENTS

4.1 Subscription Fees
Roleigh QuanTrader may charge a monthly subscription fee for use of the Service. Pricing is subject to change. You will be notified of any price changes via email or Discord at least 30 days in advance.

4.2 Trading Fees
Alpaca charges commission-free trades on paper accounts. Live accounts may incur fees as per Alpaca's fee schedule. Roleigh QuanTrader is not responsible for Alpaca's fees.

4.3 Refunds
A 14-day money-back guarantee is available for new subscribers. After that, subscriptions can be cancelled at any time. You will retain access until the end of your current billing period.

5. DATA AND PRIVACY

Please refer to our Privacy Policy for full details on data collection, storage, and your rights.

Key points:
- We store your username, hashed password, encrypted API keys, and trading preferences
- We NEVER see, handle, or have access to your bank details or trading funds
- Payment processing is handled by Stripe — we never see your card number
- You can request deletion of all your data at any time (see section 8)

6. INTELLECTUAL PROPERTY

6.1 Roleigh QuanTrader
All code, design, and content of Roleigh QuanTrader is the intellectual property of the developer. You may not reverse engineer, decompile, redistribute, or resell the Service without explicit written permission.

6.2 Your Data
Your trade history, settings, and preferences remain your property. You may export them at any time.

6.3 Watermarking
CSV exports from Roleigh QuanTrader include a watermark identifying the source. This watermark must not be removed.

7. LIMITATION OF LIABILITY

7.1 To the maximum extent permitted by law, Roleigh QuanTrader and its developer shall NOT be liable for any direct, indirect, incidental, special, consequential, or punitive damages arising from:
- Any trading losses, including loss of capital
- System downtime, bugs, or errors
- Incorrect signals, missed trades, or delayed executions
- Any action or inaction of Alpaca, OpenAI, Finnhub, or any third-party service
- Any unauthorised access to your account due to compromised API keys

7.2 You acknowledge that automated trading carries inherent risks and you assume full responsibility for all trading decisions, even those made automatically by the Service.

8. ACCOUNT TERMINATION AND DATA DELETION

8.1 You may delete your account at any time. Upon deletion, all your data (username, encrypted API keys, trade history, settings) will be permanently removed from our servers within 30 days.

8.2 You must revoke your API keys from your Alpaca dashboard before or after account deletion. Roleigh QuanTrader is not responsible for API keys that remain active in your Alpaca account after service termination.

8.3 We reserve the right to suspend or terminate accounts that violate these terms, attempt to abuse the Service, or engage in market manipulation.

9. AVAILABILITY

The Service is provided "as is" and "as available." We do not guarantee uninterrupted access. Scheduled maintenance will be communicated in advance where possible. We are not liable for any losses resulting from Service downtime.

10. CHANGES TO TERMS

We may update these Terms of Service from time to time. Material changes will be communicated via email or Discord at least 30 days before taking effect. Continued use of the Service after changes constitutes acceptance of the new terms.

11. GOVERNING LAW

These terms are governed by the laws of England and Wales. Any disputes shall be resolved through the courts of England and Wales.

12. CONTACT

For questions about these terms, please contact us through our Discord server.

By creating an account and using Roleigh QuanTrader, you confirm that you have read, understood, and agree to these Terms of Service.
"""


RISK_DISCLAIMER = """
⚠️ RISK DISCLAIMER

Trading stocks involves SIGNIFICANT RISK OF LOSS. You could lose some or all of your invested capital. Past performance does not guarantee future results.

Roleigh QuanTrader is automated trading SOFTWARE. It is NOT a financial advisor, investment advisor, or broker-dealer. The signals and trades generated by the Service are based on technical analysis and do not constitute financial advice.

• Paper trading uses simulated money. Paper trading results do NOT guarantee similar results with real money.
• Automated trading means the bot will buy and sell stocks WITHOUT manual confirmation when running.
• Stop losses and risk management features are NOT foolproof and may not execute as expected.
• You are solely responsible for monitoring your account and managing your risk.
• Always start with paper trading to test strategies before using real money.

If you are unsure whether automated trading is suitable for you, consult a qualified financial advisor.

Roleigh QuanTrader is not responsible for any losses or damages arising from the use of the Service. All money is held by Alpaca Securities LLC, a FINRA-registered broker-dealer. SIPC insurance covers up to $500,000.

By using this Service, you acknowledge these risks and accept full responsibility for your trading decisions.
"""


PRIVACY_POLICY = """
Roleigh QuanTrader — Privacy Policy

Last updated: June 2026

1. WHO WE ARE

Roleigh QuanTrader is developed and operated by an independent developer based in the United Kingdom. For the purposes of GDPR, we are the data controller.

2. WHAT DATA WE COLLECT

2.1 Account Data
- Username
- Hashed password (never stored in plain text)
- Email address (if provided)
- Account creation date
- Last login date

2.2 Trading Data
- Alpaca API key (encrypted at rest)
- Alpaca secret key (encrypted at rest)
- OpenAI API key (encrypted at rest)
- Finnhub API key (encrypted at rest)
- Discord webhook URL (encrypted at rest)
- Trading preferences and settings
- Trade history generated by the Service

2.3 Usage Data
- Login timestamps
- Feature usage patterns
- Error logs (for debugging)

2.4 WHAT WE DO NOT COLLECT
- Bank account details — NEVER. Payment processing is handled by Stripe.
- Card numbers — NEVER. Stripe processes all payments.
- Alpaca account passwords — NEVER. We only use API keys.
- Trading funds — NEVER. All money is held by Alpaca.

3. HOW WE USE YOUR DATA

3.1 To provide the Service
- Username and hashed password for authentication
- API keys to connect to Alpaca for automated trading
- OpenAI key for AI sentiment analysis
- Finnhub key for IPO and new listings scanning
- Discord webhook for trade alerts
- Trading preferences to configure the bot

3.2 To improve the Service
- Error logs to fix bugs
- Anonymised usage patterns to improve features

3.3 We will NEVER
- Sell your personal data to third parties
- Use your trading data to trade on our own behalf
- Share your API keys with anyone
- Access your Alpaca account beyond what is needed for the Service

4. HOW WE PROTECT YOUR DATA

4.1 Encryption
- API keys are encrypted at rest using Fernet symmetric encryption
- Passwords are hashed using bcrypt (never reversible)
- All connections use HTTPS encryption
- Database access is restricted to the application

4.2 Access Control
- Only you can access your own data
- No employee or third party has access to your API keys in plain text
- Encryption keys are stored separately from the database

4.3 Data Retention
- We keep your data only for as long as your account is active
- Upon account deletion, all data is permanently removed within 30 days
- Trade history is retained for your use and can be exported at any time

5. YOUR RIGHTS UNDER GDPR

You have the following rights:

5.1 Right to Access — You can request a copy of all data we hold about you. We will provide this within 30 days.

5.2 Right to Rectification — You can update your personal information at any time through the Settings page.

5.3 Right to Erasure (Right to be Forgotten) — You can delete your account at any time. All your data will be permanently removed within 30 days.

5.4 Right to Data Portability — You can export all your data (trade history, settings, preferences) in CSV format at any time from within the app.

5.5 Right to Restrict Processing — You can disable the trading bot at any time without deleting your account.

5.6 Right to Object — You can object to any processing of your data that you believe is unlawful.

5.7 Right to Lodge a Complaint — If you believe we have mishandled your data, you can complain to the Information Commissioner's Office (ICO) at ico.org.uk.

6. THIRD-PARTY SERVICES

Roleigh QuanTrader connects to the following third-party services. Each has their own privacy policy:

6.1 Alpaca (alpaca.markets/privacy) — Holds your trading funds and executes trades. We only send API keys to connect; we do not share personal data with Alpaca beyond what is necessary for account authentication.

6.2 OpenAI (openai.com/policies/privacy-policy) — Processes stock news for sentiment analysis. Only stock symbols and news headlines are sent. No personal data is sent to OpenAI.

6.3 Discord (discord.com/privacy) — Receives trade alert messages via your webhook URL. Only trade information (symbol, action, confidence) is sent. No personal data is included in Discord messages when Privacy Mode is enabled.

6.4 Stripe (stripe.com/privacy) — Processes subscription payments. We never see or store your card details. Stripe handles all payment data securely.

6.5 Finnhub (finnhub.io/privacy-policy) — Provides IPO and market data. Only stock symbols and date ranges are sent. No personal data is sent to Finnhub.

7. DATA BREACHES

In the event of a data breach that is likely to result in a risk to your rights and freedoms, we will:
- Notify you via email within 72 hours of becoming aware of the breach
- Notify the ICO if required by law
- Take immediate steps to secure the data and prevent further breaches

8. CHANGES TO THIS POLICY

We may update this Privacy Policy from time to time. Material changes will be communicated via email at least 30 days before taking effect. Continued use of the Service after changes constitutes acceptance of the new policy.

9. CONTACT

For privacy-related questions or data requests, please contact us through our Discord server or via email.
"""


COOKIE_NOTICE = """
🍪 Cookie Notice

Roleigh QuanTrader uses essential cookies for:
- Session management (keeping you logged in)
- Security (preventing unauthorised access)

We do NOT use advertising cookies, tracking cookies, or analytics cookies at this time.

If we add non-essential cookies in the future (such as analytics), we will update this notice and request your consent before enabling them.

This notice applies to the Roleigh QuanTrader web application only. Third-party services (Alpaca, OpenAI, Discord, Stripe, Finnhub) may set their own cookies according to their own policies.
"""


ONBOARDING_STEPS = [
    {
        "step": 1,
        "title": "🏦 Create Your Alpaca Account",
        "description": "Alpaca is a FINRA-registered broker-dealer where your money lives and your trades happen. Paper trading is completely free.",
        "url": "https://alpaca.markets",
        "url_text": "Open Alpaca",
        "instructions": [
            "Go to alpaca.markets and sign up for a free account",
            "Verify your email and complete the registration",
            "Start with Paper Trading (fake money, real market data)",
            "Go to Your Apps → Create New App → Generate API Keys",
            "Copy your API Key and Secret Key — you'll paste these into Roleigh QuanTrader",
        ],
        "important": "Your money NEVER passes through Roleigh QuanTrader. It stays at Alpaca, which is SIPC insured up to $500,000.",
    },
    {
        "step": 2,
        "title": "🧠 Create Your OpenAI Account (Optional)",
        "description": "Used for AI news sentiment analysis. The bot works without it, but you won't get AI-powered news insights.",
        "url": "https://platform.openai.com",
        "url_text": "Open OpenAI",
        "instructions": [
            "Go to platform.openai.com and create a free account",
            "Navigate to API Keys → Create new secret key",
            "Add $5 credit (this lasts months for sentiment analysis)",
            "Copy your API key — you'll paste this into Roleigh QuanTrader Settings",
        ],
        "important": "Optional. The bot's core signals (RSI, MACD, Bollinger, VIX filter) all work without OpenAI.",
    },
    {
        "step": 3,
        "title": "📡 Set Up Discord Alerts (Optional)",
        "description": "Get instant notifications when trades happen, stops trigger, or profits are extracted.",
        "url": "https://discord.com",
        "url_text": "Open Discord",
        "instructions": [
            "Create a Discord server (or use an existing one)",
            "Go to Server Settings → Integrations → Webhooks",
            "Click 'New Webhook' and give it a name like 'Roleigh QuanTrader Alerts'",
            "Copy the Webhook URL — you'll paste this into Roleigh QuanTrader Settings",
            "Optional: Create a second webhook for Daily P&L reports",
        ],
        "important": "Optional. All alerts are also visible in the app. Discord just lets you see them on your phone.",
    },
    {
        "step": 4,
        "title": "🚀 You're Ready!",
        "description": "Start with Paper Trading to test the system. When you're confident, switch to real money by funding your Alpaca account directly.",
        "url": "",
        "url_text": "",
        "instructions": [
            "Paste your Alpaca API keys into Roleigh QuanTrader Settings (left sidebar)",
            "Click 'Connect' on the Auto Trade tab",
            "Start with Paper Trading to watch how the bot performs",
            "Monitor the bot for a few days before considering real money",
            "When ready, fund your Alpaca account directly (not through Roleigh QuanTrader)",
        ],
        "important": "ALWAYS start with paper trading. Never risk real money until you understand how the bot works.",
    },
]


def get_terms_summary():
    """Return a short summary for display in the app."""
    return "By using Roleigh QuanTrader, you agree that: (1) Trading involves risk and you may lose money, (2) Roleigh QuanTrader is software not a financial advisor, (3) Your money is held by Alpaca not Roleigh QuanTrader, (4) You can revoke API keys at any time, (5) Past performance does not guarantee future results."


def get_risk_summary():
    """Return a one-line risk summary for display in the app."""
    return "⚠️ Trading involves significant risk of loss. Not financial advice. Always start with paper trading."


def get_tier_info():
    """Return tier information for display in the app."""
    return {
        "starter": {
            "name": "Starter",
            "icon": "🪣",
            "features": [
                "Paper trading only (no real money)",
                "3-bucket auto-trading system",
                "Basic signals (RSI, volume)",
                "Dividend tracking",
                "Discord trade alerts",
                "Backtesting",
                "1 Alpaca account",
            ],
        },
        "pro": {
            "name": "Roleigh QuanTrader Pro",
            "icon": "💎",
            "features": [
                "Everything in Starter",
                "Real money trading enabled",
                "Advanced signals (MACD, Bollinger, MA Cross, ATR)",
                "VIX fear filter (blocks buying in volatile markets)",
                "OpenAI news sentiment analysis",
                "IPO & New Listings scanner (Finnhub)",
                "DRIP calculator & dividend calendar",
                "Diamond Standard metrics (Sortino, Calmar, Omega)",
                "Auto profit extraction to withdrawal pot",
                "Priority Discord alerts",
            ],
        },
        "fund": {
            "name": "Roleigh QuanTrader Fund",
            "icon": "🏦",
            "features": [
                "Everything in Pro",
                "Multiple Alpaca accounts",
                "Auto-rebalancing (keeps buckets on target)",
                "Weekly performance reports auto-posted",
                "Portfolio risk score",
                "Advanced backtesting",
                "Full trade journal with AI notes",
                "Priority support",
                "Early access to new features",
            ],
        },
    }
